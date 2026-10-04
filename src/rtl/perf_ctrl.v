//=============================================================================
// perf_ctrl.v —— 演奏交互层核心（设备无关）  目标：基础项 M1 + M9
//
// 【M1】「≥2 个独立可控演奏维度」判据是"现场演示可分别操控"
// 【M9】「自研演奏交互形态……基于各类传感器实现演奏动作精准采集，
//        支持选音、触发、拨弦、力度感应等操作」
//
// ---------------------------------------------------------------------------
// 【为什么把"核心"和"传感器"分开】
//   本模块【只认一条通用测量总线】，不认任何具体器件：
//        m1_raw/m1_vld  → 维度1（选音）   例：测距值、编码器计数、触摸键序号
//        m2_raw/m2_vld  → 维度2（力度）   例：第二次测量、挥速、压力值
//        pads[3:0]      → 触发（按下持续 / 松手收声）
//   具体传感器只要写一个几十行的"解码模块"把电气信号变成这条总线即可，
//   核心一行都不用改 —— 这样"器件还没定"也不耽误把 M1/M9 的骨架和判据做完。
//
// ---------------------------------------------------------------------------
// 【两种演奏手感，各自对应 M9 的一个词】
//   · pads 按下（触摸键/按键）→ note-on，**按住持续**，松手才 note-off
//         = 「选音」+「触发」
//   · m1 变化率超阈值（挥手）→ note-on，固定门长后**自动收声**
//         = 「拨弦」，而且力度 = 挥速 ⇒「力度感应」
//
// ---------------------------------------------------------------------------
// 【★ 锁存语义（乐器必须有，也是判据之一）】
//   音高与力度在【触发那一瞬间锁存】，之后转动/移动传感器**不能改变正在响的音**。
//   真实乐器就是这样：拨完弦再移动手，音高不会跟着跑。
//   第一版没锁存，结果"扫一遍维度1"会把已经发出的音全部重新定音 —— 判据 P3 抓住。
//
// ---------------------------------------------------------------------------
// 【为什么全程不用除法】映射写成
//        note = note_lo + ((m1_raw - m1_lo) >> m1_shift)
//        vel  = (m2_raw >> m2_shift) 上限 15
//   只用移位与加法：既省逻辑，又让上位机/测试台能逐字复算出期望值
//   （判据脚本正是这么独立算一遍再比对的）。
//=============================================================================

