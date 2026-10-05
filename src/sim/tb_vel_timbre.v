//=============================================================================
// tb_vel_timbre.v -- 力度->音色 的【端到端】判据（穿 tdm_top）
//
// 为什么要这条：V1-V8 验的是 vel_shape 【单元】；寄存器是否真能让它生效、
//   装载通路里的幅度是否真的变了，只有穿过 tdm_top 才能证明。
//   （本项目已经吃过"单元绿、集成路径从未跑到"的亏。）
//
// 做法：
//   1. 直接驱动 tdm_top 的事件端口（与 tb_vp7 同款）
//   2. 用层次引用戳 reg_bank 的 mem，设置 0x6B/0x6C/0x6D
//   3. 每个力度发一次 note-on，跟着 load_en 抓 16 条 load_amp（= 实际装载的频谱）
//   4. 落盘 vel_timbre.txt，由 Python 判据算谱心并比对
//
// 输出文件格式：每行 "标签 v <16 个幅度>"
//=============================================================================
`timescale 1ns/1ps

module tb_vel_timbre;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;             // ≈27 MHz

    reg rst_n = 1'b0;

    wire [15:0] pad_bus;
    reg         uart_rx = 1'b1;
    wire        uart_tx;
    reg         ev_valid, ev_on;
    reg [6:0]   ev_note;
    reg [3:0]   ev_vel;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    integer    fd;
    integer    caps [0:15];
    integer    n, i, errors;
    reg [8*24-1:0] tag;

    //-------------------------------------------------------------- 抓一次装载
    task play_and_capture;
        input [3:0] v;
        input [8*24-1:0] label;
        integer k;
        begin
            // 发 note-on
            ev_note  = 7'd60;               // 固定 C4，只变力度
            ev_vel   = v;
            ev_on    = 1'b1;
            ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            ev_on    = 1'b0;

            // 跟随装载：每次 load_en 抓一条幅度
            k = 0;
            while (k < 16) begin
                @(posedge clk);
                if (u_top.u_nm.load_en) begin
                    caps[k] = u_top.u_nm.load_amp;
                    k = k + 1;
                end
            end

            // 落盘
            $fwrite(fd, "%0s %0d", label, v);
            for (i = 0; i < 16; i = i + 1) $fwrite(fd, " %0d", caps[i]);
            $fwrite(fd, "\n");
            $display("  %0s v=%0d 幅度 = %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                     label, v,
                     caps[0],caps[1],caps[2],caps[3],caps[4],caps[5],caps[6],caps[7],
                     caps[8],caps[9],caps[10],caps[11],caps[12],caps[13],caps[14],caps[15]);

            // 收尾：note-off，等声部释放
            ev_note = 7'd60; ev_on = 1'b0; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            repeat (4000) @(posedge clk);
        end
    endtask

    initial begin
        $display("==============================================================");
        $display(" vel_timbre end-to-end criteria (through tdm_top)");
        $display("==============================================================");

        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (2000) @(posedge clk);

        fd = $fopen("vel_timbre.txt", "w");
        if (fd == 0) begin
            $display("  FAIL  无法创建 vel_timbre.txt");
            $finish;
        end

        //-------------------------------------------------- 第一组：默认参数（恒等）
        //   寄存器保持上电默认（0x6B/0x6C/0x6D 全 0）
        $display(" [A] default parameters (identity expected)");
        play_and_capture(4'd2,  "ident_lo");
        play_and_capture(4'd14, "ident_hi");

        //-------------------------------------------------- 第二组：打开倾斜
        //   bias = -300 (10 位补码 0x2D4 -> lo=0xD4, hi=0x02)，gain = 28 (0x1C)
        u_top.u_reg.mem[8'h6B] = 8'hD4;
        u_top.u_reg.mem[8'h6C] = 8'h02;
        u_top.u_reg.mem[8'h6D] = 8'h1C;
        repeat (100) @(posedge clk);

        $display(" [B] tilt enabled (bias=-300, gain=28)");
        play_and_capture(4'd2,  "tilt_lo");
        play_and_capture(4'd14, "tilt_hi");

        $fclose(fd);
        $display("  → vel_timbre.txt 已写出（4 行：ident_lo/ident_hi/tilt_lo/tilt_hi）");
        $display("==============================================================");
        $display(" 端到端采集完成，请用 judge 脚本判定");
        $display("==============================================================");
        $finish;
    end

    initial begin
        #400_000_000;
        $display(" [watchdog] timeout");
        $finish;
    end

endmodule
