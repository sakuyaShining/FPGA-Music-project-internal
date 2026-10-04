//=============================================================================
// tb_tdm_demo.v —— TDM 引擎的【音色示范】测试台
//
// 【它和 tb_tdm_equiv 的分工】
//   tb_tdm_equiv ：验证"TDM 与全并行逐位一致"（正确性，黄金参考法）
//   tb_tdm_demo  ：验证"加上每泛音独立包络之后，音色到底变了没有"（听感/效果）
//   两者刻意分开 —— 把一个测试台塞两种目的，最后两边都说不清。
//
// 【时间基准】
//   clk = 2.5 MHz（周期 400 ns），NSLOT = 64  ->  fs = 39062.5 Hz
//   这是【真实音频率】，所以输出可以直接写成 WAV 播放，
//   不需要任何重采样或时间缩放。
//
// 【怎么选音色】
//   预设表由 tools/scripts/tdm_demo.py gen 生成（preset.hex，64 行 48 位字）。
//   本测试台通过 +IDX=<0..3> 选择播放哪一组 16 个时隙：
//     组 0 = 拉杆风琴（对照组：频谱静止）
//     组 1 = 钢琴
//     组 2 = 钟（非谐 + 高次先死）
//     组 3 = 马林巴（1:4 非谐 + 很快衰减）
//
// 【为什么一次只放一个音色】
//   换成"一次跑完四个音色"需要在段间重新装载 + 重新触发，
//   而重新触发要走 RELEASE 段、相位也从不清零 —— 会引入与音色无关的差异。
//   分四次跑，每次都是干净的起音，比较才有意义。
//
// 用法：
//   iverilog -g2005 -o demo.vvp -s tb_tdm_demo src/rtl/*.v src/sim/tb_tdm_demo.v
//   vvp demo.vvp +IDX=2
//=============================================================================

`timescale 1ns/1ps

module tb_tdm_demo;

    localparam NSLOT    = 64;
    localparam PHASE_W  = 24;
    localparam AMP_W    = 8;
    localparam ENV_W    = 16;
    localparam OUT_W    = 24;

    localparam CLK_HALF = 200;          // 2.5 MHz
    localparam NSAMP    = 31250;        // 0.8 s @ 39062.5 Hz
    localparam NPART    = 16;           // 每组 16 个泛音

    reg clk, rst_n;

    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 音频时钟使能：每 NSLOT 拍一个样本（与 tdm_top 同一套链）
    //-------------------------------------------------------------------------
    wire sample_en;
    reg [5:0] pc;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)      pc <= 6'd0;
        else if (pc == NSLOT - 1) pc <= 6'd0;
        else             pc <= pc + 6'd1;
    end
    assign sample_en = (pc == 6'd0);

    //-------------------------------------------------------------------------
    // 预设表：由 Python 生成的 64 行 56 位字
    //   {inc[23:0], amp[7:0], epar[23:0]}   24 + 8 + 24 = 56
    //   ★ 曾用 48 位并把 amp 放 [23:16] —— 与 epar[23:0] 重叠，
    //     幅度高位漏进 s_lvl，包络早早停在 SUS，音色完全不变。
    //-------------------------------------------------------------------------
    reg [55:0] preset_mem [0:NSLOT-1];

    // ★ 这几根必须先声明再被下面的 p_inc/p_amp/p_epar 引用（Verilog 是声明先于使用）
    reg        load_en;
    reg [5:0]  load_slot;
    reg [22:0] load_epar;
    reg [PHASE_W-1:0] load_inc;
    reg [AMP_W-1:0]   load_amp;

    integer idx;
    initial begin
        if (!$value$plusargs("IDX=%d", idx)) idx = 0;
    end

    wire [PHASE_W-1:0] p_inc  = preset_mem[idx*NPART + load_slot][55:32];
    wire [AMP_W-1:0]   p_amp  = preset_mem[idx*NPART + load_slot][31:24];
    wire [22:0]        p_epar = preset_mem[idx*NPART + load_slot][23:0];

    //-------------------------------------------------------------------------
    // DUT
    //-------------------------------------------------------------------------
    wire signed [OUT_W-1:0] sample;

    tdm_engine #(
        .NSLOT(NSLOT), .PHASE_W(PHASE_W), .AMP_W(AMP_W),
        .ENV_W(ENV_W), .OUT_W(OUT_W), .GAIN_UP(4), .SHIFT(0)
    ) u_tdm (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .clr(1'b0), .pclr(1'b0), .gate_in(1'b1),
        .load_en(load_en), .load_slot(load_slot),
        .load_inc(load_inc), .load_amp(load_amp), .load_gate(1'b1),
        .load_epar(load_epar),
        .load_gq(18'sd0),
        .pmod_cfg(58'd0),
        .env_en(1'b1),
        .a_inc(16'd117), .d_inc(16'd1), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(16'd22938), .r_inc(16'd1), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(16'd100), .exp_mode(1'b1),
        .sample_out(sample), .sum_raw(), .slot_dbg()
    );

    //-------------------------------------------------------------------------
    // 激励
    //-------------------------------------------------------------------------
    integer k;
    integer fout;

    initial begin
        $readmemh("preset.hex", preset_mem);

        rst_n     = 1'b0;
        load_en   = 1'b0;
        load_slot = 6'd0;
        load_inc  = 24'd0;
        load_amp  = 8'd0;
        load_epar = 23'd0;

        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);

        // 装载本组 16 个时隙（其余时隙 amp=0，不发声）
        for (k = 0; k < NSLOT; k = k + 1) begin
            @(negedge clk);
            load_en   = 1'b1;
            load_slot = k[5:0];
            if (k < NPART) begin
                load_inc  = p_inc;
                load_amp  = p_amp;
                load_epar = p_epar;
            end
            else begin
                load_inc  = 24'd0;
                load_amp  = 8'd0;
                load_epar = 23'd0;
            end
        end
        @(negedge clk);
        load_en = 1'b0;

        // 起音：等一个周期边界后让门抬起（gcur 装载时已置 1，
        //   而 gq 初值 0 -> 第一个访问即触发）
        repeat (4) @(posedge clk);

        $display("==============================================");
        $display(" TDM 音色示范   预设组 %0d   NSLOT=%0d  fs=%0d Hz",
                 idx, NSLOT, 39062);
        $display(" 时长 %0d 样本 = %.2f s", NSAMP, NSAMP / 39062.5);
        $display("==============================================");

        fout = $fopen("demo_out.txt", "w");
        for (k = 0; k < NSAMP * NSLOT; k = k + 1) begin
            @(posedge clk);
            if (sample_en) $fdisplay(fout, "%0d %0d %0d %0d %0d %0d",
                k / NSLOT, $signed(sample),
                u_tdm.env_mem[0], u_tdm.epar_mem[0],
                u_tdm.env_mem[0] , u_tdm.stg_mem[0]);
        end
        $fclose(fout);
        $display(" 写出 demo_out.txt（%0d 个样本）", NSAMP);
        $finish;
    end

    // 硬超时
    initial begin
        #4_000_000_000;
        $display("[TIMEOUT] 仿真超时");
        $finish;
    end

endmodule
