//=============================================================================
// eeprom_capture_top.v —— I²C 边沿捕获 + UART 回放（EEPROM 数据通路取证）
//
// 【为什么要这个模块】
//   队友给的 eeprom_exercise_top 用两个 LED 判"通/不通"，但它的判据
//   （cfg_ok = CRC(读回数据) == EEPROM 里存的 CRC）只证明"EEPROM 内容自洽"，
//   不证明"写进去的字节回来了"——因为那个 CRC 是写的时候一起写进去的。
//   结论是"灯亮"这个信息量不够，需要看线上到底发生了什么。
//
//   本模块把 eeprom_exercise_top 的读写循环**逐行照抄**（同样的
//   WAIT_BITS / pattern 递增 / A-B 双副本），只**增加观察**：
//   把 SCL/SDA 每一次跳变的时刻与电平记进 BRAM，采满后从 UART 吐出来。
//
//   被测的 cfg_eeprom_store.v 是**原样拷贝**（sha256 必须等于
//   CE40C936C63F09E7DEE182884D4ABAA7994834388396155C21144FFD65FE931B），
//   所以抓到的就是他那份代码在真芯片上的真实行为，不是我们改过的版本。
//
// 【捕获什么】
//   每次 (SCL,SDA) 电平变化记一条 32 位记录：
//       { tstamp[23:0], scl, sda, 6'b0 }
//   · tstamp 单位 = 1 个 27 MHz 时钟 = 37.037 ns
//   · tstamp 在每个 START 条件（SCL 高时 SDA 下降）清零 ⇒ 每个事务从 0 开始，
//     24 位足够（最长事务 ~6 ms，24 位可表示 621 ms）
//   · 缓冲 8192 条，够装一次读事务（约 1700 边沿）+ 一次写事务（约 1650 边沿）
//
// 【为什么不用示波器】
//   27 MHz 采样 100 kHz I²C，时间分辨率 37 ns —— 远细于 10 µs 的位宽。
//   上升沿的模拟形状看不到（4.7k 上拉的 RC），但**谁在什么时候拉低/放开**
//   看得很清楚，而这正是判"末字节 ACK 之后从机是否还占着 SDA"所需要的。
//
// 【串口输出格式】115200 8N1，纯文本，每行：
//     表头  #EEPROBE XXXX\r\n          （XXXX = 记录条数，十六进制）
//     数据  TTTTTT,S,D\r\n             （T = tstamp 6 位十六进制，S/D = 0/1）
//   解析与画图见 tools/eeprom_capture_decode.py。
//
// 【LED】
//   led[5] = 读校验曾经通过（与 eeprom_exercise_top 同义）
//   led[3] = 曾经出现过 err
//   led[0] = 缓冲已采满（正在/即将回放）
//
// 【引脚】见 eeprom_probe.cst
//   clk = 4   sda = 25   scl = 26   uart_tx = 69   led[5]=20  led[3]=18
//   外部需要 4.7k 上拉到 3V3（裸 Nano 20K 上没有；载板上 R33/R34 + R60/R61 已有）
//=============================================================================
module eeprom_capture_top #(
    parameter integer BYTES      = 56,
    parameter integer SCL_HZ     = 100_000,
    parameter integer WAIT_BITS  = 22,
    parameter integer DEPTH_LOG2 = 13,          // 8192 条
    parameter integer BAUD       = 115200
)(
    input  wire       clk,
    inout  wire       sda,
    output wire       scl,
    output wire       uart_tx,
    output wire [5:0] led
);
    localparam integer DEPTH = (1 << DEPTH_LOG2);

    //-------------------------------------------------------------------------
    // 上电复位
    //-------------------------------------------------------------------------
    reg [15:0] por = 16'd0;
    wire rst_n = &por;
    always @(posedge clk) if (!rst_n) por <= por + 16'd1;

    //-------------------------------------------------------------------------
    // 慢节奏（与 eeprom_exercise_top 完全一致：4 个 tick 一轮，约 621 ms）
    //-------------------------------------------------------------------------
    reg [WAIT_BITS-1:0] div = 0;
    wire tick = (div == {WAIT_BITS{1'b1}});
    always @(posedge clk) div <= tick ? {WAIT_BITS{1'b0}} : div + 1'b1;

    //-------------------------------------------------------------------------
    // 被测逻辑：与 eeprom_exercise_top 逐行相同（只有 LED 那一节不同）
    //-------------------------------------------------------------------------
    localparam [1:0] S_LOAD = 2'd0, S_W1 = 2'd1, S_SAVE = 2'd2, S_W2 = 2'd3;
    reg [1:0]  st = S_LOAD;
    reg        load_req = 0, save_req = 0;
    reg [8*BYTES-1:0] cfg_in = 0;
    wire [8*BYTES-1:0] cfg_out;
    wire cfg_ok, busy, err;
    wire scl_lo, sda_lo;

    assign scl = ~scl_lo;
    assign sda = sda_lo ? 1'b0 : 1'bz;

    reg [7:0] pattern = 8'hA0;
    reg       ok_q = 0, err_q = 0;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= S_LOAD; load_req <= 0; save_req <= 0; ok_q <= 0; err_q <= 0;
            pattern <= 8'hA0;
        end else begin
            load_req <= 1'b0;
            save_req <= 1'b0;
            if (cfg_ok) ok_q <= 1'b1;
            if (err)    err_q <= 1'b1;

            case (st)
            S_LOAD: if (tick) begin load_req <= 1'b1; st <= S_W1; end
            S_W1:   if (tick) begin pattern <= pattern + 8'd1; st <= S_SAVE; end
            S_SAVE: if (tick) begin save_req <= 1'b1; st <= S_W2; end
            S_W2:   if (tick) st <= S_LOAD;
            endcase
        end
    end

    // 写入内容：pattern 递增填充（原样）
    integer ci;
    always @(*) begin
        for (ci = 0; ci < BYTES; ci = ci + 1)
            cfg_in[8*ci +: 8] = pattern + ci[7:0];
    end

    cfg_eeprom_store #(
        .CLK_HZ(27_000_000), .SCL_HZ(SCL_HZ), .BYTES(BYTES)
    ) u_ee (
        .clk(clk), .rst_n(rst_n),
        .save_req(save_req), .load_req(load_req),
        .cfg_in(cfg_in), .cfg_out(cfg_out),
        .cfg_ok(cfg_ok), .busy(busy), .err(err),
        .scl_lo(scl_lo), .sda_lo(sda_lo), .sda_in(sda)
    );

    //-------------------------------------------------------------------------
    // 边沿捕获
    //
    // 两级同步：sda 是外部开漏线，异步；scl 虽然由本模块驱动，但为了和 sda
    // 保持同样的 2 拍延迟（否则 SCL/SDA 之间会有 37 ns 的人为偏斜），一起过。
    //-------------------------------------------------------------------------
    reg s1_scl = 1'b1, s2_scl = 1'b1;
    reg s1_sda = 1'b1, s2_sda = 1'b1;
    always @(posedge clk) begin
        s1_scl <= scl;   s2_scl <= s1_scl;
        s1_sda <= sda;   s2_sda <= s1_sda;
    end

    reg [31:0] cap_mem [0:DEPTH-1];
    reg [DEPTH_LOG2-1:0] cap_wr = 0;
    reg        cap_full = 0;
    reg [23:0] tstamp   = 0;
    reg        scl_d    = 1'b1;
    reg        sda_d    = 1'b1;
    reg        cap_clr  = 0;                 // 由回放状态机给的一拍脉冲

    // START：SCL 为高时 SDA 下降。用它把 tstamp 清零，让每个事务从 0 开始。
    wire start_cond = s2_scl && sda_d && !s2_sda;
    wire [23:0] t_now = start_cond ? 24'd0 : tstamp;

    // 看门狗：6 s 没采满也照发，避免"线上根本没有边沿"时永远不动
    reg [27:0] wd = 0;
    wire wd_hit = (wd[27:20] == 8'h9A);      // ≈ 162e6 拍 ≈ 6.0 s

    always @(posedge clk) begin
        if (cap_clr) begin
            cap_wr   <= 0;
            cap_full <= 1'b0;
            tstamp   <= 24'd0;
            scl_d    <= s2_scl;
            sda_d    <= s2_sda;
            wd       <= 28'd0;
        end else begin
            tstamp <= t_now + 24'd1;
            wd     <= wd_hit ? 28'd0 : wd + 28'd1;

            if (!cap_full && (s2_scl != scl_d || s2_sda != sda_d)) begin
                cap_mem[cap_wr] <= {t_now, s2_scl, s2_sda, 6'b000000};
                cap_wr   <= cap_wr + 1'b1;
                if (cap_wr == DEPTH - 1) cap_full <= 1'b1;
            end
            scl_d <= s2_scl;
            sda_d <= s2_sda;
        end
    end

    //-------------------------------------------------------------------------
    // UART 回放
    //-------------------------------------------------------------------------
    reg  [7:0] tx_byte  = 0;
    reg        tx_start = 0;
    wire       tx_busy, tx_done;

    uart_tx #(.CLK_HZ(27_000_000), .BAUD(BAUD)) u_tx (
        .clk(clk), .rst_n(rst_n), .tx_data(tx_byte), .tx_start(tx_start),
        .tx(uart_tx), .busy(tx_busy), .done(tx_done));

    // 十六进制字符
    function [7:0] hexc(input [3:0] v);
        begin
            hexc = (v < 4'd10) ? (8'h30 + {4'd0, v}) : (8'h37 + {4'd0, v});
        end
    endfunction

    localparam [2:0] C_CAP = 3'd0, C_HDR = 3'd1, C_ROW = 3'd2, C_CHAR = 3'd3,
                     C_DONE = 3'd4, C_WAIT = 3'd5;
    localparam [3:0] HDR_LAST = 4'd14;       // 0..14 共 15 个字符
    localparam [3:0] ROW_LAST = 4'd11;       // 0..11 共 12 个字符

    reg [2:0]  cs   = C_CAP;
    reg [DEPTH_LOG2:0] cnt  = 0;             // 本次要发的记录条数（可为 DEPTH）
    reg [DEPTH_LOG2:0] left = 0;
    reg [DEPTH_LOG2-1:0] ri = 0;
    reg [31:0] cur  = 0;
    reg [3:0]  chi  = 0;
    reg [2:0]  settle = 0;
    reg        req  = 0;                     // 已发 tx_start，等 done

    // 表头字符
    wire [15:0] cnt16 = {2'b00, cnt};
    reg  [7:0]  hc;
    always @(*) begin
        case (chi)
        4'd0: hc = "#";  4'd1: hc = "E";  4'd2: hc = "E";  4'd3: hc = "P";
        4'd4: hc = "R";  4'd5: hc = "O";  4'd6: hc = "B";  4'd7: hc = "E";
        4'd8: hc = " ";
        4'd9:  hc = hexc(cnt16[15:12]);
        4'd10: hc = hexc(cnt16[11:8]);
        4'd11: hc = hexc(cnt16[7:4]);
        4'd12: hc = hexc(cnt16[3:0]);
        4'd13: hc = 8'h0D;
        default: hc = 8'h0A;
        endcase
    end

    // 数据行字符：TTTTTT,S,D
    reg [7:0] rc;
    always @(*) begin
        case (chi)
        4'd0: rc = hexc(cur[31:28]);
        4'd1: rc = hexc(cur[27:24]);
        4'd2: rc = hexc(cur[23:20]);
        4'd3: rc = hexc(cur[19:16]);
        4'd4: rc = hexc(cur[15:12]);
        4'd5: rc = hexc(cur[11:8]);
        4'd6: rc = ",";
        4'd7: rc = cur[7] ? "1" : "0";
        4'd8: rc = ",";
        4'd9: rc = cur[6] ? "1" : "0";
        4'd10: rc = 8'h0D;
        default: rc = 8'h0A;
        endcase
    end

    wire [7:0] ch = (cs == C_HDR) ? hc : rc;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cs <= C_CAP; cnt <= 0; left <= 0; ri <= 0; chi <= 0;
            req <= 0; tx_start <= 0; tx_byte <= 0; cap_clr <= 0;
        end else begin
            cap_clr   <= 1'b0;
            tx_start  <= 1'b0;

            case (cs)
            //---- 等采满（或看门狗超时）----
            C_CAP: begin
                if (cap_full || wd_hit) begin
                    cnt  <= cap_full ? DEPTH : {1'b0, cap_wr};
                    left <= cap_full ? DEPTH : {1'b0, cap_wr};
                    ri   <= 0;
                    chi  <= 0;
                    // 一条都没采到就别发了，否则 left 会下溢成死循环
                    cs   <= (cap_full || cap_wr != 0) ? C_HDR : C_DONE;
                end
            end

            //---- 表头 ----
            C_HDR: begin
                if (!req) begin
                    tx_byte  <= ch;
                    tx_start <= 1'b1;
                    req      <= 1'b1;
                end else if (tx_done) begin
                    req <= 1'b0;
                    if (chi == HDR_LAST) begin
                        chi <= 0;
                        cs  <= C_ROW;
                    end else chi <= chi + 1'b1;
                end
            end

            //---- 取一行 ----
            C_ROW: begin
                cur <= cap_mem[ri];
                chi <= 0;
                cs  <= C_CHAR;
            end

            //---- 发一行 ----
            C_CHAR: begin
                if (!req) begin
                    tx_byte  <= ch;
                    tx_start <= 1'b1;
                    req      <= 1'b1;
                end else if (tx_done) begin
                    req <= 1'b0;
                    if (chi == ROW_LAST) begin
                        chi <= 0;
                        if (left == 1) cs <= C_DONE;
                        else begin
                            left <= left - 1'b1;
                            ri   <= ri + 1'b1;
                            cs   <= C_ROW;
                        end
                    end else chi <= chi + 1'b1;
                end
            end

            //---- 清缓冲，等它落定，再重新开始 ----
            C_DONE: begin
                cap_clr <= 1'b1;
                settle  <= 3'd0;
                cs      <= C_WAIT;
                cnt     <= 0;
                left    <= 0;
                ri      <= 0;
                chi     <= 0;
            end

            // cap_full / cap_wr 是 cap_clr 之后一拍才落地，这里多等 4 拍，
            // 否则会拿着"上一轮的 cap_full"立刻又进一次回放。
            C_WAIT: begin
                if (settle == 3'd3) begin
                    settle <= 3'd0;
                    cs     <= C_CAP;
                end else settle <= settle + 1'b1;
            end

            default: cs <= C_CAP;
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // LED（共阳极：0 = 亮）
    //-------------------------------------------------------------------------
    assign led[5] = ~ok_q;      // 读校验曾经通过
    assign led[3] = ~err_q;     // 曾经出现过 err
    assign led[0] = ~cap_full;  // 缓冲已采满
    assign led[4] = 1'b1;
    assign led[2] = 1'b1;
    assign led[1] = 1'b1;

endmodule
