//=============================================================================
// cfg_eeprom_store.v -- 24C256 I2C EEPROM 配置存取层（字节级引擎）
//
// 为什么需要
//   冻结基线要求"断电保留"。当前产品掉电即丢：音色库与参数全在寄存器里，
//   没有非易失载体。本模块补上这块。
//
// 为什么不复用 i2c_master.v
//   那个模块单次事务上限 4 字节（reg_a + wr_d[15:0] + wr_n），
//   而 24C256 一页写要 "2 字节地址 + N 字节数据"。这里需要任意长度事务。
//
// 设计
//   · 字节级引擎：先把整个事务的发送字节装进 tx_mem，再逐位发出；
//     需要回读时再逐位接收。位时序四相：准备 / SCL 高 / 采样 / SCL 低。
//   · 开漏语义：scl_lo / sda_lo 为 1 表示拉低；sda_in 为线上电平。
//   · 事务：save = [0x50|0][hi][lo][data...]；load = [0x50|0][hi][lo][0x50|1] + 读 N 字节。
//   · 写完等待 WR_CYCLE 个时钟（24C256 规格 5 ms，默认给 10 ms）。
//
// 单元测试见 tb/tb_cfg_eeprom.v（含行为级 24C256 模型）。
//=============================================================================
module cfg_eeprom_store #(
    parameter integer CLK_HZ   = 27_000_000,
    parameter integer SCL_HZ   = 100_000,
    parameter integer DEV_ADDR = 7'h50,
    parameter integer BYTES    = 56
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        save_req,
    input  wire        load_req,
    input  wire [8*BYTES-1:0] cfg_in,
    output reg  [8*BYTES-1:0] cfg_out,
    output reg         cfg_ok,
    output reg         busy,
    output reg         err,

    output reg         scl_lo,
    output reg         sda_lo,
    input  wire        sda_in
);
    // 每个 bit 由 4 个 q tick 组成 ⇒ q tick = CLK/(SCL*4)，四舍五入
    localparam integer DIV = (CLK_HZ + SCL_HZ * 2) / (SCL_HZ * 4);

    // M5：24C256 页大小 64 字节。一次写事务 = 3 字节(设备+地址) + BYTES 数据 + 2 字节 CRC，
    //     超过 64 就会跨页回卷，把本页开头覆盖掉。当前 BYTES=56 ⇒ 61，安全。
    //     改大 BYTES 前先看这条断言。
    localparam integer PAGE_OK = ((BYTES + 5) <= 64) ? 1 : 0;
    // synthesis translate_off
    initial begin
        if (!PAGE_OK) begin
            $display("cfg_eeprom_store: BYTES=%0d 会跨 64 字节页边界（%0d > 64）", BYTES, BYTES + 5);
            $finish;
        end
    end
    // synthesis translate_on
    localparam integer WR_WAIT = CLK_HZ / 100;           // 10 ms

    reg [15:0] tick;
    wire q = (tick >= DIV[15:0] - 1);
    always @(posedge clk or negedge rst_n)
        if (!rst_n) tick <= 16'd0;
        else        tick <= q ? 16'd0 : tick + 16'd1;

    // M3：sda_in 是异步信号，两级打拍后再用。直接采样有亚稳态风险，
    //     且在 SCL 沿附近可能采到跳变中的值。
    reg sda_s1, sda_s2;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin sda_s1 <= 1'b1; sda_s2 <= 1'b1; end
        else        begin sda_s1 <= sda_in; sda_s2 <= sda_s1; end
    wire sda_q = sda_s2;

    // ---- 事务缓冲 -----------------------------------------------------------
    reg [7:0] tx_mem [0:BYTES+8];
    reg [7:0] rx_mem [0:BYTES+1];   // +2 存 CRC
    reg [7:0] tx_len, tx_idx, rx_len, rx_idx;
    reg [7:0] tx_byte, rx_byte;
    reg [15:0] calc_crc;      // CRC16-CCITT，poly 0x1021，初值 0xFFFF
    reg [7:0]  stage_i;       // STAGE 阶段的字节下标
    reg [3:0]  rec_cnt;       // 总线恢复：已发出的时钟数（最多 9 个）

    wire [7:0]  stage_byte = cfg_in[8*stage_i +: 8];
    wire [15:0] crc_next   = crc_byte(calc_crc, stage_byte);

    // 与 uart_cfg_transport 相同的 CRC（上位机可以用同一份实现核对）
    function [15:0] crc_byte;
        input [15:0] c_in;
        input [7:0]  d;
        integer i;
        reg [15:0] c;
        begin
            c = c_in ^ {d, 8'd0};
            for (i = 0; i < 8; i = i + 1)
                c = c[15] ? ((c << 1) ^ 16'h1021) : (c << 1);
            crc_byte = c;
        end
    endfunction

    // ---- 状态 ---------------------------------------------------------------
    localparam [3:0] IDLE=0, LOADTX=1, START=2, TXBIT=3, TXACK=4,
                     RXBIT=5, RXACK=6, STOP=7, WAIT=8, FINISH=9, RSTART=10, STAGE=11, RECOVER=12;
    reg [3:0] st;
    reg [1:0] ph;          // 位内四相
    reg [2:0] bc;          // 位序 7..0
    reg [1:0] mode;        // 0=save 1=load
    reg [31:0] wcnt;      // 32 位：WR_WAIT 是 270000，16 位会截断成 7856（实测只等 291us）
    reg save_d, load_d;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin save_d <= 0; load_d <= 0; end
        else        begin save_d <= save_req; load_d <= load_req; end
    wire save_go = save_req & ~save_d;
    wire load_go = load_req & ~load_d;

    // 请求锁存：save_go / load_go 只维持半个时钟，而状态机在 q 节拍采样，
    // 直接用边沿做触发会漏脉冲（实测现象：SAVE 成功、LOAD 永不启动）。
    reg save_pend, load_pend;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) begin save_pend <= 1'b0; load_pend <= 1'b0; end
        else begin
            if (save_go) save_pend <= 1'b1;
            if (load_go) load_pend <= 1'b1;
            if (st == START) begin save_pend <= 1'b0; load_pend <= 1'b0; end
            // 恢复流程走完：无论总线是否已放开，都放弃这次请求。
            // 仍然卡死时由 FINISH 置 err 上报，让上层决定是否重试；
            // 不能在这里自动重试——那会形成无限循环，把总线一直占着。
            if (st == FINISH && mode == 2'd2) begin save_pend <= 1'b0; load_pend <= 1'b0; end
        end

    // 副本地址：A=0x0000 B=0x0040，A/B 交替写
    reg        copy_a;
    reg        last_copy;   // 最近一次写入用的是哪个副本（load 要读它）
    wire [15:0] wr_base = copy_a ? 16'h0040 : 16'h0000;

    integer k;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= IDLE; ph <= 2'd0; bc <= 3'd7; mode <= 2'd0;
            tx_len <= 8'd0; tx_idx <= 8'd0; rx_len <= 8'd0; rx_idx <= 8'd0;
            busy <= 1'b0; err <= 1'b0; cfg_ok <= 1'b0; cfg_out <= 0;
            scl_lo <= 1'b0; sda_lo <= 1'b0; wcnt <= 32'd0; copy_a <= 1'b0; last_copy <= 1'b0;
        end else if (q) begin
            case (st)
            IDLE: begin
                scl_lo <= 1'b0; sda_lo <= 1'b0; busy <= 1'b0;
                // err 不在这里清：恢复失败后置的 err 要保持到下次事务开始，
                // 否则上层读到的永远是 0。
                cfg_ok <= 1'b0; wcnt <= 32'd0;
                if ((save_pend || load_pend) && (sda_q == 1'b0)) begin
                    // M4 总线恢复：SDA 被从机拉低说明它卡在某个字节中间。
                    // 直接发起 START 会得到一个残缺事务，先发 9 个时钟把它顶出来。
                    mode    <= 2'd2;          // 2 = 恢复（FINISH 里只上报，不输出数据）
                    err     <= 1'b0;
                    rec_cnt <= 4'd0;
                    ph      <= 2'd0;
                    st      <= RECOVER;
                end else if (save_pend || load_pend) begin
                    busy <= 1'b1;
                    err  <= 1'b0;
                    tx_idx <= 8'd0; rx_idx <= 8'd0; bc <= 3'd7; ph <= 2'd0;
                    if (save_pend) begin
                        mode <= 2'd0;
                        tx_mem[0] <= {DEV_ADDR, 1'b0};
                        tx_mem[1] <= wr_base[15:8];
                        tx_mem[2] <= wr_base[7:0];
                        calc_crc <= 16'hFFFF;
                        stage_i  <= 8'd0;
                        rx_len   <= 8'd0;
                        last_copy <= copy_a;   // 记下这次写的是哪一份
                        copy_a   <= ~copy_a;
                        st <= STAGE;           // 逐字节填充 + 算 CRC
                    end else begin
                        mode <= 2'd1;
                        tx_mem[0] <= {DEV_ADDR, 1'b0};
                        tx_mem[1] <= (last_copy ? 16'h0040 : 16'h0000) >> 8;
                        tx_mem[2] <= (last_copy ? 16'h0040 : 16'h0000) & 8'hFF;
                        tx_mem[3] <= {DEV_ADDR, 1'b1};
                        tx_len <= 8'd4;
                        rx_len <= BYTES[7:0] + 8'd2;   // 数据 + CRC
                        calc_crc <= 16'hFFFF;
                        st <= START;
                    end
                end
            end

            RECOVER: begin
                case (ph)
                2'd0: begin scl_lo <= 1'b1; sda_lo <= 1'b0; ph <= 2'd1; end   // SCL 低，SDA 释放
                2'd1: begin scl_lo <= 1'b0; ph <= 2'd2; end                  // SCL 高
                2'd2: begin ph <= 2'd3; end
                default: begin
                            scl_lo  <= 1'b1;
                            ph      <= 2'd0;
                            rec_cnt <= rec_cnt + 4'd1;
                            // 发满 9 个时钟，或从机已放开 SDA —— 两种都可以收尾
                            if (rec_cnt == 4'd8 || sda_q) begin
                                busy <= 1'b1;
                                ph   <= 2'd0;
                                st   <= STOP;      // 用标准 STOP 收尾，把总线交回空闲
                            end
                        end
                endcase
            end

            STAGE: begin
                // 每拍填一个字节并推进 CRC（BYTES 拍后把 CRC 两字节也放进事务）
                tx_mem[3 + stage_i] <= stage_byte;
                calc_crc <= crc_next;
                if (stage_i == BYTES[7:0] - 8'd1) begin
                    tx_mem[3 + BYTES]     <= crc_next[7:0];
                    tx_mem[3 + BYTES + 1] <= crc_next[15:8];
                    tx_len <= BYTES[7:0] + 8'd5;
                    st <= START;
                end else begin
                    stage_i <= stage_i + 8'd1;
                end
            end

            START: begin
                case (ph)
                2'd0: begin sda_lo <= 1'b1; ph <= 2'd1; end          // SDA 拉低（SCL 仍高）⇒ START
                2'd1: begin scl_lo <= 1'b1; ph <= 2'd2; end          // SCL 拉低，占用总线
                default: begin ph <= 2'd0; tx_byte <= tx_mem[0]; st <= TXBIT; end
                endcase
            end

            TXBIT: begin
                case (ph)
                2'd0: begin sda_lo <= ~tx_byte[bc]; ph <= 2'd1; end   // SCL 低时建立数据
                2'd1: begin scl_lo <= 1'b0; ph <= 2'd2; end           // SCL 抬为高
                2'd2: begin ph <= 2'd3; end
                default: begin scl_lo <= 1'b1; ph <= 2'd0;
                             if (bc == 3'd0) st <= TXACK; else bc <= bc - 3'd1; end
                endcase
            end

            TXACK: begin
                case (ph)
                2'd0: begin sda_lo <= 1'b0; ph <= 2'd1; end           // 释放 SDA（0=不驱动）给从机应答
                2'd1: begin scl_lo <= 1'b0; ph <= 2'd2; end
                2'd2: begin if (sda_q) err <= 1'b1; ph <= 2'd3; end   // 高 = NACK
                default: begin scl_lo <= 1'b1; ph <= 2'd0; bc <= 3'd7;
                             tx_idx <= tx_idx + 8'd1;
                             if (tx_idx + 8'd1 == 8'd3 && rx_len != 8'd0)
                                 st <= RSTART;                 // 地址发完，重发起始位再读
                             else if (tx_idx + 8'd1 >= tx_len)
                                 st <= (rx_len == 8'd0) ? STOP : RXBIT;
                             else begin tx_byte <= tx_mem[tx_idx + 8'd1]; st <= TXBIT; end
                         end
                endcase
            end

            // 重复起始位：SCL 高时 SDA 先放高再拉低
            RSTART: begin
                case (ph)
                2'd0: begin scl_lo <= 1'b1; sda_lo <= 1'b0; ph <= 2'd1; end   // SCL 低，SDA 放高
                2'd1: begin scl_lo <= 1'b0; ph <= 2'd2; end                  // SCL 高
                2'd2: begin sda_lo <= 1'b1; ph <= 2'd3; end                  // SDA 低 ⇒ 重复 START
                default: begin scl_lo <= 1'b1; ph <= 2'd0; bc <= 3'd7;
                             tx_byte <= tx_mem[3]; st <= TXBIT; end
                endcase
            end

            RXBIT: begin
                case (ph)
                2'd0: begin sda_lo <= 1'b0; ph <= 2'd1; end           // 释放 SDA（0=不驱动）
                2'd1: begin scl_lo <= 1'b0; ph <= 2'd2; end
                2'd2: begin rx_byte[bc] <= sda_q; ph <= 2'd3; end
                default: begin scl_lo <= 1'b1; ph <= 2'd0;
                             if (bc == 3'd0) st <= RXACK; else bc <= bc - 3'd1; end
                endcase
            end

            RXACK: begin
                case (ph)
                2'd0: begin sda_lo <= 1'b1; ph <= 2'd1; end           // 主机 ACK：拉低 SDA
                2'd1: begin scl_lo <= 1'b0; ph <= 2'd2; end
                2'd2: begin ph <= 2'd3; end
                default: begin scl_lo <= 1'b1; ph <= 2'd0; bc <= 3'd7;
                             rx_mem[rx_idx] <= rx_byte;
                             if (rx_idx < BYTES[7:0])
                                 calc_crc <= crc_byte(calc_crc, rx_byte);
                             rx_idx <= rx_idx + 8'd1;
                             if (rx_idx + 8'd1 >= rx_len) st <= STOP;
                             else st <= RXBIT;
                         end
                endcase
            end

            STOP: begin
                case (ph)
                2'd0: begin scl_lo <= 1'b1; sda_lo <= 1'b1; ph <= 2'd1; end   // SCL 低、SDA 低
                2'd1: begin scl_lo <= 1'b0; ph <= 2'd2; end                  // SCL 高
                2'd2: begin sda_lo <= 1'b0; ph <= 2'd3; end                  // SDA 升 ⇒ STOP
                default: begin ph <= 2'd0; wcnt <= 32'd0; st <= WAIT; end
                endcase
            end

            WAIT: begin
                wcnt <= wcnt + 16'd1;
                if (wcnt >= WR_WAIT) st <= FINISH;
            end

            FINISH: begin
                if (mode == 2'd2) begin
                    // 恢复结束：SDA 仍然是低 ⇒ 从机没放开，报错给上层
                    err <= (sda_q == 1'b0);
                end
                if (mode == 2'd1) begin
                    cfg_out <= {BYTES{8'h00}};
                    for (k = 0; k < BYTES; k = k + 1)
                        cfg_out[8*k +: 8] <= rx_mem[k];
                    // 只有 CRC 相符才认这份配置是好的；不符时 cfg_ok=0，
                    // 上层必须据此丢弃，不能假设"读回来就是对的"。
                    cfg_ok <= (calc_crc == {rx_mem[BYTES+1], rx_mem[BYTES]});
                end
                busy <= 1'b0;
                scl_lo <= 1'b0; sda_lo <= 1'b0;
                st <= IDLE;
                ph <= 2'd0;
            end

            default: st <= IDLE;
            endcase
        end
    end
endmodule
