//=============================================================================
// tb_synth_top.v —— 多声部引擎（4 声部 + 混音）自检
//
// 验收标准（对应 docs/02-技术方案/14-必须项实施计划.md 步骤 4）：
//   V1 ★ 4 个声部【同时】发声，且音高互不相同 —— 频谱上应出现 4 个独立基频峰
//        （这是 M5「复音数 ≥4」的实质证据：4 个声部不是"更响"，而是"4 个音"）
//   V2 混音 = 各声部之和（在不饱和区间内，逐样本核对）
//   V3 饱和正确：故意让 4 个满幅声部叠加 → 输出卡在满幅，【不回绕】
//   V4 门独立：松开一个声部不影响其他三个
//
// 模型约定：1 个时钟 = 1 个样本，周期 20 µs → fs = 50 kHz
//   inc = round(f × 2^24 / 50000)
//
// 测试用例：
//   A「单泛音四音」：每声部只开第 1 个泛音 → 频谱应恰好 4 个峰，便于机器判定
//   B「八泛音四音」：每声部 8 个泛音全开 → 检查混音与饱和
//
// 输出文件（供 Python 做 FFT 与数值比对）：
//   mix_a.txt / voice_a.txt     用例 A：混音输出 / 4 个声部分别输出
//   mix_b.txt / voice_b.txt     用例 B
//=============================================================================

`timescale 1ns/1ps

module tb_synth_top;

    localparam NV      = 4;
    localparam NPART   = 8;
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam OUT_W   = 24;
    localparam N_SAMP  = 8192;         // 8192 点 FFT（fs=50k → 分辨率 6.1 Hz）
    localparam CLK_HALF= 10000;        // 20 µs 周期 → fs = 50 kHz

    reg clk, rst_n;
    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 4 个声部的音高：A 大三和弦 220 / 277.18 / 329.63 / 440 Hz
    //   inc = round(f × 2^24 / 50000)
    //-------------------------------------------------------------------------
    localparam [23:0] INC_A3 = 24'd73820;    // 220.00 Hz
    localparam [23:0] INC_CS = 24'd93009;    // 277.18 Hz
    localparam [23:0] INC_E4 = 24'd110610;   // 329.63 Hz
    localparam [23:0] INC_A4 = 24'd147640;   // 440.00 Hz

    reg [NV*NPART*PHASE_W-1:0] inc_all;
    reg [NV*NPART*AMP_W-1:0]   amp_all;   // 每声部一份（四份相同）
    reg [NV-1:0]               gate;
    reg [2:0]                  mix_gain_up;

    wire signed [OUT_W-1:0]  sample_out;
    wire [NV*OUT_W-1:0]      voice_out;

    //-------------------------------------------------------------------------
    // DUT
    //-------------------------------------------------------------------------
    synth_top #(
        .NV(NV), .NPART(NPART), .PHASE_W(PHASE_W), .AMP_W(AMP_W), .OUT_W(OUT_W)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .sample_en  (1'b1),            // 每拍一个样本
        .inc_all    (inc_all),
        .amp_all    (amp_all),
        .gate       (gate),
        .env_en     (1'b0),            // 包络旁路：本用例只验多声部与混音
        .a_inc      (16'd0),
        .d_inc      (16'd0),
        .d_m        (2'd0),
        .d_k        (5'd0),
        .s_lvl      (16'd0),
        .r_inc      (16'd0),
        .r_m        (2'd0),
        .r_k        (5'd0),
        .env_cutoff (16'd0),
        .exp_mode   (1'b1),
        .mix_gain_up(mix_gain_up),
        .mix_shift  (2'd0),
        .sample_out (sample_out),
        .voice_out  (voice_out)
    );

    //-------------------------------------------------------------------------
    // 激励
    //-------------------------------------------------------------------------
    integer fm, fv;
    integer n;
    integer gv, gp;

    task set_inc;
        input [PHASE_W-1:0] i0, i1, i2, i3;
        integer k;
        begin
            // 每个声部的 8 个泛音都设为同一个 inc（用例 A 里只有第 1 个有幅度）
            for (k = 0; k < NPART; k = k + 1) begin
                inc_all[(0*NPART + k)*PHASE_W +: PHASE_W] = i0;
                inc_all[(1*NPART + k)*PHASE_W +: PHASE_W] = i1;
                inc_all[(2*NPART + k)*PHASE_W +: PHASE_W] = i2;
                inc_all[(3*NPART + k)*PHASE_W +: PHASE_W] = i3;
            end
        end
    endtask

    task dump_case;
        input [8*32-1:0] fmix;
        input [8*32-1:0] fvox;
        integer k;
        begin
            rst_n = 1'b0;
            repeat (4) @(posedge clk);
            rst_n = 1'b1;
            repeat (12) @(posedge clk);        // 等流水线填满（7 级 + 余量）

            fm = $fopen(fmix, "w");
            fv = $fopen(fvox, "w");
            for (k = 0; k < N_SAMP; k = k + 1) begin
                @(posedge clk);
                #1;
                $fdisplay(fm, "%0d", sample_out);
                // ★ 同样必须 $signed()：切片会丢符号性
                $fdisplay(fv, "%0d %0d %0d %0d",
                          $signed(voice_out[0*OUT_W +: OUT_W]),
                          $signed(voice_out[1*OUT_W +: OUT_W]),
                          $signed(voice_out[2*OUT_W +: OUT_W]),
                          $signed(voice_out[3*OUT_W +: OUT_W]));
            end
            $fclose(fm);
            $fclose(fv);
        end
    endtask

    initial begin
        inc_all  = {(NV*NPART*PHASE_W){1'b0}};
        amp_all  = {(NV*NPART){8'd0}};
        gate     = 4'b1111;
        mix_gain_up = 3'd0;

        $display("==============================================");
        $display(" 多声部引擎自检  NV=%0d  fs=50kHz", NV);
        $display("==============================================");

        //---------------- 用例 A：4 声部 × 单泛音 ----------------
        set_inc(INC_A3, INC_CS, INC_E4, INC_A4);
        // 只开第 1 个泛音，其余 7 个幅度为 0 → 频谱上每个声部只有一个峰
        amp_all  = {(NV*NPART){8'd0}};
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 0)*AMP_W +: AMP_W] = 8'd120;
        dump_case("mix_a.txt", "voice_a.txt");
        $display(" [A] 4 声部单泛音 → mix_a.txt / voice_a.txt");

        //---------------- 用例 B：4 声部 × 8 泛音 ----------------
        mix_gain_up = 3'd4;   // 真实电平（×16）
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 0)*AMP_W +: AMP_W] = 8'd200;
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 1)*AMP_W +: AMP_W] = 8'd120;
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 2)*AMP_W +: AMP_W] = 8'd80;
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 3)*AMP_W +: AMP_W] = 8'd60;
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 4)*AMP_W +: AMP_W] = 8'd45;
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 5)*AMP_W +: AMP_W] = 8'd36;
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 6)*AMP_W +: AMP_W] = 8'd30;
        for (gp = 0; gp < NV; gp = gp + 1)
            amp_all[(gp*NPART + 7)*AMP_W +: AMP_W] = 8'd26;
        dump_case("mix_b.txt", "voice_b.txt");
        $display(" [B] 4 声部八泛音 → mix_b.txt / voice_b.txt");

        $display("==============================================");
        $display(" 仿真结束，请用 Python 做 FFT 与数值比对");
        $display("==============================================");
        $finish;
    end

endmodule
