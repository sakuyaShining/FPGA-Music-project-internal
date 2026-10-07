//=============================================================================
// tb_glide.v —— 滑音（portamento）不变量判据
//
// 【为什么必须单独有这一条（2026-10-07 发现）】
//   本仓此前**没有任何滑音判据**，而出货默认配置下滑音是**不可听的**：
//     · CTRL(0x00) 自举值 = 0x02 ⇒ bit2 = 1（GLIDE_EN 开）
//     · GLIDE_STEP(0x35/0x36) 自举值 = 0 ⇒ 速率 0 ⇒ gq 永不衰减
//   ⇒ **默认无滑音**。因此任何既有音频判据都不会因为滑音逻辑有 bug 而变红。
//   换句话说：滑音是"开着但没速率、也没人验"的状态。
//   这一条把滑音的行为单独钉住，避免它长期处于"未验证"。
//
// 【被测语义（2026-10-07 **逐行核对 pitch_mod.v 后**重写，第一版我写错了三条）】
//
//   衰减（sample_en 门控，每样本一次）—— 注意两条**设计如此**的行为：
//       gq > 0 : gq <= (gq >  step) ? gq - step : 0
//       gq < 0 : gq <= (gq < -step) ? gq + step : 0
//     ★ **衰减不受 glide_en 门控**（注释明写"关滑音时也要照常走完，
//       否则残留偏移会永久卡住"）⇒ 关掉再打开不会残留旧偏移。
//     ★ `GLIDE_CUT` **是死参数**：衰减式 `(gq > stp) ? gq-stp : 0` 本身就
//       **精确收敛到 0**（不会卡在 ±1），所以那个"低于阈值直接归零"的机制
//       从未被使用。grep 全文件：GLIDE_CUT 只在参数声明(45)与文档(22/45)出现，
//       **没有任何一处读它**。⇒ 它不是缺陷（精确收敛已达成），但是**未使用的参数**，
//       容易误导读者以为有 CUT 行为。（第一版判据就照文档写了 CUT 用例 ⇒ 假失败。）
//
//   输出（应用处门控）：
//       gq_sel  = glide_en ? gq_eff : 0
//       vib_sel = vib_en   ? vib_raw : 0
//       poff    = clamp(gq_sel + vib_sel, CLAMP_LO, CLAMP_HI)
//     ⇒ **glide_en=0 时 poff 恒为 0**（即使 gq 内部非零）。
//
// 【判据】
//   G1 glide_en=0 ⇒ **poff 恒为 0**（门控在应用处；gq 内部仍照常衰减）
//   G2 glide_step=0 ⇒ 不衰减：初值原样出现在 poff 上（**这是出货默认配置**）
//   G3 step>0、gq0>0 ⇒ 每样本减 step，**耗时精确等于 ceil(gq0/step)**
//   G4 step>0、gq0<0 ⇒ 对称
//   G5 无论初值多小，最终**精确到 0**（不卡在 ±1）—— 这才是"无残余抖动"的真正保证
//   G6 收敛后稳定停在 0（不抖动、不反向）
//   G7 关滑音期间 gq **仍在衰减**：关掉→等够→再打开，poff 不应残留旧偏移
//
// 【判据不循环】耗时期望值由测试台按 |gq0|/step **独立算出**（独立循环模拟），
//   不引用 RTL 内部信号；只读输出 `poff`。
//=============================================================================
`timescale 1ns/1ps

module tb_glide;

    localparam integer NG = 32;
    localparam integer QW = 18;
    //   注：原来这里还有个 `localparam GLIDE_CUT = 24`，随 pitch_mod 的参数删除
    //       一并向去掉（它只是用来打印，不参与任何判据）。

    reg clk = 1'b0;
    always #10 clk = ~clk;
    reg rst_n = 1'b0;

    //  被测模块的控制输入
    reg                  sample_en;
    reg  [23:0]          lfo_inc   = 24'd0;
    reg  [15:0]          vib_depth = 16'd0;
    reg  [15:0]          glide_step;
    reg                  vib_en    = 1'b0;      // 颤音全程关，只验滑音
    reg                  glide_en;
    reg                  gw_en;
    reg  [4:0]           gw_note;
    reg  signed [QW-1:0] gw_val;
    reg  [4:0]           rd_note;
    wire signed [QW-1:0] poff;

    //   ★ 2026-10-07：`GLIDE_CUT` 已从 pitch_mod 删除（死参数，见该文件注释）。
    //     本测试台原先 `.GLIDE_CUT(GLIDE_CUT)` 传参，现已一并去掉。
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

    //   写一个组的滑音初值
    task set_gq;
        input [4:0]           n;
        input signed [QW-1:0] v;
        begin
            gw_note = n; gw_val = v; gw_en = 1'b1;
            @(posedge clk);
            gw_en = 1'b0;
            repeat (2) @(posedge clk);
        end
    endtask

    //   走 k 个样本周期（每个周期发一次 sample_en）
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

    integer v, n_used;

    initial begin
        $display("==============================================================");
        $display(" 滑音（portamento）不变量判据");
        $display("==============================================================");

        fails = 0; sample_en = 1'b0; glide_step = 16'd0;
        glide_en = 1'b0; gw_en = 1'b0; gw_note = 5'd0; gw_val = 18'sd0;
        rd_note = 5'd3; n_used = 3;
        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);

        //--------------------------------------------------------------- G1
        $display(" G1 glide_en=0 ⇒ poff 恒为 0（门控在应用处，gq 内部仍照常衰减）");
        glide_step = 16'd1000; glide_en = 1'b0;
        set_gq(n_used[4:0], 18'sd100000);
        run_samples(50);
        check("G1-disabled-poff-zero", poff, 0);

        //--------------------------------------------------------------- G2
        $display(" G2 glide_step=0 ⇒ 不衰减：初值原样出现在 poff 上（出货默认配置）");
        glide_step = 16'd0; glide_en = 1'b1;
        set_gq(n_used[4:0], 18'sd100000);
        run_samples(50);
        check("G2-zero-step-holds", poff, 100000);

        //--------------------------------------------------------------- G3
        $display(" G3 step>0、gq0>0 ⇒ 每样本减 step，耗时 == ceil(gq0/step)");
        glide_step = 16'd1000; glide_en = 1'b1;
        //   期望耗时：独立模拟一遍 RTL 的衰减式（不引用内部信号）
        begin : g3exp
            integer g, steps;
            g = 100000; steps = 0;
            while (g != 0) begin
                if (g > 1000) g = g - 1000; else g = 0;
                steps = steps + 1;
            end
            check("G3-expected-steps-computed", steps, 100);
        end
        set_gq(n_used[4:0], 18'sd100000);
        run_samples(99);
        check("G3-after-99-samples-nonzero", (poff != 0), 1);
        run_samples(1);                       // 第 100 个样本
        check("G3-after-100-samples-zero", poff, 0);
        //   收敛后保持稳定（不抖动、不反向）
        run_samples(20);
        check("G6-stable-at-zero", poff, 0);

        //--------------------------------------------------------------- G4
        $display(" G4 step>0、gq0<0 ⇒ 每样本加 step，耗时对称");
        set_gq(n_used[4:0], -18'sd100000);
        run_samples(99);
        check("G4-after-99-samples-nonzero", (poff != 0), 1);
        run_samples(1);
        check("G4-after-100-samples-zero", poff, 0);
        run_samples(20);
        check("G4-stable-at-zero", poff, 0);

        //--------------------------------------------------------------- G5
        $display(" G5 小初值也精确收敛到 0（不卡在 ±1）—— 这才是无残余抖动的真保证");
        //   故意选 |gq0| 不是 step 的整数倍，制造"余数"情形
        glide_step = 16'd7; glide_en = 1'b1;
        set_gq(n_used[4:0], 18'sd20);         // 20 / 7 = 2 余 6
        run_samples(3);                       // 7→13→6→0
        check("G5-remainder-converges-exactly", poff, 0);
        set_gq(n_used[4:0], -18'sd20);
        run_samples(3);
        check("G5-neg-remainder-converges-exactly", poff, 0);

        //   极小初值（比任何"阈值"都小）也必须到一个样本内归零
        glide_step = 16'd1000; glide_en = 1'b1;
        set_gq(n_used[4:0], 18'sd1);
        run_samples(1);
        check("G5-tiny-value-zero-in-1-sample", poff, 0);

        //--------------------------------------------------------------- G7
        $display(" G7 关滑音期间 gq 仍在衰减（注释明写：否则残留偏移会永久卡住）");
        glide_step = 16'd10000; glide_en = 1'b0;
        set_gq(n_used[4:0], 18'sd100000);
        run_samples(20);                      // 关着衰减 20 步 → 内部应为 0
        check("G7-during-off-poff-zero", poff, 0);
        glide_en = 1'b1;                       // 再打开
        run_samples(2);
        check("G7-reenable-no-residue", poff, 0);

        $display("==============================================================");
        if (fails == 0) $display("RESULT glide=PASS");
        else            $display("RESULT glide=FAIL fails=%0d", fails);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #2_000_000;
        $display("RESULT glide=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
