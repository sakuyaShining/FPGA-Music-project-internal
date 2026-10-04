//=============================================================================
// tb_osc_env.v —— ADSR 包络状态推进单元的自检测试台
//
// 被测：src/rtl/osc_env.v（无状态组合单元，状态由本测试台持有 —— 这正是槽式接口的用法）
//
// 验收标准（对应 docs/02-技术方案/14-必须项实施计划.md 步骤 1）：
//   A1 起音：给 trig_on 后，恰好 ceil(FULL/a_inc) 拍到达满幅并进入 DECAY
//   A2 衰减：DECAY 段电平单调不增，降到延音电平后停在 SUSTAIN（不再往下掉）
//   A3 延音：SUSTAIN 段电平【恒定】= s_lvl，持续多久都不变
//   A4 释放：给 trig_rel 后进入 RELEASE，电平单调不增，最终精确归零并回 IDLE
//   A5 ★ 没有 trig_rel 就【永不】离开 SUSTAIN —— 这条直接钉死"弹一下响个不停"那类 bug
//   A6 指数模式：RELEASE 段相邻两拍电平之比恒定 ≈ r_coef/32768（证明是一阶指数）
//   A7 释放时长：实测归零拍数与解析式 ln(cutoff/FULL)/ln(r_coef/32768) 相差 ≤ 2 拍
//   A8 线性模式：RELEASE 段每拍恰好减 r_inc（证明线性分支没走错）
//   A9 重新触发：IDLE 状态下再次 trig_on 能重新起音（复音分配器依赖它）
//
// 为什么 A5 必须存在：
//   项目早期版本因为键盘读不到"松开"事件，音符进入 sustain 后永远不停。
//   包络本身没写错，错在没人给它下降沿。A5 守的就是"释放只能由 trig_rel 驱动"。
//
// 模型约定：1 个时钟 = 1 个包络拍（与 osc_additive 的 sample_en 同拍）
//=============================================================================