`timescale 1ns/1ps

module perf_ctrl #(
    parameter integer NB     = 7,     // MIDI 音高位数
    parameter integer GATE_W = 20     // 自动收声门长位宽（单位：样本）
)(
    input  wire              clk,
    input  wire              rst_n,
    input  wire              sample_en,

    // ---- 通用测量总线（由具体传感器的解码模块驱动）----
    input  wire [15:0]       m1_raw,
    input  wire              m1_vld,      // 一次新测量（一个时钟宽）
    input  wire [15:0]       m2_raw,
    input  wire              m2_vld,
    input  wire [3:0]        pads,        // 4 路触发（高有效）

    // ---- 运行时配置 ----
    input  wire              en,          // 交互层使能
    input  wire [3:0]        m1_shift,    // 维度1→音高：每个半音 = 2^shift 个原始值
    input  wire [15:0]       m1_lo,       // 维度1 下限（低于它算最低音）
    input  wire [NB-1:0]     note_lo,     // 音域下限
    input  wire [3:0]        m2_shift,    // 维度2→力度：每级 = 2^shift 个原始值
    input  wire              rate_en,     // 变化率触发（挥手=拨弦）
    input  wire [15:0]       rate_th,     // 触发阈值
    input  wire [3:0]        rate_shift,  // 变化率→力度
    input  wire [GATE_W-1:0] gate_len,    // 自动收声长度（样本）

    // ---- 输出：统一"演奏动作"总线（与引擎 ev_* 同构）----
    output reg               act_valid,
    output reg               act_on,      // 1 = note-on, 0 = note-off
    output reg  [NB-1:0]     act_note,
    output reg  [3:0]        act_vel,

    // ---- 调试 / LED ----
    output reg  [NB-1:0]     dim_note,    // 当前维度1 对应的音高
    output reg  [3:0]        dim_vel,     // 当前维度2
    output reg  [15:0]       rate_dbg,    // 当前变化率（调试）
    output reg               activity     // 正在响（给 LED）
);

    //-------------------------------------------------------------------------
    // 维度1 → 音高
    //-------------------------------------------------------------------------
    wire [16:0] m1_diff = {1'b0, m1_raw} - {1'b0, m1_lo};
    wire [16:0] m1_off  = (m1_raw < m1_lo) ? 17'd0 : (m1_diff >> m1_shift);
    wire [17:0] m1_sum  = {4'd0, note_lo} + {1'b0, m1_off};
    wire [NB-1:0] m1_note = (m1_sum > 18'd127) ? {NB{1'b1}} : m1_sum[NB-1:0];

    //-------------------------------------------------------------------------
    // 维度2 → 力度（0..15）
    //-------------------------------------------------------------------------
    wire [15:0] m2_off = m2_raw >> m2_shift;
    wire [3:0]  m2_vel = (m2_off > 16'd15) ? 4'd15 : m2_off[3:0];

    //-------------------------------------------------------------------------
    // 变化率 → 力度（挥手越快越响）
    //-------------------------------------------------------------------------
    reg  [15:0] m1_prev;
    reg  [15:0] rate_abs;
    reg         rate_vld;
    wire [15:0] rate_diff = (m1_raw >= m1_prev) ? (m1_raw - m1_prev) : (m1_prev - m1_raw);
    wire [15:0] rate_sh   = rate_abs >> rate_shift;
    wire [3:0]  rate_vel  = (rate_sh > 16'd15) ? 4'd15 : rate_sh[3:0];

    //-------------------------------------------------------------------------
    // 触发与门控
    //-------------------------------------------------------------------------
    reg  [3:0]  pads_d;
    wire        pad_rise = |(pads & ~pads_d);      // 任一路按下
    wire        pad_fall = |(~pads & pads_d);      // 任一路松开

    reg         gate_hold;                          // 由 pads 按住
    reg  [GATE_W-1:0] gate_cnt;                     // 自动收声倒计时
    reg  [NB-1:0] held_note;                        // ★ 锁存：正在响的音高
    reg  [3:0]    held_vel;                         // ★ 锁存：正在响的力度

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            act_valid <= 1'b0; act_on <= 1'b0;
            act_note  <= {NB{1'b0}}; act_vel <= 4'd0;
            dim_note  <= {NB{1'b0}}; dim_vel <= 4'd0;
            rate_dbg  <= 16'd0; activity <= 1'b0;
            m1_prev   <= 16'd0; rate_abs <= 16'd0; rate_vld <= 1'b0;
            pads_d    <= 4'd0; gate_hold <= 1'b0; gate_cnt <= {GATE_W{1'b0}};
            held_note <= {NB{1'b0}}; held_vel <= 4'd0;
        end
        else begin
            act_valid <= 1'b0;
            pads_d    <= pads;
            rate_vld  <= 1'b0;

            // ---- 刷新"当前维度值"（不改变已锁存的音）----
            if (m1_vld) begin
                dim_note <= m1_note;
                rate_abs <= rate_diff;
                rate_dbg <= rate_diff;
                rate_vld <= 1'b1;
                m1_prev  <= m1_raw;
            end
            if (m2_vld)
                dim_vel <= m2_vel;

            if (!en) begin
                // 关掉交互层时若还有音在响，补一个 note-off，不留挂音
                if (activity) begin
                    act_valid <= 1'b1; act_on <= 1'b0;
                    act_note  <= held_note; act_vel <= held_vel;
                end
                gate_hold <= 1'b0;
                gate_cnt  <= {GATE_W{1'b0}};
                activity  <= 1'b0;
            end
            else begin
                if (pad_rise) begin
                    //==== 「触发」：按下即发声，音高/力度【当场锁存】====
                    act_valid <= 1'b1; act_on <= 1'b1;
                    act_note  <= m1_note;
                    act_vel   <= m2_vel;
                    held_note <= m1_note;
                    held_vel  <= m2_vel;
                    gate_hold <= 1'b1;
                    gate_cnt  <= {GATE_W{1'b0}};     // pads 型靠松手收声
                    activity  <= 1'b1;
                end
                else if (rate_en && rate_vld && (rate_abs >= rate_th) && (rate_abs != 16'd0)) begin
                    //==== 「拨弦」：挥手触发，力度 = 挥速，固定门长后自动收声 ====
                    act_valid <= 1'b1; act_on <= 1'b1;
                    act_note  <= m1_note;
                    act_vel   <= rate_vel;
                    held_note <= m1_note;
                    held_vel  <= rate_vel;
                    gate_hold <= 1'b0;
                    gate_cnt  <= gate_len;
                    activity  <= 1'b1;
                end
                else if (gate_hold && pad_fall) begin
                    //==== 松手收声 ====
                    act_valid <= 1'b1; act_on <= 1'b0;
                    act_note  <= held_note; act_vel <= held_vel;
                    gate_hold <= 1'b0;
                    activity  <= 1'b0;
                end
                else if (gate_cnt != {GATE_W{1'b0}} && sample_en) begin
                    //==== 自动收声（拨弦型）====
                    gate_cnt <= gate_cnt - 1'b1;
                    if (gate_cnt == {{(GATE_W-1){1'b0}}, 1'b1}) begin
                        act_valid <= 1'b1; act_on <= 1'b0;
                        act_note  <= held_note; act_vel <= held_vel;
                        activity  <= 1'b0;
                    end
                end
            end
        end
    end

endmodule
