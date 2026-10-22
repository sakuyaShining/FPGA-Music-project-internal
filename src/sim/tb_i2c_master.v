//=============================================================================
// tb_i2c_master.v —— I2C 主机 + MPR121 模型 的自检测试台
//
// 用例：
//   1) 写寄存器后读回，值应一致
//   2) 读触摸状态 2 字节，应与 touch 输入一致
//   3) 对不存在的从机地址访问，应置 err
// 判定：逐条打印 PASS / FAIL，末尾给出汇总；挂死由看门狗兜底。
//=============================================================================
`timescale 1ns/1ps

module tb_i2c_master;

    // ---------------- 时钟与复位 ----------------
    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #10 clk = ~clk;                  // 50 MHz（仿真用；真实为 27 MHz）

    integer errors = 0;
    integer i;

    // ---------------- 总线（开漏 + 上拉） ----------------
    wire sda;
    wire scl;
    pullup(sda);
    pullup(scl);

    // ---------------- 主机 ----------------
    reg        req = 1'b0;
    reg        rd = 1'b0;
    reg [6:0]  dev = 7'h5A;
    reg [7:0]  reg_a = 8'h00;
    reg [15:0] wr_d = 16'h0000;
    reg [1:0]  wr_n = 2'd0;
    reg [2:0]  rd_n = 3'd1;

    wire [31:0] rd_d;
    wire        busy, done, err;
    wire        scl_lo_m, sda_lo_m;

    assign scl = scl_lo_m ? 1'b0 : 1'bz;
    assign sda = sda_lo_m ? 1'b0 : 1'bz;

    i2c_master #(.CLK_HZ(50000000), .SCL_HZ(1000000)) u_m (
        .clk(clk), .rst_n(rst_n),
        .req(req), .dev(dev), .rd(rd), .reg_a(reg_a),
        .wr_d(wr_d), .wr_n(wr_n), .rd_n(rd_n),
        .rd_d(rd_d), .busy(busy), .done(done), .err(err),
        .scl_lo(scl_lo_m), .sda_lo(sda_lo_m),
        .sda_in(sda), .scl_in(scl)
    );

    // ---------------- 从机模型 ----------------
    reg [11:0] touch = 12'h000;

    mpr121_model #(.ADDR(7'h5A), .PROBE(0)) u_s (
        .clk(clk), .rst_n(rst_n), .sda(sda), .scl(scl), .touch(touch)
    );

    // ---------------- 一次传输 ----------------
    task do_xfer;
        input        r;
        input [6:0]  d;
        input [7:0]  ra;
        input [15:0] wd;
        input [1:0]  wn;
        input [2:0]  rn;
        integer      guard;
        begin
            dev = d; rd = r; reg_a = ra; wr_d = wd; wr_n = wn; rd_n = rn;
            @(posedge clk);
            req <= 1'b0;
            @(negedge clk); req <= 1'b1;
            @(negedge clk); req <= 1'b0;
            guard = 0;
            while (!done && guard < 400000) begin
                @(posedge clk);
                guard = guard + 1;
            end
            if (guard >= 400000) begin
                $display("  [超时] 传输未在限定周期内完成");
                errors = errors + 1;
            end
            @(posedge clk);
        end
    endtask

    task check;
        input [127:0] name;
        input [31:0]  got;
        input [31:0]  exp;
        begin
            if (got === exp) $display("  PASS  %0s  得到 0x%08h", name, got);
            else begin
                $display("  FAIL  %0s  得到 0x%08h 期望 0x%08h", name, got, exp);
                errors = errors + 1;
            end
        end
    endtask


    // ---------------- 临时：总线边沿跟踪 ----------------
    reg scl_p = 1'b1, sda_p = 1'b1;
    integer trace_n = 0;
    always @(posedge clk) begin
        scl_p <= scl; sda_p <= sda;
        if ($test$plusargs("trace") && (scl !== scl_p || sda !== sda_p) && trace_n < 200) begin
            trace_n = trace_n + 1;
            $display("   t=%0t scl=%b sda=%b | st=%0d seq=%0d bitc=%0d q=%0d busy=%b err=%b mst=%0d sbc=%0d sdr=%b",
                     $time, scl, sda, u_m.st, u_m.seq, u_m.bitc, u_m.q, busy, err, u_s.st, u_s.bitc, u_s.sda_drive_lo);
        end
    end


    // ---------------- RX 采样跟踪（定位主机接收侧） ----------------
    integer rx_trace = 0;
    always @(posedge clk) begin
        if ($test$plusargs("trace") && u_m.st == 3'd4 && u_m.q == 2'd2 && rx_trace < 30) begin   // S_RX 且处于采样相位
            rx_trace <= rx_trace + 1;
            $display("      [主机收] bitc=%0d sda=%b 移位=%b rxc=%0d",
                     u_m.bitc, sda, u_m.sh, u_m.rxc);
        end
    end

    // ---------------- 看门狗 ----------------
    initial begin
        #20_000_000;
        $display("  [看门狗] 仿真超时，强制结束");
        $display("  汇总：错误 %0d 项", errors + 1);
        $finish;
    end

    // ---------------- 主流程 ----------------
    initial begin
        $display("==============================================================");
        $display(" I2C 主机 + MPR121 模型 自检");
        $display("==============================================================");

        rst_n = 1'b0;
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (10) @(posedge clk);

        $display(" 用例 1：写寄存器 0x5E = 0x24，再读回");
        do_xfer(1'b0, 7'h5A, 8'h5E, 16'h0024, 2'd1, 3'd1);
        if (err) begin $display("  FAIL  写入时从机未应答"); errors = errors + 1; end
        do_xfer(1'b1, 7'h5A, 8'h5E, 16'h0000, 2'd0, 3'd1);
        check("reg-readback", rd_d, 32'h0000_0024);

        $display(" 用例 2：读触摸状态 2 字节（touch = 0x0F0）");
        touch = 12'h0F0;
        repeat (10) @(posedge clk);
        do_xfer(1'b1, 7'h5A, 8'h00, 16'h0000, 2'd0, 3'd2);
        check("touch-status", rd_d, 32'h0000_00F0);

        $display(" 用例 3：访问不存在的从机地址 0x33，应报 err");
        do_xfer(1'b1, 7'h33, 8'h00, 16'h0000, 2'd0, 3'd1);
        if (err) $display("  PASS  未应答被正确标记");
        else begin $display("  FAIL  未应答未被标记"); errors = errors + 1; end

        $display("==============================================================");
        if (errors == 0) $display("RESULT i2c_basic=PASS");
        else begin $display("RESULT i2c_basic=FAIL errors=%0d", errors); $finish(1); end
        $display("==============================================================");
        $finish;
    end

endmodule