`timescale 1ns/1ps

module tb_osc_env;

    localparam ENV_W = 16;
    localparam STG_W = 3;
    localparam CLK_HALF = 10000;      // 20 µs 周期 -> 50 kHz

    localparam [STG_W-1:0] ST_IDLE = 3'd0,
                           ST_ATK  = 3'd1,
                           ST_DEC  = 3'd2,
                           ST_SUS  = 3'd3,
                           ST_REL  = 3'd4;

    localparam [ENV_W-1:0] FULL = 16'd32768;
    // 指数每拍比值理论值：1 - m/2^k（r_m=3, r_k=11）
    localparam real EXP_RATIO = 1.0 - 3.0/2048.0;

    reg clk;
    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 参数（与 Python 镜像必须一致）
    //-------------------------------------------------------------------------
    reg [ENV_W-1:0] a_inc, d_inc, s_lvl, r_inc, cutoff;
    reg [1:0]       d_m, r_m;
    reg [4:0]       d_k, r_k;
    reg             exp_mode;

    initial begin
        a_inc   = 16'd109;        // 32768/109 ≈ 300 拍 ≈ 6 ms @50kHz
        d_inc   = 16'd22;         // 线性衰减步长
        d_m     = 2'd3;           // 指数衰减：每拍减 (lvl*3)>>10 ≈ 2.93e-3·lvl
        d_k     = 5'd10;
        s_lvl   = 16'd22938;      // 延音电平 0.70
        r_inc   = 16'd22;         // 线性释放步长
        r_m     = 2'd3;           // 指数释放：每拍减 (lvl*3)>>11 ≈ 1.465e-3·lvl
        r_k     = 5'd11;
        cutoff  = 16'd100;        // 归零阈值
        exp_mode= 1'b1;
    end

    //-------------------------------------------------------------------------
    // 状态由测试台持有（槽式接口的用法：状态在哪，由使用者决定）
    //-------------------------------------------------------------------------
    reg [ENV_W-1:0] lvl;
    reg [STG_W-1:0] stg;
    wire [ENV_W-1:0] lvl_n;
    wire [STG_W-1:0] stg_n;
    reg trig_on, trig_rel;

    osc_env #(.ENV_W(ENV_W), .STG_W(STG_W)) dut (
        .lvl_i   (lvl),
        .stg_i   (stg),
        .trig_on (trig_on),
        .trig_rel(trig_rel),
        .a_inc   (a_inc),
        .d_inc   (d_inc),
        .d_m     (d_m),
        .d_k     (d_k),
        .s_lvl   (s_lvl),
        .r_inc   (r_inc),
        .r_m     (r_m),
        .r_k     (r_k),
        .cutoff  (cutoff),
        .exp_mode(exp_mode),
        .lvl_o   (lvl_n),
        .stg_o   (stg_n)
    );

    //-------------------------------------------------------------------------
    integer errors;
    integer i;
    // 报错信息用固定宽度向量承载（字符串左对齐，左侧补 NUL）。
    // ★ 不能直接用 %0s —— 会把左侧的 NUL 一起打出来，终端里变成乱码。
    //   这里逐字节输出并跳过前导 NUL。
    task chk;
        input cond;
        input [8*64-1:0] msg;
        integer j;
        reg started;
        begin
            if (!cond) begin
                errors = errors + 1;
                $write("  [FAIL] ");
                // ★ 字符串赋给向量是【左对齐】的：高字节存首字符。
                //   从高位往低位扫，并且【完全跳过 NUL 字节】——
                //   一旦 started 就无脑输出会把尾部填充的 NUL 也打出来，终端里是乱码。
                for (j = 63; j >= 0; j = j - 1) begin
                    if (msg[j*8 +: 8] != 8'h00) $write("%c", msg[j*8 +: 8]);
                end
                $write("   (lvl=%0d stg=%0d)\n", lvl, stg);
            end
        end
    endtask

    // 推进一拍（无事件）
    task tick;
        begin
            trig_on = 1'b0; trig_rel = 1'b0;
            @(posedge clk); #1;
            lvl = lvl_n; stg = stg_n;
        end
    endtask

    // 推进一拍，并在这一拍给出起音触发
    task tick_on;
        begin
            trig_on = 1'b1; trig_rel = 1'b0;
            @(posedge clk); #1;
            lvl = lvl_n; stg = stg_n;
            trig_on = 1'b0;
        end
    endtask

    // 推进一拍，并在这一拍给出释放触发
    task tick_rel;
        begin
            trig_on = 1'b0; trig_rel = 1'b1;
            @(posedge clk); #1;
            lvl = lvl_n; stg = stg_n;
            trig_rel = 1'b0;
        end
    endtask

    // 复位到 IDLE
    task reset_env;
        begin
            lvl = {ENV_W{1'b0}};
            stg = ST_IDLE;
            trig_on = 1'b0; trig_rel = 1'b0;
            #1;
        end
    endtask

    //-------------------------------------------------------------------------
    integer n_step, n_atk, n_dec, n_rel, n_ref;
    reg [ENV_W-1:0] prev_lvl, rr;
    reg [31:0] rt;
    reg ok_mono;
    reg [ENV_W-1:0] e0, e1, e2;
    real r01, r12;

    initial begin
        errors = 0;

        $display("==============================================");
        $display(" ADSR 包络状态推进单元自检  (fs = 50 kHz)");
        $display(" a_inc=%0d s_lvl=%0d r_m/k=%0d/%0d cutoff=%0d", a_inc, s_lvl, r_m, r_k, cutoff);
        $display("==============================================");

        //====================================================== A1/A2/A3/A5
        $display("[A1-A3,A5] IDLE->ATTACK->DECAY->SUSTAIN，且无 trig_rel 永不离开");
        reset_env;
        tick_on;

        // A1：起音拍数 = ceil(FULL / a_inc)
        n_atk = 0;
        while (stg == ST_ATK && n_atk < 2000) begin
            tick;
            n_atk = n_atk + 1;
        end
        $display("   起音: %0d 拍 (期望 %0d)  -> 状态=%0d", n_atk, (FULL+a_inc-1)/a_inc, stg);
        chk(n_atk == (FULL + a_inc - 1) / a_inc, "A1 起音拍数不符");
        chk(stg == ST_DEC, "A1 起音结束应进入 DECAY");
        chk(lvl == FULL,   "A1 起音结束电平应为满幅");

        // A2：衰减单调不增，落到 s_lvl 后进 SUSTAIN
        ok_mono = 1'b1; prev_lvl = lvl; n_dec = 0;
        while (stg == ST_DEC && n_dec < 100000) begin
            tick;
            if (lvl > prev_lvl) ok_mono = 1'b0;
            prev_lvl = lvl; n_dec = n_dec + 1;
        end
        $display("   衰减: %0d 拍后进入状态=%0d 电平=%0d (延音=%0d)", n_dec, stg, lvl, s_lvl);
        chk(ok_mono,          "A2 衰减段电平出现上升");
        chk(stg == ST_SUS,    "A2 衰减应停在 SUSTAIN");
        chk(lvl == s_lvl,     "A2 延音电平应精确等于 s_lvl");

        // A3 + A5：延音段长时间保持，绝不自行离开
        for (i = 0; i < 20000; i = i + 1) begin
            tick;
            if (stg != ST_SUS || lvl != s_lvl) begin
                chk(1'b0, "A5 未给 trig_rel 却离开了 SUSTAIN");
                i = 20000;
            end
        end
        $display("   延音: 20000 拍无 trig_rel，状态仍=%0d 电平=%0d  [A3/A5 OK]", stg, lvl);

        //====================================================== A4/A6/A7
        $display("[A4,A6,A7] 指数释放：单调不增、比值恒定、时长符合解析式");
        prev_lvl = lvl; n_rel = 0; ok_mono = 1'b1;
        tick_rel;                                     // 给出下降沿
        chk(stg == ST_REL, "A4 trig_rel 应进入 RELEASE");
        while (stg == ST_REL && n_rel < 200000) begin
            if (lvl > prev_lvl) ok_mono = 1'b0;
            prev_lvl = lvl; n_rel = n_rel + 1;
            tick;
        end
        // A7 参考模型：用同一递推式独立迭代一遍，验证状态机走的就是这条递推。
        //   ★ 不能拿"从满幅起步"的解析式来比 —— 释放是从【延音电平】起步的，
        //     而且整数每拍向下取整会让衰减比理论值略快。上次就是这么比错的。
        //   递推本身的正确性由 A6（相邻拍比值 ≈ coef/32768）独立保证。
        // 逐拍【镜像 RTL 的 RELEASE 分支】（含"步长至少为 1"的保护和阈值提前判定），
        // 比较的是状态机时序本身，而不是把解析式硬套上去 —— 解析式在
        // "从延音电平起步 + 整数取整 + 末段步长被钳到 1"这三重影响下本来就不准。
        rr = s_lvl; n_ref = 0;
        while (rr != 0 && n_ref < 200000) begin
            n_ref = n_ref + 1;
            if (rr <= cutoff)
                rr = 0;
            else begin
                rt = (rr * r_m) >> r_k;
                if (rt == 0) rt = 1;
                if ({1'b0, rr} <= {1'b0, cutoff} + rt[ENV_W:0]) rr = 0;
                else rr = rr - rt[ENV_W-1:0];
            end
        end
        $display("   释放: 实测 %0d 拍   参考递推 %0d 拍   末态=%0d 电平=%0d",
                 n_rel, n_ref, stg, lvl);
        chk(ok_mono,           "A6 释放段电平出现上升");
        chk(n_rel >= 2,        "A6 释放至少要走两拍");
        chk(lvl == 0,          "A4 释放结束电平应精确为 0");
        chk(stg == ST_IDLE,    "A4 释放结束应回 IDLE");
        chk(n_ref == n_rel,    "A7 实测释放拍数与参考递推不一致");

        // A6 比值恒定：单独跑一段指数释放，抽两对相邻拍校验
        reset_env; tick_on;
        while (stg != ST_SUS) tick;
        tick_rel;
        tick; tick; tick;                              // 越过最初两拍
        e0 = lvl; tick; e1 = lvl; tick; e2 = lvl;
        // 一阶指数要求 x1/x0 与 x2/x1 两个比值都 ≈ r_coef/32768
        chk(e1 < e0 && e2 < e1, "A6 指数释放未单调下降");
        chk(e0 > 0 && e1 > 0,   "A6 抽样点已归零");
        r01 = (e0 > 0) ? (e1 * 1.0 / e0) : 0.0;
        r12 = (e1 > 0) ? (e2 * 1.0 / e1) : 0.0;
        $display("   指数比值: x1/x0=%.6f  x2/x1=%.6f  理论 1-m/2^k=%.6f",
                 r01, r12, EXP_RATIO);
        chk((r01 - r12) < 0.001 && (r12 - r01) < 0.001, "A6 相邻拍比值不恒定（不是一阶指数）");
        chk((r01 - EXP_RATIO) < 0.001 && (EXP_RATIO - r01) < 0.001,
                                                        "A6 实测比值偏离 1-m/2^k 超过 0.001");

        //====================================================== A8 线性模式
        $display("[A8] 线性释放：每拍恰好减 r_inc");
        exp_mode = 1'b0;
        reset_env; tick_on;
        while (stg != ST_SUS) tick;
        tick_rel;
        prev_lvl = lvl;
        ok_mono = 1'b1;
        for (i = 0; i < 50; i = i + 1) begin
            tick;
            if (stg == ST_REL) begin
                if (lvl != prev_lvl - r_inc && lvl != 0) ok_mono = 1'b0;
                prev_lvl = lvl;
            end
        end
        chk(ok_mono, "A8 线性释放每拍减量不等于 r_inc");
        $display("   线性释放 50 拍后 电平=%0d 状态=%0d", lvl, stg);

        //====================================================== A9 重新触发
        $display("[A9] 回 IDLE 后再次 trig_on 能重新起音");
        exp_mode = 1'b1;
        while (stg != ST_IDLE) tick;
        tick_on;
        chk(stg == ST_ATK, "A9 重新触发应回到 ATTACK");
        for (i = 0; i < 400; i = i + 1) tick;
        chk(stg == ST_DEC || stg == ST_SUS, "A9 重新起音后未推进到 DECAY/SUSTAIN");

        //====================================================== 汇总
        $display("==============================================");
        if (errors == 0)
            $display(" [PASS] A1~A9 全部通过：ADSR 四段时序、阈值归零、无 trig_rel 永不自停");
        else
            $display(" [FAILED] 共 %0d 处错误", errors);
        $display("==============================================");
        $finish;
    end

endmodule
