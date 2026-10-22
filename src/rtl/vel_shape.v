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
    parameter NFLOOR = 9'd64,       // 保护区最小权重（保证基音/低次永不消失）
    parameter NPART_PROTECT = 4'd3  // 前 N 条恒保留
)(
    vel, part, base, tilt_bias, tilt_gain, amp
);
    input  wire [3:0]         vel;         // 力度 0..15
    input  wire [3:0]         part;        // 泛音序号 0..15（0 = 基音）
    input  wire [AW-1:0]      base;        // 该泛音的预设幅度
    input  wire signed [9:0]  tilt_bias;   // 预留（将来的全局倾斜基准）
    input  wire [7:0]         tilt_gain;   // 非零 = 打开"力度->音色"
    output wire [AW-1:0]      amp;

    //=========================================================================
    // 2026-10-06：由【公式】改为【查表】
    //
    //   为什么换：
    //     · 表达力：公式只能表达"倾斜 + 门限置零"；表可以直接写任意谱形
    //       （奇次优先的单簧管式空洞、弱音器的凹陷，都能写进去）
    //     · 时序：原公式含 wmul/15 除法，实测把 SETUP slack 打到 +4.488 ns
    //       （低于 5 ns 阈值，被闸口判红）；查表只剩"ROM + 一次小乘法"
    //     · 可调：表是 hex 文件（tools/scripts/gen_vel_wtab.py 生成），
    //       改音色不用改 RTL
    //
    //   恒等保证：tilt_gain = 0 ⇒ 功能关闭 ⇒ 权重恒为 256 ⇒ amp == base
    //     与改造前逐位相同（判据 V8 守着这一条）。
    //=========================================================================
    //   位宽必须是 12：hex 每项 3 个十六进制位（如 100 / 1D2）。
    //   2026-10-06 实测教训：原先声明 9 位，综合报
    //     WARN (EX2526): Entry size 12 ... does not match memory width 9
    //   仿真侧看不出来（iverilog 按数值读），但【板上 ROM 会装不进去】——
    //   典型的"仿真绿、上板不响"。这里按 12 位声明，只用低 9 位参与计算。
    reg [11:0] wtab [0:255];
    initial $readmemh("vel_wtab.hex", wtab);

    wire        feat_on = (tilt_gain != 8'd0);
    wire [7:0]  widx    = {vel, part};
    wire [8:0]  w_rom   = wtab[widx][8:0];             // 异步读：无延迟，无需流水对齐
    wire [8:0]  w_raw   = feat_on ? w_rom : 9'd256;    // 关功能 = 恒等

    //   保护区再兜一层：即使表里把基音/低次写得很低，也保底不消失。
    wire        protect = (part == 4'd0) || (part < NPART_PROTECT);
    wire [8:0]  w       = (protect && (w_raw < NFLOOR)) ? NFLOOR : w_raw;

    wire [AW+8:0] shaped_full = base * w;
    assign amp = (shaped_full[AW+8:8] > {AW{1'b1}}) ? {AW{1'b1}} : shaped_full[AW+7:8];

endmodule
