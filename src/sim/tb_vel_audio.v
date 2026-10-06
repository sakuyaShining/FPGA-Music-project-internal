//=============================================================================
// tb_vel_audio.v -- 力度音色【试听】渲染：仿真导出真实音频
//
// 目的：让"力度参数调音"不必等硬件——仿真跑音频、导出 wav、人耳听、改表。
//
// 关键设计：**同级力度做"开/关"对比**
//   若直接比 轻 vs 重，重的那条只是更响（v14 比 v4 响约 7 倍），听不出音色差别。
//   所以四个用例是：
//     L_flat  (v=4 , 0x6D=0)   轻、功能关  ← 基准
//     L_shape (v=4 , 0x6D=1)   轻、功能开  ← 与上一行【同响度】，只差音色
//     H_flat  (v=14, 0x6D=0)   重、功能关
//     H_shape (v=14, 0x6D=1)   重、功能开
//
// 采样对齐：跟着 tdm_top 内部的 sample_en 落样本（即 DAC 真正收到的样本）
// 固定音高：MIDI 60（C4）
//=============================================================================
`timescale 1ns/1ps

module tb_vel_audio;

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

    parameter integer NSAMP = 20000;         // ≈0.38 s @ 52734 Hz（-P 可覆盖）
    parameter integer CASE_SET = 0;          // 0=四个用例 1=只做 L 对（诊断用）

    integer fd;
    integer i;
    reg [8*16-1:0] tag;

    //-------------------------------------------------------------- 落样本
    //   一直等到攒够 NSAMP 个 sample_en 脉冲
    task capture;
        input [8*16-1:0] name;
        integer n;
        begin
            fd = $fopen({name, ".txt"}, "w");
            n = 0;
            while (n < NSAMP) begin
                @(posedge clk);
                if (u_top.sample_en) begin
                    $fdisplay(fd, "%0d %0d", n, $signed(u_top.audio));
                    n = n + 1;
                end
            end
            $fclose(fd);
            $display("  %0s.txt 已写出（%0d 样本）", name, NSAMP);
        end
    endtask

    //-------------------------------------------------------------- 一个用例
    task do_case;
        input [8*16-1:0] name;
        input [3:0]      v;
        input            shape_on;
        begin
            // 先确保没有在响的音
            ev_note = 7'd60; ev_on = 1'b0; ev_valid = 1'b1;
            @(posedge clk); ev_valid = 1'b0;
            repeat (3000) @(posedge clk);

            // 力度->音色的【唯一开关兼灵敏度】= 0x6E：
            //   0x00 = 关；0x80 = 一等一（与参数表逐位相同）。
            //   （0x6D 是历史"倾斜斜率"，查表化后已不参与运算，这里不动它。）
            u_top.u_reg.mem[8'h6E] = shape_on ? 8'h80 : 8'h00;
            repeat (50) @(posedge clk);

            // 起音
            ev_note = 7'd60; ev_vel = v; ev_on = 1'b1; ev_valid = 1'b1;
            @(posedge clk); ev_valid = 1'b0; ev_on = 1'b0;

            // 采集
            capture(name);
        end
    endtask

    initial begin
        $display("==============================================================");
        $display(" vel_audio: 力度音色试听渲染（导出真实音频样本）");
        $display("==============================================================");

        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (2000) @(posedge clk);

        //-------------------------------------------------- 采样率自检
        //   上位机（tools/scripts/vel_audition.py）靠这一行确定 wav 头里的采样率。
        //   写死数字的风险：本项目采样率随 NSLOT/时钟配置变过多次
        //   （39062.5 / 46875 / 48828 / 52734…），一旦不匹配，试听就是"音调不对"，
        //   而人会先怀疑算法、不会怀疑采样率。
        begin : meas_fs
            integer t0, t1, w;
            t0 = 0; t1 = 0; w = 0;
            while (w < 3) begin
                @(posedge clk);
                if (u_top.sample_en) begin
                    if (w == 0) t0 = $time;
                    if (w == 2) t1 = $time;
                    w = w + 1;
                end
            end
            $display(" [采样率自检] 每样本约 %0d ns（3 个样本共 %0d ns）",
                     (t1 - t0) / 2, (t1 - t0));
        end

        do_case("L_flat",  4'd4,  1'b0);
        do_case("L_shape", 4'd4,  1'b1);
        if (CASE_SET == 0) begin
            do_case("H_flat",  4'd14, 1'b0);
            do_case("H_shape", 4'd14, 1'b1);
        end

        $display("==============================================================");
        $display(" 四个 txt 已写出：L_flat / L_shape / H_flat / H_shape");
        $display(" 用 tools/scripts/render_wav.py 转成 wav 试听");
        $display("==============================================================");
        $finish;
    end

    initial begin
        #5_000_000_000;
        $display(" [watchdog] timeout");
        $finish;
    end

endmodule
