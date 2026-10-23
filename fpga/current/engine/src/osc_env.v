//=============================================================================
// osc_env.v —— ADSR 包络的【槽式】状态推进单元（无状态 / 纯组合）
//
// 【它是什么】
//   给定"当前包络状态 + 事件 + 参数"，算出"下一拍的状态"。
//   模块自己【不持有任何状态】—— 状态从 lvl_i/stg_i 进来，从 lvl_o/stg_o 出去，
//   存在哪里（寄存器阵列 / 将来 TDM 的 BSRAM）是外层的事。
//   与 osc_core 的拆分是同一个纪律（状态与运算分离），
//   目的是让"每声部一份""每泛音一份"乃至 TDM 时隙都能复用同一份逻辑。
//
// 【为什么每个泛音都要有自己的包络（合规性，不是锦上添花）】
//   赛题原文：独立发声单元 = 含【独立相位累加器、频率调控、包络控制】的完整振荡器；
//             加法合成【按运算分量统计】。
//   加法合成分量 = 每个泛音。若包络只做在声部级，严格读法下每个泛音并不拥有
//   自己的包络控制，"完整振荡器"就不成立 —— 而它直接决定核心指标能否声称。
//   所以本模块按【每泛音一份】实例化（见 osc_additive.v 的 G_ENV 生成块）。
//
// 【为什么一阶指数用"移位+加法"而不是乘系数（2026-09-30 实测逼出来的）】
//   首版写的是 lvl_next = (lvl * coef) >> 15，即每拍乘一个系数。
//   综合报告显示：加包络后 DSP 从 3/24 飙到 **15/24（63%）** ——
//   因为每个泛音有 2 个系数乘法（衰减 + 释放），8 个泛音就是 16 个乘法器。
//   一个声部就 63%，4 个声部必然溢出，而 DSP 溢出会退化成 LUT 乘法器，
//   吃掉大量逻辑并拖垮时序。
//
//   改成 lvl_next = lvl - ((lvl * m) >> k)：
//     · ×m 只用移位与加法（m=2 → 左移 1；m=3 → lvl + (lvl<<1)），**不占 DSP**
//     · 每拍衰减量 ≈ m / 2^k，仍是【一阶指数】（等比衰减），听感不变
//     · 时间常数 τ ≈ 2^k / m 个采样；-60 dB 约需 6.9τ
//     · m∈{1,2,3}、k∈{0..31} 的组合足以精确贴合设计值：
//         释放 0.40 s @46875 → τ≈2717 → m=3,k=13 (τ=2731) 误差 0.5%
//         释放 0.10 s @46875 → τ≈679  → m=3,k=11 (τ=683)  误差 0.6%
//   代价：只有移位与加减，**零 DSP**；换来的是 4 声部能装下。
//
// 【状态机】
//   IDLE --trig_on--> ATTACK --到满--> DECAY --到延音电平--> SUSTAIN
//   任意状态 --trig_rel--> RELEASE --低于阈值--> IDLE
//   · trig_on / trig_rel 由外层从"门信号的上升沿/下降沿"产生，
//     所以 RELEASE 是【按键抬起事件】驱动的 —— 这正是必须项 M7 的判定点。
//   · 攻击段固定线性（可预测）；衰减段可选线性或一阶指数。
//
// 【双段衰减（2026-10-23）】
//   DEC 段在跌破 d2_lvl 之后，把右移量从 d_k 换成 d2_k（更大的 k = 更慢）。
//   状态机【不增加状态】—— 仍是 5 态。原因是第二段与第一段共享同一个
//   "从当前电平向 s_lvl 递减"的语义，只是步长不同；加状态会破坏
//   "包络状态只有 3 位、512 个槽各存一份"的存储预算。
//   关闭方式：d2_k = 0。
//
// 【数值约定】
//   电平 Q1.15 无符号：0 = 静音，32768 = 满幅（1.0）。
//   所有运算都是整数移位/加减，必须与 Python 镜像【逐位一致】。
//=============================================================================

