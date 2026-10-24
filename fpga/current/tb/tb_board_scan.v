//=============================================================================
// tb_board_scan.v —— 载板扫描前端验证
//
// 覆盖三件事，每一件都是"写错了仿真也未必看得出"的那类：
//
//  A. scan_shift165 的位序
//     74HC165 装载后 QH 立即 = H(bit7)，是 MSB first。若按 LSB first 拼字节，
//     读回的按键整体位序颠倒 —— 而如果激励也按同样错误顺序给，仿真照样通过。
//     所以这里用**独立的 74HC165 行为模型**（左移 + QH=sr[7]）产生波形，
//     再比对读回值是否等于模型输入，位序错了必然暴露。
//
//  B. scan_bus_arbiter 的"持有到释放"
//     `scan_shift595` 在 state>=LOW 时若丢 grant 就置 grant_error。
//     所以要验证：请求者 B 在 A 持有期间提出请求，A 的 grant 不能被抢走。
//
//  C. sensor_frontend_board 的整体连通
//     确认 595 侧能产出 row_valid、165 侧能读回按键、两条 SCK 没有互相打架。
//=============================================================================

`timescale 1ns/1ps

//-----------------------------------------------------------------------------
// 74HC165 行为模型
//   内部 8 级移位链 A→B→...→H→QH，QH 是最后一级。
//   装载（PL 低）：A..H 并行进链，QH 立即 = H = d[7]
//   移位（CP 上升沿）：H←G, G←F, ..., B←A，即 sr <= {sr[6:0], serial_in}
//   因此是 MSB first。
//-----------------------------------------------------------------------------
module hc165_model(
    input  wire       pl_n,
    input  wire       cp,
    input  wire [7:0] d,
    output wire       qh
);
    reg [7:0] sr;
    initial sr = 8'h00;

    // 装载是异步的：PL 一拉低，QH 立刻反映 H
    always @(pl_n or d)
        if (!pl_n) sr = d;

    // 只在 PL 为高时移位
    always @(posedge cp)
        if (pl_n) sr <= {sr[6:0], 1'b0};

    assign qh = sr[7];
endmodule


module tb_board_scan;

    reg clk = 0;
    always #10 clk = ~clk;          // 50 MHz，只为缩短仿真时间
    reg rst_n = 0;

    integer errors = 0;

    task fail(input [255:0] msg);
        begin
            $display("  [FAIL] %0s", msg);
            errors = errors + 1;
        end
    endtask

    //=========================================================================
    // A. scan_shift165 位序验证
    //=========================================================================
    reg         pl_n_a;
    wire        sck_a;    // 直接是 scan_shift165 的输出、同时喂给 165 模型，必须是 wire
                          // （写成 reg 只有 -g2012 能过，-g2005 会报"不能由连续赋值驱动"）
    wire        qh_a;
    reg  [7:0]  key_pat;
    wire        qh_unused;

    hc165_model u_model(
        .pl_n (pl_n_a),
        .cp   (sck_a),
        .d    (key_pat),
        .qh   (qh_a)
    );

    reg         start_a;
    reg         gnt_a;
    wire        ready_a, req_a, load_a, dv_a, ge_a;
    wire [7:0]  data_a;

    scan_shift165 #(.HALF_PERIOD(4), .WIDTH(8), .MSB_FIRST(1)) u_165 (
        .clk         (clk),
        .rst_n       (rst_n),
        .start       (start_a),
        .ready       (ready_a),
        .bus_request (req_a),
        .bus_grant   (gnt_a),
        .sck         (sck_a),
        .load_n      (load_a),
        .serial_in   (qh_a),
        .data        (data_a),
        .data_valid  (dv_a),
        .grant_error (ge_a)
    );

    // load_n 直接驱动模型
    always @(*) pl_n_a = load_a;

    //=========================================================================
    // B. 仲裁器
    //=========================================================================
    reg  [1:0] areq;
    wire [1:0] agrant;

    scan_bus_arbiter #(.REQ(2)) u_arb (
        .clk     (clk),
        .rst_n   (rst_n),
        .request (areq),
        .grant   (agrant)
    );

    //=========================================================================
    // C. 前端整体
    //=========================================================================
    reg  [5:0] sense_n;
    wire       f_sck, f_mosi, f_latch, f_load, f_return;
    wire       f_row_valid, f_frame_tick;
    wire [3:0] f_row_addr;
    wire [71:0] f_row_count;
    wire [5:0]  f_row_fault;
    wire [31:0] f_row_seq;
    wire [7:0]  f_keys;
    wire        f_keys_valid;
    wire        f_ge_scan, f_ge_key;

    reg         f_row_ready;

    sensor_frontend_board #(
        .LANES(6), .CW(12),
        .DISCHARGE_CYCLES(16),      // 缩短，只为仿真
        .TIMEOUT_CYCLES(200),
        .SPI_HALF_PERIOD(2),
        .KEY_PERIOD(3000)
    ) u_front (
        .clk              (clk),
        .rst_n            (rst_n),
        .calibrate        (1'b0),
        .sense_n          (sense_n),
        .bus_sck          (f_sck),
        .bus_mosi         (f_mosi),
        .scan_latch       (f_latch),
        .input_load_n     (f_load),
        .bus_return       (f_return),
        .row_valid        (f_row_valid),
        .row_ready        (f_row_ready),
        .row_address      (f_row_addr),
        .row_count        (f_row_count),
        .row_fault        (f_row_fault),
        .row_sequence     (f_row_seq),
        .frame_tick       (f_frame_tick),
        .keys             (f_keys),
        .keys_valid       (f_keys_valid),
        .scan_grant_error (f_ge_scan),
        .key_grant_error  (f_ge_key)
    );

    // 前端总线回读：接一个 165 模型，让 BUS_RETURN 有真实波形
    hc165_model u_fmodel(
        .pl_n (f_load),
        .cp   (f_sck),
        .d    (8'h2D),    // 非位回文：反转后是 0xB4
        .qh   (f_return)
    );

    //=========================================================================
    // 主流程
    //=========================================================================
    integer cyc, rows_seen, keys_seen;

    initial begin
        start_a     = 0;
        gnt_a       = 0;
        areq        = 2'b00;
        key_pat     = 8'h01;        // 非位回文：反转后是 0x80，位序错必暴露
        sense_n     = 6'b000000;
        f_row_ready = 1;

        $display("=== tb_board_scan ===");

        repeat (4) @(posedge clk);
        rst_n = 1;
        repeat (2) @(posedge clk);

        //---------------------------------------------------------------
        // A. 165 位序
        //---------------------------------------------------------------
        $display("[A] scan_shift165 MSB-first 位序");
        @(posedge clk);
        start_a = 1;
        @(posedge clk);
        start_a = 0;
        gnt_a   = 1;

        cyc = 0;
        while (!dv_a && cyc < 500) begin
            @(posedge clk);
            cyc = cyc + 1;
        end

        if (!dv_a) begin
            fail("165 未在 500 周期内产出 data_valid");
        end else if (data_a !== key_pat) begin
            $display("  [FAIL] 位序错误: 读回 0x%02h，模型输入 0x%02h",
                     data_a, key_pat);
            errors = errors + 1;
        end else begin
            $display("  [PASS] 读回 0x%02h == 模型 0x%02h（%0d 周期）",
                     data_a, key_pat, cyc);
        end

        if (ge_a) begin
            fail("165 报告 grant_error");
        end

        // 再测一个反相模式，防止"恒等于某值"的巧合
        key_pat = 8'h9B;   // 非位回文：反转后是 0xD9
        @(posedge clk);
        start_a = 1;
        @(posedge clk);
        start_a = 0;
        cyc = 0;
        while (!dv_a && cyc < 500) begin
            @(posedge clk);
            cyc = cyc + 1;
        end
        if (data_a !== key_pat) begin
            $display("  [FAIL] 第二次位序错误: 读回 0x%02h，期望 0x%02h",
                     data_a, key_pat);
            errors = errors + 1;
        end else begin
            $display("  [PASS] 第二次 0x%02h 正确", data_a);
        end

        gnt_a = 0;

        //---------------------------------------------------------------
        // B. 仲裁：不抢占
        //---------------------------------------------------------------
        $display("[B] scan_bus_arbiter 持有到释放");
        areq = 2'b01;
        repeat (2) @(posedge clk);
        if (agrant !== 2'b01) begin
            $display("  [FAIL] 单请求未授权: grant=%b", agrant);
            errors = errors + 1;
        end else $display("  [PASS] req=01 -> grant=01");

        // 请求者 1 在 0 持有期间插队，grant 不能被抢
        areq = 2'b11;
        repeat (3) @(posedge clk);
        if (agrant !== 2'b01) begin
            $display("  [FAIL] 高优先级插队抢走了持有者: grant=%b", agrant);
            errors = errors + 1;
        end else $display("  [PASS] req=11 期间 grant 仍为 01（不抢占）");

        // 释放
        areq = 2'b10;
        repeat (2) @(posedge clk);
        if (agrant !== 2'b10) begin
            $display("  [FAIL] 释放后未轮到请求者1: grant=%b", agrant);
            errors = errors + 1;
        end else $display("  [PASS] req=10 -> grant=10");

        areq = 2'b00;
        repeat (2) @(posedge clk);
        if (agrant !== 2'b00) begin
            $display("  [FAIL] 无请求时 grant 未归零: %b", agrant);
            errors = errors + 1;
        end else $display("  [PASS] 无请求 -> grant=00");

        //---------------------------------------------------------------
        // C. 前端整体
        //---------------------------------------------------------------
        $display("[C] sensor_frontend_board 整体连通");
        rows_seen = 0;
        keys_seen = 0;

        fork
            begin : watch
                integer n;
                for (n = 0; n < 60000; n = n + 1) begin
                    @(posedge clk);
                    if (f_row_valid) rows_seen = rows_seen + 1;
                    if (f_keys_valid) begin
                        keys_seen = keys_seen + 1;
                        if (f_keys !== 8'h2D) begin
                            $display("  [FAIL] 前端读键 0x%02h != 0x2D", f_keys);
                            errors = errors + 1;
                        end
                    end
                end
            end
            begin : ready_drive
                integer n;
                for (n = 0; n < 60000; n = n + 1) begin
                    @(posedge clk);
                    f_row_ready = 1;
                end
            end
        join

        if (rows_seen == 0) begin
            fail("前端 60000 周期内没有产出 row_valid");
        end else begin
            $display("  [PASS] row_valid 出现 %0d 次，帧序号 %0d",
                     rows_seen, f_row_seq);
        end

        if (keys_seen == 0) begin
            fail("前端 60000 周期内没有产出 keys_valid");
        end else begin
            $display("  [PASS] keys_valid 出现 %0d 次", keys_seen);
        end

        if (f_ge_scan) fail("扫描侧 grant_error 被置起");
        if (f_ge_key)  fail("按键侧 grant_error 被置起");

        //---------------------------------------------------------------
        $display("=== 结果: %0d 个失败 ===", errors);
        if (errors == 0) $display("ALL PASS");
        $finish;
    end

    // 超时保护
    initial begin
        #5000000;
        $display("TIMEOUT");
        $finish;
    end

endmodule
