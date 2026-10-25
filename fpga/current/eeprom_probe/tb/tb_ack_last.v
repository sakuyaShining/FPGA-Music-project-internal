//=============================================================================
// tb_ack_last.v -- 直接验证 cfg_eeprom_store 的读事务结尾对不对
//
// 【判据】
//   A. 读 58 字节（BYTES=56 + CRC 2）时，主机必须 ACK 前 57 个、NACK 第 58 个。
//      —— I²C 规矩：最后一个字节回 NACK，从机才知道该交出总线。
//   B. 一次 save + 一次 load 应该看到 2 个 STOP。
//      把 0x003A 预先写成 0x00（模拟"最后一个字节后面那一格不是 0xFF"），
//      若主机没 NACK，从机会继续把 0x003A 的 bit7（=0）按在 SDA 上，
//      STOP 的上升沿就不存在 —— 总线上看到的是"卡死"，不是 STOP。
//
// 【为什么 B 要专门构造】
//   默认的空片里 0x003A 是 0xFF，bit7=1，从机 ACK 之后释放 SDA，
//   STOP 恰好还能成立 —— 也就是说这个 bug 在**默认数据下是隐形的**。
//   B 就是把那个"恰好"拆掉，让隐形的失效显出来。
//
// 【标签为什么用 ASCII】
//   chk() 的 tag 是 task 参数，iverilog 的 %0s 传中文过 task 参数会把多字节
//   字符弄坏（实测 "STOP 次数" 只剩 "ST"）。所以标签一律 ASCII，
//   中文说明写在上面的 $display 里。
//
// 运行：python tools/run_probe_sim.py
//=============================================================================
`timescale 1ns/1ps
module tb_ack_last;
    localparam integer BYTES   = 56;

    // 仿真用 2.7 MHz 而不是 27 MHz：DUT 里 WR_WAIT = CLK_HZ/100 是个 localparam，
    // 时钟降 10 倍，整条事务就降 10 倍（680 ms -> 68 ms），协议与相对时序完全不变。
    // **倍率关系不受影响**，下面判据里没有任何一条依赖绝对时间。
    localparam integer CLK_HZ  = 2_700_000;

    reg clk = 1'b0;
    always #185.185 clk = ~clk;              // 2.7 MHz

    reg  rst_n = 1'b0;
    wire sda, scl;
    wire scl_lo, sda_lo;
    wire cfg_ok, busy, err;
    reg  save_req = 1'b0, load_req = 1'b0;
    reg  [8*BYTES-1:0] cfg_in = 0;
    wire [8*BYTES-1:0] cfg_out;

    pullup(sda);
    assign scl = ~scl_lo;
    assign sda = sda_lo ? 1'b0 : 1'bz;

    cfg_eeprom_store #(.CLK_HZ(CLK_HZ), .SCL_HZ(100_000), .BYTES(BYTES)) dut (
        .clk(clk), .rst_n(rst_n),
        .save_req(save_req), .load_req(load_req),
        .cfg_in(cfg_in), .cfg_out(cfg_out),
        .cfg_ok(cfg_ok), .busy(busy), .err(err),
        .scl_lo(scl_lo), .sda_lo(sda_lo), .sda_in(sda));

    ee24lc256 u_ee(.scl(scl), .sda(sda));

    integer errors = 0;
    integer checks = 0;

    //-------------------------------------------------------------------------
    // 捕获导出：格式与 eeprom_capture_top 的 UART 文本逐字节相同
    //     TTTTTT,S,D\n
    // 时间戳在每个 START 条件（SCL 高时 SDA 下降）清零，和探针一致。
    // 单位是 ns（本 tb 的 timescale），探针里是 27 MHz 拍 —— 解码器按 SCL 周期
    // 自动判别单位，所以两种都能吃。
    //
    // 为什么要导出：让 tools/eeprom_capture_decode.py 能拿**真 RTL 的行为**
    // 做端到端验证，而不是用手搓的假数据自我满足。
    //-------------------------------------------------------------------------
    integer    fd     = 0;
    reg        cap_en = 0;
    reg [63:0] cap_t0 = 0;
    reg [23:0] cap_tt = 0;          // 必须正好 24 位，否则 %06x 会印出 16 个 0
    reg        cap_sda_p = 1'b1;

    always @(scl or sda) begin
        if (cap_en && fd != 0) begin
            if (scl === 1'b1 && cap_sda_p === 1'b1 && sda === 1'b0) cap_t0 = $time;
            cap_tt = ($time - cap_t0);
            $fwrite(fd, "%06x,%0d,%0d\n", cap_tt,
                    (scl === 1'b1) ? 1 : 0,
                    (sda === 1'b1) ? 1 : 0);
        end
        cap_sda_p = sda;
    end

    task cap_open_a;
        begin
            fd = $fopen("sim_capture_A.txt", "w");
            cap_t0 = $time; cap_sda_p = sda; cap_en = 1'b1;
        end
    endtask

    task cap_open_b;
        begin
            fd = $fopen("sim_capture_B.txt", "w");
            cap_t0 = $time; cap_sda_p = sda; cap_en = 1'b1;
        end
    endtask

    task cap_close;
        begin
            cap_en = 1'b0;
            if (fd != 0) $fclose(fd);
            fd = 0;
        end
    endtask

    task chk(input [63:0] tag, input integer got, input integer want);
        begin
            checks = checks + 1;
            if (got !== want) begin
                $display("      [FAIL] %0s = %0d，期望 %0d", tag, got, want);
                errors = errors + 1;
            end else
                $display("      %0s = %0d  OK", tag, got);
        end
    endtask

    task wait_busy(input [63:0] tag);
        reg [63:0] t0;
        integer g;
        begin
            g = 0;
            while (!busy && g < 20000) begin @(posedge clk); g = g + 1; end
            if (!busy) begin
                $display("      [FAIL] %0s busy 一直没起来（状态机没启动）", tag);
                errors = errors + 1;
            end else begin
                t0 = $time;
                wait (!busy);
                $display("      %0s 事务耗时 %0.3f ms", tag, ($time - t0) / 1000000.0);
                // 这条**不计入** A/B 判据，它记的是另一件事：
                // WR_WAIT = CLK_HZ/100 是 q 拍，不是时钟拍，实际等待 = 10 ms x DIV。
                // 本仿真把 CLK 降了 10 倍，DIV 也从 68 变成 7，倍率被压缩到 ~7；
                // 27 MHz 真机上是 68 倍（680 ms）。这里只把测量值打出来供报告引用。
                if (($time - t0) > 64'd30_000_000)
                    $display("      [NOTE] %0s 耗时远超设计意图（~16 ms）：WR_WAIT 是 q 拍不是时钟拍", tag);
            end
        end
    endtask

    task do_save(input [8*BYTES-1:0] data);
        begin
            cfg_in = data;
            @(posedge clk); save_req <= 1'b1;
            @(posedge clk); save_req <= 1'b0;
            wait_busy("save");
        end
    endtask

    task do_load;
        begin
            @(posedge clk); load_req <= 1'b1;
            @(posedge clk); load_req <= 1'b0;
            wait_busy("load");
        end
    endtask

    task hard_reset;
        begin
            rst_n = 1'b0;
            repeat (200) @(posedge clk);
            rst_n = 1'b1;
            repeat (50)  @(posedge clk);
            u_ee.clear_stats;
            cfg_in = 0;
        end
    endtask

    //-------------------------------------------------------------------------
    // A：默认空片（0x003A = 0xFF）—— 检查 ACK/NACK 分布
    //-------------------------------------------------------------------------
    task test_a;
        begin
            $display("");
            $display("  A 读事务结尾：58 个读字节里，前 57 个 ACK、第 58 个必须 NACK");
            $display("     rd_bytes=读字节数 ACK/NACK=主机应答 lastNACK=末字节 STOP=停止位");
            u_ee.init_ff;
            hard_reset;
            cap_open_a;
            do_save(56'h0);
            do_load;
            cap_close;

            chk("rd_bytes", u_ee.n_read_bytes, 58);
            chk("ACK     ", u_ee.n_ack,  57);
            chk("NACK    ", u_ee.n_nack,  1);
            chk("lastNACK", u_ee.last_nack, 1);
            chk("STOP    ", u_ee.n_stop,  2);
            chk("cfg_ok  ", cfg_ok,       1);
        end
    endtask

    //-------------------------------------------------------------------------
    // B：把 0x003A 写成 0x00 —— 没 NACK 就会把总线按住，STOP 消失
    //-------------------------------------------------------------------------
    task test_b;
        begin
            $display("");
            $display("  B 最后一个字节后面那一格 = 0x00：没 NACK 就没有 STOP");
            u_ee.init_ff;
            u_ee.mem[16'h003A] = 8'h00;
            hard_reset;
            cap_open_b;
            do_save(56'h0);
            do_load;
            cap_close;

            chk("STOP    ", u_ee.n_stop, 2);
        end
    endtask

    initial begin
        $display("=============================================================");
        $display(" cfg_eeprom_store 读事务结尾判定");
        $display("=============================================================");
        test_a;
        test_b;
        $display("");
        $display("-------------------------------------------------------------");
        $display(" 判据 %0d 项，失败 %0d 项", checks, errors);
        if (errors == 0)
            $display(" PASS —— 读事务结尾符合 I2C 规范（最后一个字节回 NACK）");
        else begin
            $display(" FAIL —— 读事务结尾不符合 I2C 规范");
            $display("        主机对最后一个读字节回了 ACK。24LC256 收到 ACK 会继续");
            $display("        把下一字节送到 SDA 上；只要那个字节的 bit7 是 0，STOP");
            $display("        的上升沿就不存在，总线当场卡住（A 的默认数据恰好是 0xFF，");
            $display("        所以平时看不见 —— B 就是把这个巧合拆掉）。");
        end
        $display("-------------------------------------------------------------");
        $finish;
    end

    initial begin
        #1_500_000_000;                       // 1.5 s
        $display("      [FAIL] 仿真超时（1.5 s）");
        $finish;
    end

endmodule