`timescale 1ns/1ps

module osc_env #(
    parameter ENV_W = 16,      // 包络电平位宽（Q1.15 无符号）
    parameter STG_W = 3        // 状态编码位宽
)(
    // ---- 当前状态（外部持有）----
    input  wire [ENV_W-1:0] lvl_i,
    input  wire [STG_W-1:0] stg_i,
    // ---- 事件（外层由门信号边沿产生）----
    input  wire             trig_on,     // 门的上升沿：起音
    input  wire             trig_rel,    // 门的下降沿：释放
    // ---- 参数（寄存器给出，可实时改）----
    input  wire [ENV_W-1:0] a_inc,       // 起音每拍线性增量
    input  wire [ENV_W-1:0] d_inc,       // 衰减每拍线性减量（线性模式用）
    input  wire [1:0]       d_m,         // 指数衰减倍率 m ∈ {1,2,3}
    input  wire [4:0]       d_k,         // 指数衰减右移量 k
    input  wire [ENV_W-1:0] s_lvl,       // 延音电平
    // ---- 双段衰减（2026-10-23 新增）----
    //   真实钢琴/弦乐的衰减是"先快后慢"：击弦瞬间能量经琴桥快速传走，
    //   之后由共鸣板辐射主导，衰减明显变慢。单段指数只能均匀衰减，
    //   听感上的"电子味"主要就来自这里。
    //   机制：DEC 段里电平跌破 d2_lvl 之后，右移量由 d_k 换成 d2_k。
    //   k 越大步长越小 ⇒ 衰减越慢，所以"变慢"必须 d2_k > d_k。
    //   关闭：d2_k = 0（此时 d2_lvl 无意义），行为与改动前逐位一致。
    input  wire [ENV_W-1:0] d2_lvl,      // 第二段起点（Q1.15，低于它切慢衰减）
    input  wire [4:0]       d2_k,        // 第二段右移量；0 = 关闭
    input  wire [ENV_W-1:0] r_inc,       // 释放每拍线性减量（线性模式用）
    input  wire [1:0]       r_m,         // 指数释放倍率 m ∈ {1,2,3}
    input  wire [4:0]       r_k,         // 指数释放右移量 k
    input  wire [ENV_W-1:0] cutoff,      // 归零阈值：低于它直接判静音
    input  wire             exp_mode,    // 1 = 衰减/释放用一阶指数, 0 = 线性
    // ---- 下一状态 ----
    output reg  [ENV_W-1:0] lvl_o,
    output reg  [STG_W-1:0] stg_o
);

    localparam [STG_W-1:0] ST_IDLE = 3'd0;
    localparam [STG_W-1:0] ST_ATK  = 3'd1;
    localparam [STG_W-1:0] ST_DEC  = 3'd2;
    localparam [STG_W-1:0] ST_SUS  = 3'd3;
    localparam [STG_W-1:0] ST_REL  = 3'd4;

    localparam [ENV_W-1:0] FULL = {1'b1, {(ENV_W-1){1'b0}}};   // 32768 = 1.0
    localparam [ENV_W-1:0] ONE  = {{(ENV_W-1){1'b0}}, 1'b1};

    //-------------------------------------------------------------------------
    // 组合中间量
    //-------------------------------------------------------------------------
    wire [ENV_W:0] atk_sum = {1'b0, lvl_i} + {1'b0, a_inc};    // 17 位防溢出
    // DECAY and RELEASE are mutually exclusive. Select parameters before
    // arithmetic so both phases share one shifter, threshold sum and subtractor.
    wire release_phase = stg_i == ST_REL;
    wire [1:0] step_m = release_phase ? r_m : d_m;
    wire [4:0] step_k = release_phase ? r_k : d_k;
    wire [ENV_W-1:0] linear_step = release_phase ? r_inc : d_inc;
    wire [ENV_W-1:0] floor_level = release_phase ? cutoff : s_lvl;

    // ×m（m=1/2/3）用移位与加法，不占 DSP
    wire [ENV_W+1:0] lvl_x1 = {2'b00, lvl_i};
    wire [ENV_W+1:0] lvl_x2 = {1'b0, lvl_i, 1'b0};
    wire [ENV_W+1:0] lvl_x3 = lvl_x1 + lvl_x2;

    wire [ENV_W+1:0] step_mul = (step_m == 2'd2) ? lvl_x2 :
                                (step_m == 2'd3) ? lvl_x3 : lvl_x1;

    //-------------------------------------------------------------------------
    // 双段衰减：DEC 段跌破 d2_lvl 后换成更小的步长（更大的 k）
    //
    //   三个条件缺一不可：
    //     1. d2_k != 0        —— 0 是"关闭"的编码，不是"k=0"（k=0 步长=满电平，
    //                            一拍就归零，毫无意义）
    //     2. d2_k >  step_k   —— **只允许变慢，不允许变快**。
    //                            没有这条守卫，某个泛音原本 d_k=20（很慢）时，
    //                            配一个 d2_k=15 会让尾音【突然加速】，听感上
    //                            是"尾巴被掐断"，比没有双段还糟。
    //     3. lvl_i < d2_lvl   —— 已经跌破断点
    //   release_phase 排除掉：释放是演奏者的手势，不该被"音色衰减形状"改写。
    //-------------------------------------------------------------------------
    wire d2_on = (d2_k != 5'd0) && (d2_k > step_k) &&
                 !release_phase && (lvl_i < d2_lvl);
    wire [4:0] step_k_eff = d2_on ? d2_k : step_k;

    wire [ENV_W+1:0] shifted = step_mul >> step_k_eff;

    // 步长若被移成 0 就取 1 —— 否则电平会永远卡住不动（死锁）
    wire [ENV_W-1:0] exp_step = (shifted == 0) ? ONE : shifted[ENV_W-1:0];
    reg [ENV_W-1:0] step;
    // Keep the old procedural-if behavior even when exp_mode is unknown.
    always @* if(exp_mode) step=exp_step; else step=linear_step;
    wire [ENV_W:0] floor_sum = {1'b0,floor_level}+{1'b0,step};
    wire crosses_floor = {1'b0,lvl_i} <= floor_sum;
    wire [ENV_W-1:0] reduced = lvl_i-step;

    //-------------------------------------------------------------------------
    // 次态逻辑
    //-------------------------------------------------------------------------
    always @(*) begin
        lvl_o = lvl_i;
        stg_o = stg_i;

        // A new excitation can arrive during sustain or an old release tail.
        // Restart attack from the current level, preserving phase/amplitude
        // continuity. Gate-off and ordinary parameter refresh do not trigger it.
        if (trig_on) begin
            stg_o = ST_ATK;
        end else case (stg_i)
            //------------------------------------------------- IDLE
            ST_IDLE: begin
                lvl_o = {ENV_W{1'b0}};
                if (trig_on)
                    stg_o = ST_ATK;
            end

            //------------------------------------------------- ATTACK
            ST_ATK: begin
                if (trig_rel)
                    stg_o = ST_REL;
                else if (atk_sum >= {1'b0, FULL}) begin
                    lvl_o = FULL;
                    stg_o = ST_DEC;
                end
                else
                    lvl_o = atk_sum[ENV_W-1:0];
            end

            //------------------------------------------------- DECAY
            ST_DEC: begin
                if (trig_rel)
                    stg_o = ST_REL;
                else if (lvl_i <= s_lvl) begin
                    lvl_o = s_lvl;
                    stg_o = ST_SUS;
                end
                else if (crosses_floor) begin
                    lvl_o = s_lvl;
                    stg_o = ST_SUS;
                end
                else lvl_o = reduced;
            end

            //------------------------------------------------- SUSTAIN
            ST_SUS: begin
                lvl_o = s_lvl;
                if (trig_rel)
                    stg_o = ST_REL;
            end

            //------------------------------------------------- RELEASE
            ST_REL: begin
                if (lvl_i <= cutoff) begin
                    lvl_o = {ENV_W{1'b0}};      // 到阈值以下：硬归零并回 IDLE
                    stg_o = ST_IDLE;
                end
                else if (crosses_floor) begin
                    lvl_o = {ENV_W{1'b0}};
                    // Preserve legacy linear release: it enters IDLE on the
                    // following update, while exponential release enters now.
                    if(exp_mode) stg_o = ST_IDLE;
                end
                else lvl_o = reduced;
            end

            //------------------------------------------------- 兜底
            default: stg_o = ST_IDLE;
        endcase
    end

endmodule
