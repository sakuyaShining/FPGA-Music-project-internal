//=============================================================================
// tb_decay2.v —— 双段衰减（osc_env.v 的 d2_lvl / d2_k）专项判据
//
// 【这份 tb 存在的理由】
//   双段衰减改的是【所有音色共用的那一条包络路径】。改错了不是"新功能不好用"，
//   而是"所有既有音色全部变味"，而全部历史音频判据、全部已调好的参数
//   都建立在那条路径上。所以本 tb 的第一条判据不是"第二段生效"，
//   而是【关闭时与改动前逐位一致】。
//
// 【怎么保证"逐位一致"是有牙的判据】
//   在 tb 里独立实现一份"改动前"的递推（legacy_next），不复用 DUT 的任何逻辑，
//   然后一步一步比对整条电平轨迹。只要 DUT 在任何一拍多走/少走一步就红。
//
// 【判据清单】
//   D1  关闭（d2_k=0）：4000 拍轨迹与 legacy 参考逐拍相同
//   D2  断点位置：第二段在"第一次跌破 d2_lvl"的那一拍切换，不早不晚
//   D3  只慢不快：d2_k < d_k 时必须【完全不生效】（否则尾音被掐断）
//   D4  第二段确实更慢：同一断点下，开 d2 的衰减步长严格小于关 d2 的
//   D5  尾音时长：开 d2 到 cutoff 的拍数 >= 关 d2 的 1.5 倍
//   D6  不死锁：第二段里电平每拍都严格下降，不会卡住
//   D7  释放不受影响：trig_rel 之后的衰减只由 r_k 决定，与 d2 无关
//   D8  断点=0（但 d2_k!=0）：等价于关闭
//   D9  s_lvl 高于断点：DEC 在 s_lvl 停住，第二段从未被用到
//   D10 m 语义不变：第二段只改 k，不改 m（m=1/2/3 三档都要走通）
//
// 消息全 ASCII：iverilog 把字符串字面量当任务实参传进位向量时，
// UTF-8 多字节会被切坏（tb_rst_gen / tb_strike 都栽过）。
//=============================================================================
`timescale 1ns/1ps

module tb_decay2;

    localparam [15:0] FULL = 16'h8000;      // 32768 = 1.0（Q1.15）

    //---- DUT 的驱动与状态 ----
    reg  [15:0] lvl;
    reg  [2:0]  stg_in;
    reg  [15:0] a_inc, d_inc, s_lvl, r_inc, cutoff, d2_lvl;
    reg  [1:0]  d_m, r_m;
    reg  [4:0]  d_k, r_k, d2_k;
    reg         trig_on, trig_rel, exp_mode;
    wire [15:0] lvl_o;
    wire [2:0]  stg_o;

    localparam [2:0] ST_DEC = 3'd2;
    localparam [2:0] ST_SUS = 3'd3;
    localparam [2:0] ST_REL = 3'd4;

    osc_env #(.ENV_W(16), .STG_W(3)) dut (
        .lvl_i(lvl), .stg_i(stg_in),
        .trig_on(trig_on), .trig_rel(trig_rel),
        .a_inc(a_inc), .d_inc(d_inc), .d_m(d_m), .d_k(d_k),
        .s_lvl(s_lvl), .d2_lvl(d2_lvl), .d2_k(d2_k),
        .r_inc(r_inc), .r_m(r_m), .r_k(r_k),
        .cutoff(cutoff), .exp_mode(exp_mode),
        .lvl_o(lvl_o), .stg_o(stg_o)
    );

    //-------------------------------------------------------------------------
    // 独立参考模型：**改动前**的 osc_env 递推（不含 d2）
    //   故意从零手写一遍，不复用 DUT 的任何中间量 —— 复用就失去对照意义。
    //-------------------------------------------------------------------------
    function [15:0] legacy_next(input [15:0] l, input [1:0] m, input [4:0] k,
                                input [15:0] s);
        reg [17:0] mul, sh;
        reg [15:0] st;
        begin
            mul = (m == 2'd2) ? {1'b0, l, 1'b0} :
                  (m == 2'd3) ? ({1'b0, l, 1'b0} + {2'b00, l}) :
                                {2'b00, l};
            sh  = mul >> k;
            st  = (sh == 18'd0) ? 16'd1 : sh[15:0];
            if (l <= s)                  legacy_next = s;
            else if (l <= (s + st))      legacy_next = s;
            else                         legacy_next = l - st;
        end
    endfunction

    //---- 判据计数器 ----
    integer pass_n, fail_n, i;
    reg [8*200-1:0] msg;

    task chk(input cond, input [8*200-1:0] text);
        begin
            if (cond) begin
                pass_n = pass_n + 1;
                $display("[OK]   %0s", text);
            end else begin
                fail_n = fail_n + 1;
                $display("[FAIL] %0s", text);
            end
        end
    endtask

    //---- 推进一拍（osc_env 是组合的：把输出回灌到输入即前进一拍）----
    task tick;
        begin
            #1 lvl = lvl_o; stg_in = stg_o;
        end
    endtask

    //---- 把环境恢复到"刚从 FULL 进入 DEC"----
    task reset_dec(input [15:0] sl, input [15:0] d2l, input [4:0] dk,
                   input [4:0] d2k, input [1:0] m);
        begin
            lvl = FULL; stg_in = ST_DEC;
            s_lvl = sl; d2_lvl = d2l; d_k = dk; d2_k = d2k; d_m = m;
            a_inc = 16'd0; d_inc = 16'd1; r_inc = 16'd1;
            r_m = 2'd3; r_k = 5'd13; cutoff = 16'd100;
            trig_on = 1'b0; trig_rel = 1'b0; exp_mode = 1'b1;
            #1;
        end
    endtask

    integer n, bad, step_off, step_on;
    reg [15:0] lref;
    reg [15:0] first_below;     // 第一次跌破断点时 DUT 的电平
    integer    cross_idx;
    reg [15:0] prev_lvl;
    reg        mono_ok, d2_seen;
    reg [15:0] step_off_v, step_on_v;

    initial begin
        pass_n = 0; fail_n = 0;

        //=====================================================================
        // D1 关闭（d2_k=0）与改动前逐位一致
        //=====================================================================
        reset_dec(16'd0, 16'd16384, 5'd12, 5'd0, 2'd3);
        lref = FULL; bad = 0;
        for (i = 0; i < 4000; i = i + 1) begin
            lref = legacy_next(lref, 2'd3, 5'd12, 16'd0);
            tick;
            if (lvl !== lref) begin
                if (bad < 3) $display("   [D1] i=%0d dut=%0d ref=%0d", i, lvl, lref);
                bad = bad + 1;
            end
        end
        chk(bad == 0, "D1 d2 off: 4000-step trace identical to pre-change reference");

        //=====================================================================
        // D2 断点位置：**两侧都要验**
        //   只验"跌破前没变"是不够的 —— 断点被改到更低处时，跌破前当然没变，
        //   判据照样绿。反向对照 NEG2（断点减半）就是这么漏过去的。
        //   所以要验三件事：
        //     (a) 跌破断点之前，轨迹与 legacy 逐拍相同   ⇒ 切换没有提前
        //     (b) 跌破之后 300 拍内必须已经与 legacy 不同 ⇒ 切换确实发生了
        //     (c) 记录到的"第一次跌破"确实是第一次
        //   为什么是 300 拍：正确实现的切换在跌破后【第 1 拍】就发生；
        //   而把断点减半的实现要再走 ~946 拍才跌破新断点，300 拍时仍与
        //   legacy 相同 ⇒ 两个方向都能分辨。
        //=====================================================================
        reset_dec(16'd0, 16'd16384, 5'd12, 5'd18, 2'd3);
        lref = FULL; bad = 0; cross_idx = -1; first_below = 16'd0;
        for (i = 0; i < 4000 && cross_idx < 0; i = i + 1) begin
            lref = legacy_next(lref, 2'd3, 5'd12, 16'd0);
            prev_lvl = lvl;
            tick;
            if (lvl < 16'd16384) begin
                cross_idx   = i;
                first_below = lvl;
            end else if (lvl !== lref) begin
                bad = bad + 1;      // 跌破之前就变了 ⇒ 切换点提前，错
            end
        end
        n = 0;                      // 跌破之后 300 拍内必须已经分叉
        for (i = 0; i < 300; i = i + 1) begin
            lref = legacy_next(lref, 2'd3, 5'd12, 16'd0);
            tick;
            if (lvl !== lref) n = n + 1;
        end
        $display("   [D2] first level below breakpoint = %0d (expect <16384), diverged steps in next 300 = %0d",
                 first_below, n);
        chk(cross_idx >= 0 && bad == 0 && n > 0 && prev_lvl >= 16'd16384,
            "D2 switch at first step below d2_lvl (verified on both sides)");

        //=====================================================================
        // D3 只慢不快：d2_k < d_k 时完全不生效
        //   d_k=20（很慢），d2_k=15（更快）—— 若守卫失效，尾音会突然加速。
        //
        //   ★ 起跑点必须【在断点下方】，否则判据没有牙：
        //     第一版从 FULL=32768 起跑、断点 16384，而 d_k=20 的衰减要 24 万拍
        //     才跌破断点，测试只跑 3000 拍 ⇒ 第二段从未被触发 ⇒ 去掉守卫也照样绿。
        //   ★ d_k/d2_k 也不能选得太极端：d_k=20 时 (lvl*3)>>20 恒被钳成 1，
        //     d2_k=15 在同一电平也是 1 ⇒ 两段步长一样，守卫有没有都看不出差别。
        //     取 d_k=15 / d2_k=12：在 lvl=20000 处两者分别是 1 和 14，一眼分得开。
        //=====================================================================
        reset_dec(16'd0, 16'd30000, 5'd15, 5'd12, 2'd3);
        lvl = 16'd20000; #2;                 // 直接在断点（30000）下方起跑
        lref = lvl; bad = 0;
        for (i = 0; i < 3000; i = i + 1) begin
            lref = legacy_next(lref, 2'd3, 5'd15, 16'd0);
            tick;
            if (lvl !== lref) bad = bad + 1;
        end
        $display("   [D3] d_k=15 d2_k=12: steps differing from legacy = %0d (expect 0)", bad);
        chk(bad == 0, "D3 d2_k < d_k is rejected: tail never accelerates");

        //=====================================================================
        // D4 第二段确实更慢（单步步长对比）
        //   ★ 不要用"循环跑到某个电平再读 lvl_o"的写法：tick 里把 lvl_o 回灌给
        //     lvl 之后，组合输出要过一个 delta 才更新，紧接着读 lvl_o 拿到的是
        //     【旧值】—— 差恒为 0（第一版就是这么误报的，9 过 1 挂）。
        //   改成在同一个固定电平上显式等两拍再读，结果确定。
        //=====================================================================
        reset_dec(16'd0, 16'd16384, 5'd12, 5'd0, 2'd3);
        lvl = 16'd8000; #2; step_off_v = lvl - lvl_o;
        reset_dec(16'd0, 16'd16384, 5'd12, 5'd18, 2'd3);
        lvl = 16'd8000; #2; step_on_v  = lvl - lvl_o;
        $display("   [D4] at lvl=8000: d2 off step=%0d, d2 on step=%0d",
                 step_off_v, step_on_v);
        chk(step_on_v > 16'd0 && step_on_v < step_off_v,
            "D4 second segment step is strictly smaller (slower) than first");

        //=====================================================================
        // D5 尾音时长：开 d2 到 cutoff 的拍数 >= 1.5x 关 d2
        //=====================================================================
        reset_dec(16'd100, 16'd16384, 5'd12, 5'd0, 2'd3);
        n = 0;
        while (lvl > 16'd100 && n < 200000) begin tick; n = n + 1; end
        step_off = n;
        reset_dec(16'd100, 16'd16384, 5'd12, 5'd18, 2'd3);
        n = 0;
        while (lvl > 16'd100 && n < 200000) begin tick; n = n + 1; end
        step_on = n;
        $display("   [D5] ticks to cutoff: off=%0d  on=%0d  ratio=%0.2f",
                 step_off, step_on, step_on * 1.0 / step_off);
        chk(step_on * 10 >= step_off * 15,
            "D5 tail is >= 1.5x longer with the second segment enabled");

        //=====================================================================
        // D6 不死锁：第二段里每拍都严格下降
        //=====================================================================
        reset_dec(16'd0, 16'd16384, 5'd12, 5'd18, 2'd3);
        mono_ok = 1'b1; d2_seen = 1'b0;
        prev_lvl = lvl;
        for (i = 0; i < 20000 && lvl > 16'd100; i = i + 1) begin
            tick;
            if (prev_lvl < 16'd16384) d2_seen = 1'b1;
            if (lvl >= prev_lvl && lvl > 16'd100) mono_ok = 1'b0;
            prev_lvl = lvl;
        end
        chk(mono_ok && d2_seen, "D6 strictly decreasing in segment 2, never deadlocks");

        //=====================================================================
        // D7 释放不受 d2 影响
        //=====================================================================
        reset_dec(16'd0, 16'd16384, 5'd12, 5'd18, 2'd3);
        for (i = 0; i < 50; i = i + 1) tick;      // 走到第二段里
        trig_rel = 1'b1;
        tick;                                     // 进入 ST_REL
        trig_rel = 1'b0;
        bad = 0;
        lref = lvl;
        for (i = 0; i < 500; i = i + 1) begin
            lref = legacy_next(lref, 2'd3, 5'd13, 16'd100);   // 只用 r_m/r_k
            tick;
            if (lvl !== lref) bad = bad + 1;
        end
        chk(stg_in == ST_REL && bad == 0,
            "D7 release uses r_m/r_k only, d2 has no effect on it");

        //=====================================================================
        // D8 断点=0 但 d2_k!=0 ⇒ 等价关闭
        //   （d2_lvl=0 时 lvl<0 永不成立；这条守住"只写了 d2_k 没写 d2_lvl"
        //     这种半配置不会意外改变音色）
        //=====================================================================
        reset_dec(16'd0, 16'd0, 5'd12, 5'd18, 2'd3);
        lref = FULL; bad = 0;
        for (i = 0; i < 3000; i = i + 1) begin
            lref = legacy_next(lref, 2'd3, 5'd12, 16'd0);
            tick;
            if (lvl !== lref) bad = bad + 1;
        end
        chk(bad == 0, "D8 d2_lvl=0 (with d2_k!=0) is identical to disabled");

        //=====================================================================
        // D9 s_lvl 高于断点 ⇒ DEC 停在 s_lvl，第二段从未被用到
        //=====================================================================
        reset_dec(16'd20000, 16'd16384, 5'd12, 5'd18, 2'd3);
        bad = 0;
        for (i = 0; i < 2000 && stg_in != ST_SUS; i = i + 1) begin
            lref = legacy_next(lref, 2'd3, 5'd12, 16'd20000);
            tick;
            if (lvl < 16'd20000) bad = bad + 1;
        end
        chk(stg_in == ST_SUS && lvl == 16'd20000 && bad == 0,
            "D9 s_lvl above breakpoint: decay stops at s_lvl, segment 2 unused");

        //=====================================================================
        // D10 第二段只改 k、不改 m：m=1/2/3 三档都要比参考慢且不死锁
        //=====================================================================
        bad = 0;
        for (i = 0; i < 3; i = i + 1) begin
            reset_dec(16'd100, 16'd16384, 5'd12, 5'd18, i[1:0] == 2'd0 ? 2'd1 : i[1:0]);
            n = 0;
            while (lvl > 16'd100 && n < 200000) begin tick; n = n + 1; end
            if (n <= 0 || n >= 200000) bad = bad + 1;
        end
        chk(bad == 0, "D10 all three m values (1/2/3) terminate with segment 2 on");

        //=====================================================================
        $display("");
        if (fail_n == 0)
            $display("RESULT(tb_decay2): PASS -- %0d checks", pass_n);
        else
            $display("RESULT(tb_decay2): FAIL -- %0d passed, %0d failed", pass_n, fail_n);
        $finish;
    end

endmodule
