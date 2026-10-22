//=============================================================================
// synth_top.v —— 多声部合成引擎（NV 个独立声部 + 混音）
//
// 【声部之间共享什么、不共享什么（这是复音合成器的标准做法）】
//
//   不共享（每声部独立）：
//     · 相位累加器 ×8      —— 决定了"这是几个独立振荡器"
//     · 包络状态 ×8        —— 决定了每个泛音的起音/衰减/释放各自走
//     · 门信号 gate        —— 每个声部自己按/放
//     · 音高 inc_all       —— 【关键】各声部音高必须能不同，否则只是"更响"，
//                             不构成复音。这是 M5（复音数 ≥4）的实质。
//
//   共享（同一个音色）：
//     · 幅度 amp_flat      —— 复音合成器里所有声部用同一个 patch，这是对的
//     · ADSR 参数          —— 同上
//
// 【为什么用 generate 例化而不是写四遍】
//   NV 做成参数后，声部数是"一个数字"而不是"四段重复代码"。
//   这样第 4 步做 4 声部、将来想扩到 8 声部只需改参数 ——
//   也正好是为了拿到"资源随声部数怎么涨"的真实曲线（TDM 决策要用）。
//
// 【混音】
//   各声部输出先各自饱和（在 osc_additive 内），再进 mixer 做加法 + 留量 + 饱和。
//   从这里再往下一级就是 i2s_tx，整条音频通路到此结束。
//=============================================================================

`timescale 1ns/1ps

module synth_top #(
    parameter NV      = 4,      // 声部数
    parameter NPART   = 8,      // 每声部泛音数
    parameter PHASE_W = 24,
    parameter AMP_W   = 8,
    parameter ENV_W   = 16,
    parameter OUT_W   = 24
)(
    input  wire clk,
    input  wire rst_n,
    input  wire sample_en,

    // ---- 各声部的音高（拼接：低段是 0 号声部）----
    input  wire [NV*NPART*PHASE_W-1:0] inc_all,

    // ---- 各声部的幅度（拼接）----
    //   正常演奏时四个声部填同一组值（同一个 patch）；
    //   测试模式下需要逐泛音独立开关，所以幅度必须是每声部一份。
    input  wire [NV*NPART*AMP_W-1:0]   amp_all,

    // ---- 各声部的门 ----
    input  wire [NV-1:0]               gate,

    // ---- 包络参数（共用）----
    input  wire                        env_en,
    input  wire [ENV_W-1:0]            a_inc,
    input  wire [ENV_W-1:0]            d_inc,
    input  wire [1:0]                  d_m,
    input  wire [4:0]                  d_k,
    input  wire [ENV_W-1:0]            s_lvl,
    input  wire [ENV_W-1:0]            r_inc,
    input  wire [1:0]                  r_m,
    input  wire [4:0]                  r_k,
    input  wire [ENV_W-1:0]            env_cutoff,
    input  wire                        exp_mode,

    // ---- 混音增益 ----
    input  wire [2:0]                  mix_gain_up,   // 电平提升（左移 0..7）
    input  wire [1:0]                  mix_shift,     // 留量（右移 0..3）

    // ---- 输出 ----
    output wire signed [OUT_W-1:0]     sample_out,   // 混音后（送 I2S）
    output wire [NV*OUT_W-1:0]         voice_out     // 各声部原始输出（调试/测试模式）
);

    //-------------------------------------------------------------------------
    // NV 个声部
    //-------------------------------------------------------------------------
    genvar gv;
    generate
        for (gv = 0; gv < NV; gv = gv + 1) begin : G_VOICE
            osc_additive #(
                .NUM_PARTIALS (NPART),
                .PHASE_W      (PHASE_W),
                .TAB_AW       (8),
                .AMP_W        (AMP_W),
                .OUT_W        (OUT_W),
                .ENV_W        (ENV_W)
            ) u_voice (
                .clk        (clk),
                .rst_n      (rst_n),
                .sample_en  (sample_en),
                .inc_flat   (inc_all[gv*NPART*PHASE_W +: NPART*PHASE_W]),
                .amp_flat   (amp_all[gv*NPART*AMP_W +: NPART*AMP_W]),
                .env_en     (env_en),
                .gate       (gate[gv]),
                .a_inc      (a_inc),
                .d_inc      (d_inc),
                .d_m        (d_m),
                .d_k        (d_k),
                .s_lvl      (s_lvl),
                .r_inc      (r_inc),
                .r_m        (r_m),
                .r_k        (r_k),
                .env_cutoff (env_cutoff),
                .exp_mode   (exp_mode),
                .sample_out (voice_out[gv*OUT_W +: OUT_W])
            );
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 混音
    //-------------------------------------------------------------------------
    mixer #(
        .NV (NV),
        .IW (OUT_W),
        .OW (OUT_W)
    ) u_mix (
        .vin    (voice_out),
        .gain_up(mix_gain_up),
        .shift  (mix_shift),
        .vout   (sample_out)
    );

endmodule
