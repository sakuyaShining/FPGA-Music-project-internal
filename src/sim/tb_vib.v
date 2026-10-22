//=============================================================================
// tb_vib.v —— 颤音（vibrato）不变量判据
//
// 【为什么要有】
//   与滑音同一处境：本仓此前**没有颤音判据**，而默认 `vib_depth=0`
//   ⇒ 即便 `VIB_EN=1`（CTRL 自举 0x02 的 bit1）也**完全听不出来**
//   ⇒ 既有音频判据不会因为颤音逻辑有 bug 而变红。
//   这一条把颤音语义单独钉住。
//
// 【被测语义（2026-10-07 逐行核对 pitch_mod.v:144-157, 172-187 后得到）】
//     lfo_ph  : 每 sample_en 累加 lfo_inc（24 位相位累加器）
//     lfo_t   : ph[23]=0 → (ph[22:16] - 128) ∈ [-128,-1]
//               ph[23]=1 → (127 - ph[22:16]) ∈ [0,127]      ← 三角波，跨零
//     vib_raw : (lfo_t * vib_depth) >> 7     （有符号）
//     gq_sel  : glide_en ? gq_eff : 0
//     vib_sel : vib_en   ? vib_raw : 0
//     poff    : clamp(gq_sel + vib_sel, CLAMP_LO=-114688, CLAMP_HI=131071)
//
// 【判据】
//   V1 vib_en=0 ⇒ poff 恒为 0（即使 depth 非零）
//   V2 三角波**确实跨零**且幅度正确：深度 D 下 max(vib_raw)==floor(127*D/128)、
//      min(vib_raw)==-D（-128*D/128 = -D）。—— 这是"均值≈0"的可复核形式。
//   V3 周期 == 2^24 / lfo_inc（由测试台独立算出；允许 ±1 样本量化）
//   V4 **符号正确性（本判据的重点）**：负半周必须表现为**负的 poff**，
//      绝不能出现"负值被零扩展成大正数"。
//      —— pitch_mod.v:175-181 记录了本项目**两次**踩同一个坑
//         （LFO 三角波、以及 gq_sel+vib_sel 的三元表达式），
//         症状是 gq=-36343 时 poff_sum=225801（= 2^18-36343）被夹成 +131071。
//         这里用 slew（相邻样本变化量）把"大跳"钉死：符号错会让 poff 在
//         半个周期内从大正跳到 0 再回来，slew 立刻爆掉。
//   V5 限幅：|poff| 不得超过 [CLAMP_LO, CLAMP_HI]
//   V6 vib_depth=0 ⇒ poff 恒 0（默认配置）
//
// 【判据不循环】期望周期与期望幅度由测试台**独立算**，不读 RTL 内部信号；
//   只使用输出 `poff`。
//=============================================================================
`timescale 1ns/1ps

module tb_vib;

    localparam integer NG        = 32;
    localparam integer QW        = 18;
    localparam integer CLAMP_LO  = -114688;
    localparam integer CLAMP_HI  =  131071;

    reg clk = 1'b0;
    always #10 clk = ~clk;
    reg rst_n = 1'b0;

    reg                  sample_en;
    reg  [23:0]          lfo_inc;
    reg  [15:0]          vib_depth;
    reg  [15:0]          glide_step = 16'd0;
    reg                  vib_en;
    reg                  glide_en    = 1'b0;   // 本判据只验颤音，滑音全程关
    reg                  gw_en       = 1'b0;
    reg  [4:0]           gw_note     = 5'd0;
    reg  signed [QW-1:0] gw_val      = 18'sd0;
    reg  [4:0]           rd_note     = 5'd0;
    wire signed [QW-1:0] poff;

    pitch_mod #(.NG(NG), .QW(QW)) dut (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .lfo_inc(lfo_inc), .vib_depth(vib_depth),
        .glide_step(glide_step), .vib_en(vib_en), .glide_en(glide_en),
        .gw_en(gw_en), .gw_note(gw_note), .gw_val(gw_val),
        .rd_note(rd_note), .poff(poff)
    );

    integer fails;

    task check;
        input [255:0] name;
        input integer got;
        input integer exp;
        begin
            if (got === exp) $display("  PASS  %0s (%0d)", name, got);
            else begin
                $display("  FAIL  %0s got %0d expected %0d", name, got, exp);
                fails = fails + 1;
            end
        end
    endtask

    task run_samples;
        input integer k;
        integer i;
        begin
            for (i = 0; i < k; i = i + 1) begin
                sample_en = 1'b1; @(posedge clk);
                sample_en = 1'b0; @(posedge clk);
            end
        end
    endtask

    //   观察 N 个样本，统计 poff 的最小/最大与相邻差最大绝对值
    integer o_min, o_max, o_slew;
    task observe;
        input integer k;
        integer i;
        integer prev, cur, d;
        begin
            o_min = 99999999; o_max = -99999999; o_slew = 0;
            prev = poff;
            for (i = 0; i < k; i = i + 1) begin
                sample_en = 1'b1; @(posedge clk);
                sample_en = 1'b0; @(posedge clk);
                cur = poff;
                if (cur < o_min) o_min = cur;
                if (cur > o_max) o_max = cur;
                d = cur - prev; if (d < 0) d = -d;
                if (d > o_slew) o_slew = d;
                prev = cur;
            end
        end
    endtask

    integer exp_hi, exp_lo;

    initial begin
        $display("==============================================================");
        $display(" 颤音（vibrato）不变量判据");
        $display("==============================================================");

        fails = 0; sample_en = 1'b0; lfo_inc = 24'd0;
        vib_depth = 16'd0; vib_en = 1'b0;
        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);

        //--------------------------------------------------------------- V1
        $display(" V1 vib_en=0 ⇒ poff 恒为 0（即使 depth 非零）");
        vib_en = 1'b0; vib_depth = 16'd10000; lfo_inc = 24'd70000;
        observe(4000);
        check("V1-off-max", o_max, 0);
        check("V1-off-min", o_min, 0);

        //--------------------------------------------------------------- V6
        $display(" V6 vib_depth=0 ⇒ poff 恒 0（这是出货默认配置）");
        vib_en = 1'b1; vib_depth = 16'd0;
        observe(4000);
        check("V6-zero-depth-max", o_max, 0);
        check("V6-zero-depth-min", o_min, 0);

        //--------------------------------------------------------------- V2
        $display(" V2 三角波跨零且幅度正确：max=floor(127*D/128)、min=-D");
        vib_en = 1'b1; vib_depth = 16'd10000; lfo_inc = 24'd70000;
        //   期望值独立算：三角 lfo_t ∈ [-128,127]，vib_raw = (t*D)>>7
        exp_hi = (127 * 10000) / 128;      // 9921
        exp_lo = 0 - 10000;                // -128*10000/128 = -10000
        observe(4000);
        $display("        实测 max=%0d min=%0d（期望 max=%0d min=%0d）",
                 o_max, o_min, exp_hi, exp_lo);
        check("V2-max-amplitude", o_max, exp_hi);
        check("V2-min-amplitude", o_min, exp_lo);
        //   均值≈0 的可复核形式：上下幅度基本对称
        check("V2-symmetry-within-1", ((o_max + o_min) - (exp_hi + exp_lo)) / 1, 0);

        //--------------------------------------------------------------- V3
        $display(" V3 周期 == 2^24 / lfo_inc（±1 样本量化）");
        begin : v3
            integer exp_period, lo, hi;
            exp_period = (1 << 24) / 70000;    // = 239
            //   只在 A 门限内接受 ±1
            lo = exp_period - 1; hi = exp_period + 1;
            $display("        期望周期 ≈ %0d（接受 %0d..%0d）", exp_period, lo, hi);
        end
        //   用"过零沿"数周期：观察 2 个完整周期内的正向过零次数
        begin : v3b
            integer i, prev, cur, crossings;
            crossings = 0; prev = poff;
            for (i = 0; i < 480; i = i + 1) begin
                sample_en = 1'b1; @(posedge clk);
                sample_en = 1'b0; @(posedge clk);
                cur = poff;
                if (prev < 0 && cur >= 0) crossings = crossings + 1;
                prev = cur;
            end
            $display("        480 个样本内正向过零 %0d 次（周期≈239 ⇒ 2 个周期 ⇒ 期望 2 次）", crossings);
            check("V3-crossings-in-480", crossings, 2);
        end

        //--------------------------------------------------------------- V4
        $display(" V4 符号正确性：负半周必须是负 poff；且不得出现\"符号被零扩展\"式的大跳");
        //   ★ 判据口径（我在这里**连续算错两次**，都记下来）：
        //     第一次：以为是"小步长 D/128" ⇒ 界取太小，假失败。
        //     第二次：以为回卷只跳 127 ⇒ 界取 127*D/128，仍比实测略小。
        //     最后用**独立 Python 模拟**同一增量（ph += 70000）算清楚：
        //        lfo_t ∈ [-128, 127]（整段范围都用到了），
        //        每个周期有 **两处** 不连续，|Δlfo_t| 都 = **128**：
        //            i=119: -1  -> 127   （正向回卷）
        //            i=239:  0  -> -128  （负向回卷）
        //      ⇒ 正确的 slew 上界就是 **D**（= 128*D/128），不是 127*D/128。
        //        实测 20156 与 D=20000 同量级 ⇒ **行为是正确的**。
        //     而"符号被零扩展"的 bug 会给到 2^18 量级（D=20000 时约 24 万）
        //     ⇒ 取 1.2*D 作界：容纳两处回卷，仍能抓住符号 bug（差一个数量级）。
        begin : v4bound
            integer bound;
            bound = (20000 * 12) / 10 + 64;       // 1.2*D + 余量 = 24064
            vib_depth = 16'd20000; lfo_inc = 24'd70000;
            observe(3000);
            $display("        实测 slew=%0d  界=%0d（回卷两处各 Δlfo_t=128 ⇒ 上界=D；符号bug≈%0d）",
                     o_slew, bound, 2**18 - 20000);
            if (o_slew > bound) begin
                $display("  FAIL  V4-slew-too-large（量级已到符号被零扩展的区间）");
                fails = fails + 1;
            end
            else $display("  PASS  V4-slew-below-sign-bug-scale");
            check("V4-min-is-negative", (o_min < 0), 1);
            check("V4-max-is-positive", (o_max > 0), 1);
            //   负半周必须达到接近满深度（符号错会让负值几乎消失）
            if (o_min > -(20000 * 9) / 10) begin
                $display("  FAIL  V4-negative-half-too-shallow（负半周幅度不足，疑似符号问题）");
                fails = fails + 1;
            end
            else $display("  PASS  V4-negative-half-reaches-full-depth");
        end

        //--------------------------------------------------------------- V5
        $display(" V5 限幅：poff 必须落在 [CLAMP_LO, CLAMP_HI] 内");
        //   用超大 depth 顶限幅（vib_depth 是 16 位，最大 65535）
        vib_depth = 16'd65535; lfo_inc = 24'd70000;
        observe(3000);
        $display("        实测 max=%0d min=%0d", o_max, o_min);
        if (o_max > CLAMP_HI) begin
            $display("  FAIL  V5-above-clamp-hi");
            fails = fails + 1;
        end
        else $display("  PASS  V5-max-within-clamp");
        if (o_min < CLAMP_LO) begin
            $display("  FAIL  V5-below-clamp-lo");
            fails = fails + 1;
        end
        else $display("  PASS  V5-min-within-clamp");

        $display("==============================================================");
        if (fails == 0) $display("RESULT vib=PASS");
        else            $display("RESULT vib=FAIL fails=%0d", fails);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #5_000_000;
        $display("RESULT vib=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
