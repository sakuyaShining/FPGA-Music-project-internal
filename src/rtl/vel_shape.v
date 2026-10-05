//=============================================================================
// vel_shape.v -- 力度 -> 谱形（音色）单元
//
// 依据（见《32-演奏表情问题总表》D-19/D-20 与真乐器物理）：
//   · 力度改变音色的第一性模型是【频谱倾斜】：
//       击得越重 -> 激励脉冲越窄 -> 高频越强
//   · 力度还改变【有几条泛音】：
//       低力度时高次泛音落到门限之下，等于不存在
//     本模块把两者合成一个操作：先算倾斜权重，再把低于门限的置零。
//
// 权重公式（第 0 版，公式实现的"表"；后续调音时可换成 16x16 逐项表）：
//     w(k, v) = 256 + tilt_eff(v) * (2k - 15) / 15        k = 0..15
//     tilt_eff(v) = TILT_BIAS + v * TILT_GAIN             (有符号)
//     amp(k) = base(k) * clamp(w, 0..511) >> 8           若该条被保留
//     amp(k) = 0                                        若 w 低于门限且不在保护区内
//
// 三条硬约束（对应判据 V1/V2）：
//   · 基音（part=0）任何力度下都不置零
//   · 最少保留 3 条泛音
//=============================================================================
module vel_shape #(
    parameter AW    = 8,
    parameter NFLOOR = 8'd64,       // 保护区最小权重（保证基音/低次永不消失）
    parameter NPART_PROTECT = 4'd3  // 前 N 条恒保留
)(
    vel, part, base, tilt_bias, tilt_gain, amp
);
    input  wire [3:0]         vel;         // 力度 0..15
    input  wire [3:0]         part;        // 泛音序号 0..15（0 = 基音）
    input  wire [AW-1:0]      base;        // 该泛音的预设幅度
    input  wire signed [9:0]  tilt_bias;   // 倾斜偏置（寄存器语义 = 每单位 skew 的增量）
    input  wire [7:0]         tilt_gain;   // 每档力度的倾斜增量
    output wire [AW-1:0]      amp;

    //=========================================================================
    // 【条数】机制：力度直接决定保留几条泛音（3 条 -> 16 条）
    //
    //   真乐器物理：力度低时高次泛音落到可闻/噪声门限之下，等于不存在。
    //   2026-10-06 改为【与倾斜解耦】：此前用"倾斜把权重压到门限下"来实现，
    //     结果既要够低（否则置零不可达）又会饱和（谱心不再单调），两难。
    //     现在条数由力度查表决定，倾斜只管亮度 —— 两条机制互不干扰。
    //=========================================================================
    function [4:0] n_keep_of;
        input [3:0] v;
        begin
            case (v)
                4'd0:  n_keep_of = 5'd3;   4'd1:  n_keep_of = 5'd3;
                4'd2:  n_keep_of = 5'd4;   4'd3:  n_keep_of = 5'd5;
                4'd4:  n_keep_of = 5'd6;   4'd5:  n_keep_of = 5'd7;
                4'd6:  n_keep_of = 5'd8;   4'd7:  n_keep_of = 5'd9;
                4'd8:  n_keep_of = 5'd10;  4'd9:  n_keep_of = 5'd11;
                4'd10: n_keep_of = 5'd12;  4'd11: n_keep_of = 5'd13;
                4'd12: n_keep_of = 5'd14;  4'd13: n_keep_of = 5'd15;
                4'd14: n_keep_of = 5'd15;  4'd15: n_keep_of = 5'd16;
                default: n_keep_of = 5'd3;
            endcase
        end
    endfunction

    //   总开关：两个倾斜寄存器都为 0 ⇒ 功能关闭 ⇒ 逐位恒等（既有证据不受影响）。
    //     2026-10-06：条数表在低力度【总是】砍泛音，与"默认恒等"直接冲突，
    //     判据 V8 抓到了这一点 ⇒ 必须给功能一个开关，而不是恒开。
    wire       feat_on = (tilt_bias != 10'sd0) || (tilt_gain != 8'd0);
    wire [4:0] n_keep  = feat_on ? n_keep_of(vel) : 5'd16;
    //   注意位宽：n_keep 是 5 位，16 用 4 位比较会被截断成 0（V 判据抓到过）
    wire [4:0] part5   = {1'b0, part};
    wire       in_cnt  = (part5 < n_keep) || (part == 4'd0);       // 基音恒保留

    //=========================================================================
    // 【亮度】机制：倾斜，范围有界且【永不饱和】
    //   w(k) = 256 + tilt_n * (k-7)，tilt_n 钳在 ±16
    //   ⇒ w ∈ [128, 384]，既不触顶也不触零，谱心严格单调
    //=========================================================================
    wire signed [15:0] tilt_eff = $signed({{6{tilt_bias[9]}}, tilt_bias}) +
                                  ($signed({8'd0, tilt_gain}) * $signed({12'd0, vel}));
    wire signed [12:0] tilt_n = (tilt_eff >  16'sd16) ?  13'sd16 :
                                (tilt_eff < -16'sd16) ? -13'sd16 : tilt_eff[12:0];
    //   零点定在【基音】(skew = k)，不是中点：
    //     原式 (k-7) 在"只保留前 3 条"时会让这几条全落在零点以下，
    //     倾斜一升它们反而【相对变暗】⇒ 谱心反降（判据 V3 抓到）。
    //     改成 skew = k 后：基音不受倾斜影响，任意保留集合下谱心都单调升。
    wire signed [12:0] skew   = {9'd0, part};                      // k ∈ [0, 15]
    wire signed [15:0] wraw   = 16'sd256 + tilt_n * skew;
    wire        [9:0]  wcl    = (wraw < 16'sd0) ? 10'd0 : wraw[9:0];   // 已不会触顶

    //   保护区再兜一层：即使倾斜把权重压得很低，前 N 条也保底，
    //   保证"基音永不消失"（判据 V1 曾抓到过这里漏掉的情况）。
    wire        [9:0]  wfin = (in_cnt && (wcl < {2'd0, NFLOOR})) ? {2'd0, NFLOOR} : wcl;

    wire [AW+8:0] shaped_full = base * wfin;
    wire [AW-1:0] shaped = (shaped_full[AW+8:8] > {AW{1'b1}})
                           ? {AW{1'b1}}
                           : shaped_full[AW+7:8];

    assign amp = in_cnt ? shaped : {AW{1'b0}};

endmodule
