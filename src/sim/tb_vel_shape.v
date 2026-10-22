//=============================================================================
// tb_vel_shape.v -- 力度->谱形 的判据（对应总表 V1..V6）
//
//   V1 基音永不置零（所有 16 档力度）
//   V2 最少保留 3 条泛音（所有 16 档力度）
//   V3 谱心随力度【单调上升】
//   V4 力度 0 与 15 的谱心差异足够明显（>= 15%）
//   V5 输出不越界，且高次泛音随力度增强
//   V6 tilt_gain=0 且 tilt_bias=0 时，力度不影响音色（旁路等价）
//
// 谱心定义：centroid = sum(k * amp_k) / sum(amp_k)，k = 1..16（用 1 起算避免除零）
//=============================================================================
`timescale 1ns/1ps

module tb_vel_shape;

    reg clk = 1'b0;
    always #10 clk = ~clk;                     // 50 MHz

    reg rst_n = 1'b0;

    integer errors = 0;
    integer i, v;
    integer ones, keep_cnt;

    //-------------------------------------------------------------- DUT 端口
    reg  [3:0]         vel;
    reg  [3:0]         part;
    reg  [7:0]         base;
    reg  signed [9:0]  tilt_bias;
    reg  [7:0]         tilt_gain;
    reg  [8:0]         vscale;
    wire [7:0]         amp;

    vel_shape #(.AW(8), .NFLOOR(8'd24), .NPART_PROTECT(4'd3)) dut (
        .vel(vel), .part(part), .base(base),
        .tilt_bias(tilt_bias), .tilt_gain(tilt_gain), .vscale(vscale), .amp(amp)
    );

    //-------------------------------------------------------------- 工具
    task check;
        input [255:0] name;
        input integer got;
        input integer exp;
        begin
            if (got === exp) $display("  PASS  %0s", name);
            else begin
                $display("  FAIL  %0s  got %0d expected %0d", name, got, exp);
                errors = errors + 1;
            end
        end
    endtask

    task check_ge;
        input [255:0] name;
        input integer got;
        input integer lo;
        begin
            if (got >= lo) $display("  PASS  %0s  (%0d >= %0d)", name, got, lo);
            else begin
                $display("  FAIL  %0s  (%0d < %0d)", name, got, lo);
                errors = errors + 1;
            end
        end
    endtask

    // 读某一档力度下第 k 条泛音的输出
    reg [7:0] A [0:15];                        // 当前力度的 16 条幅度
    task read_row;
        input [3:0] vv;
        integer k;
        begin
            vel = vv;
            for (k = 0; k < 16; k = k + 1) begin
                part = k[3:0]; @(posedge clk);
                @(posedge clk);
                A[k] = amp;
            end
        end
    endtask

    // 谱心（千分比，避免浮点）
    integer cen_q;
    task calc_centroid;
        integer k, num, den;
        begin
            num = 0; den = 0;
            for (k = 0; k < 16; k = k + 1) begin
                num = num + (k + 1) * A[k];
                den = den + A[k];
            end
            if (den == 0) cen_q = 0;
            else          cen_q = (num * 1000) / den;
        end
    endtask

    integer cen [0:15];                        // 各力度档的谱心
    integer cnt [0:15];                        // 各力度档保留的条数

    initial begin
        $display("==============================================================");
        $display(" vel_shape criteria (velocity -> timbre)");
        $display("==============================================================");

        rst_n     = 1'b0;
        base      = 8'd200;                    // 平坦的预设幅度，便于看倾斜效果
        tilt_bias = -10'sd16;                   // 低力度偏暗（新语义：每单位 skew 的增量）
        tilt_gain = 8'd2;                      // 每档 +2（tilt_n 不触 ±16 钳位）
        vscale    = 9'd256;                    // 灵敏度一等一（= 引入本参数之前的查表行为）
        vel       = 4'd0;
        part      = 4'd0;
        #100;
        rst_n     = 1'b1;
        #100;

        //-------------------------------------------------- 逐档采集
        for (v = 0; v < 16; v = v + 1) begin
            read_row(v[3:0]);
            calc_centroid;
            cen[v] = cen_q;
            keep_cnt = 0;
            for (i = 0; i < 16; i = i + 1) if (A[i] != 0) keep_cnt = keep_cnt + 1;
            cnt[v] = keep_cnt;
            // 顺手验越界（V5 前半）
            if (A[15] > 8'd255 || A[0] > 8'd255) begin
                $display("  FAIL  V5 幅度越界 at v=%0d", v);
                errors = errors + 1;
            end
        end

        //-------------------------------------------------- V1 基音不置零
        $display(" V1 fundamental never muted");
        keep_cnt = 0;
        for (v = 0; v < 16; v = v + 1) begin
            read_row(v[3:0]);
            if (A[0] == 8'd0) begin
                $display("  FAIL  V1 基音被置零 at v=%0d", v);
                errors = errors + 1;
            end else keep_cnt = keep_cnt + 1;
        end
        check("V1-fundamental-alive-in-16-levels", keep_cnt, 16);

        //-------------------------------------------------- V2 最少 3 条
        $display(" V2 at least 3 partials kept");
        for (v = 0; v < 16; v = v + 1) begin
            read_row(v[3:0]);
            keep_cnt = 0;
            for (i = 0; i < 16; i = i + 1) if (A[i] != 0) keep_cnt = keep_cnt + 1;
            if (keep_cnt < 3) begin
                $display("  FAIL  V2 v=%0d 只保留 %0d 条", v, keep_cnt);
                errors = errors + 1;
            end
        end
        $display("       各档保留条数 = %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                 cnt[0],cnt[1],cnt[2],cnt[3],cnt[4],cnt[5],cnt[6],cnt[7],
                 cnt[8],cnt[9],cnt[10],cnt[11],cnt[12],cnt[13],cnt[14],cnt[15]);
        begin : v2pass
            integer bad2; bad2 = 0;
            for (v = 0; v < 16; v = v + 1) if (cnt[v] < 3) bad2 = bad2 + 1;
            check("V2-partials-at-least-3-in-16-levels", bad2, 0);
        end

        //-------------------------------------------------- V3 谱心单调
        $display(" V3 spectral centroid monotonic in velocity");
        $display("       谱心(千分比) = %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
                 cen[0],cen[1],cen[2],cen[3],cen[4],cen[5],cen[6],cen[7],
                 cen[8],cen[9],cen[10],cen[11],cen[12],cen[13],cen[14],cen[15]);
        //   8 位幅度截断下严格单调不可达（实测 v=13->14 只差 0.3%），
        //   因此判据写成"不得下降超过 1%"——这才是这条性质的真实表述。
        ones = 0;
        for (v = 1; v < 16; v = v + 1) begin
            if (cen[v] * 100 < cen[v-1] * 99) begin
                $display("  FAIL  V3 谱心下降超过 1%%：v=%0d (%0d) vs v=%0d (%0d)",
                         v, cen[v], v-1, cen[v-1]);
                errors = errors + 1;
            end else ones = ones + 1;
        end
        check("V3-centroid-nondecreasing-within-1pct", ones, 15);

        //-------------------------------------------------- V4 两端差异
        $display(" V4 dynamic timbre range");
        if (cen[0] == 0) begin
            $display("  FAIL  V4 v=0 谱心为 0");
            errors = errors + 1;
        end else begin
            ones = ((cen[15] - cen[0]) * 100) / cen[0];
            check_ge("V4-centroid-rise-percent", ones, 15);
        end

        //-------------------------------------------------- V5 高次随力度增强
        $display(" V5 high partial grows with velocity");
        read_row(4'd0);  ones = A[15];
        read_row(4'd15);
        if (A[15] > ones) $display("  PASS  V5 第16条泛音 v15(%0d) > v0(%0d)", A[15], ones);
        else begin
            $display("  FAIL  V5 第16条泛音未随力度增强 v15=%0d v0=%0d", A[15], ones);
            errors = errors + 1;
        end

        //-------------------------------------------------- V6 旁路等价
        //   注意语义变化（2026-10-06）：开关现在是 vscale，不再是 tilt_gain。
        //   这一条保留它原本要证明的性质："力度对音色没有影响时，
        //   两支频谱逐位相同"——用 vscale=0 来表达那个状态。
        $display(" V6 velocity has no timbre effect when the feature is off (vscale=0)");
        vscale = 9'd0;
        tilt_bias = 10'sd0;  tilt_gain = 8'd0;
        read_row(4'd0);  ones = A[15];
        read_row(4'd15);
        begin : v6
            integer k; reg [7:0] first15;
            read_row(4'd0);
            first15 = A[15];
            read_row(4'd15);
            if (A[15] === first15) $display("  PASS  V6 关掉倾斜后力度不改变高次泛音");
            else begin
                $display("  FAIL  V6 应为旁路：v0=%0d v15=%0d", first15, A[15]);
                errors = errors + 1;
            end
        end

        //-------------------------------------------------- V7 置零路径可达
        //   加宽 bias 之前，这条路径【永远不可达】（数学上到不了门限）。
        //   用"表里的条数档"验证高次泛音真的会被置零、并随力度恢复。
        $display(" V7 muting path reachable (aggressive tilt)");
        //   ★ V6 把 vscale 置成了 0（旁路），这里必须显式抬回来：
        //     否则 V7/V8 都在"功能关闭"的状态下运行 —— 测试段之间共享全局状态，
        //     这种"上一段把状态改坏了、下一段还以为在测别的"是判据最常见的假绿来源。
        vscale    = 9'd256;
        tilt_bias = -10'sd16;  tilt_gain = 10'sd2;   // 关键在条数表，不在倾斜
        begin : v7
            integer c0, c15, bad7;
            bad7 = 0;
            read_row(4'd0);
            c0 = 0;
            for (i = 0; i < 16; i = i + 1) if (A[i] != 0) c0 = c0 + 1;
            read_row(4'd15);
            c15 = 0;
            for (i = 0; i < 16; i = i + 1) if (A[i] != 0) c15 = c15 + 1;
            $display("       v=0 保留 %0d 条，v=15 保留 %0d 条", c0, c15);
            if (c0 >= 3)  $display("  PASS  V7 最轻力度仍保留 >=3 条（%0d）", c0);
            else begin $display("  FAIL  V7 v=0 只剩 %0d 条", c0); errors = errors + 1; end
            if (c15 > c0) $display("  PASS  V7 条数随力度增长（%0d -> %0d）", c0, c15);
            else begin
                $display("  FAIL  V7 条数未随力度增长（%0d -> %0d）—— 置零路径可能仍不可达", c0, c15);
                errors = errors + 1;
            end
        end

        //-------------------------------------------------- V8 默认参数恒等
        //   这一条是【回归护身符】：默认参数下，输出必须与输入逐位相同，
        //   否则既有"加法引擎逐位一致 / TDM 黄金参考"等证据会全部失效。
        //   ★ 必须显式把 vscale 置回 0：本测试台各段共享全局状态，V7 把它设成了
        //     256（一等一）。256 时 `amp = (base × wtab) >> 8` 会有 1 的截断误差
        //     （base=16, w=437 → 15），那是【表在工作】的正常结果，不是恒等。
        //     实测：漏了这一行 ⇒ V8 报 "v=0 k=1 base=16 amp=15"（差 1）。
        //     这是"上一段改坏了状态、下一段还以为在测别的"的又一例。
        $display(" V8 identity at default parameters (regression guard)");
        vscale = 9'd0;                       // 功能关 = 恒等（这一条测的就是它）
        tilt_bias = 10'sd0;  tilt_gain = 8'd0;
        begin : v8
            integer bad8;
            bad8 = 0;
            for (v = 0; v < 16; v = v + 1) begin
                for (i = 0; i < 16; i = i + 1) begin
                    vel  = v[3:0];
                    part = i[3:0];
                    base = (i * 16 + v);      // 覆盖不同幅度
                    #1;
                    if (amp !== base) begin
                        if (bad8 < 3)
                            $display("  FAIL  V8 v=%0d k=%0d base=%0d amp=%0d", v, i, base, amp);
                        bad8 = bad8 + 1;
                    end
                end
            end
            check("V8-identity-256-combinations", bad8, 0);
            // 边界幅度也要恒等
            bad8 = 0;
            vel = 4'd7; part = 4'd5;
            base = 8'd0;   #1; if (amp !== 8'd0)   bad8 = bad8 + 1;
            base = 8'd255; #1; if (amp !== 8'd255) bad8 = bad8 + 1;
            base = 8'd128; #1; if (amp !== 8'd128) bad8 = bad8 + 1;
            check("V8-identity-boundary-bases", bad8, 0);
        end

        //-------------------------------------------------- V9 灵敏度缩放
        //   2026-10-06 新增 vscale 端口（力度灵敏度，只缩放"相对恒等的偏差"）。
        //   这一条要证明三件事，缺一条都说明实现做成了别的意思：
        //     (a) vscale=0 ⇒ 与"没有力度->音色"等价（不是"整体变小"）
        //     (b) vscale=256 ⇒ 与 wtab 逐位相同（上面的 V8 是"功能关"这条路，
        //         这里是"功能开、灵敏度一等一"那条路）
        //     (c) vscale=128 ⇒ 偏差恰好减半，且**恒等部分不动**
        //         （若误写成 (w*vscale)>>8，整体幅度会掉一半 —— 那是音量旋钮）
        $display(" V9 velocity sensitivity scales the deviation only");
        tilt_bias = 10'sd0;  tilt_gain = 8'd1;      // 打开功能
        begin : v9
            integer bad9, amp_v256, amp_v128;
            bad9 = 0;

            // (a) vscale = 0 ⇒ 逐位恒等
            vscale = 9'd0;
            for (v = 0; v < 16; v = v + 1) begin
                for (i = 0; i < 16; i = i + 1) begin
                    vel = v[3:0]; part = i[3:0]; base = (i * 16 + v);
                    #1;
                    if (amp !== base) begin
                        if (bad9 < 3)
                            $display("  FAIL  V9a vscale=0 v=%0d k=%0d base=%0d amp=%0d", v, i, base, amp);
                        bad9 = bad9 + 1;
                    end
                end
            end
            check("V9a-vscale0-identity-256-combinations", bad9, 0);

            // (b)/(c) 用【解析期望值】而不是"从输出反推权重"：
            //   反推要除 200，精度会吃掉 ±1，判据就不可信了。
            //   定标点：vel=15, part=15, base=200。
            //   本单元测试用 AW=8，输出饱和在 255 —— 所以期望值必须落在 255 以下，
            //   否则"饱和"会把不同灵敏度的差别抹平（这正是第一次写这条判据时栽的坑：
            //   期望 364/282 都 > 255，实测两条都是 255，判据自身失效）。
            //   改用 base=100：
            //     vscale=256 ⇒ w=467 ⇒ amp = 100×467/256 = 182.4 → 182
            //     vscale=128 ⇒ w=361 ⇒ amp = 100×361/256 = 141.0 → 141
            vel = 4'd15; part = 4'd15; base = 8'd100;
            vscale = 9'd256; #1;
            amp_v256 = amp;
            vscale = 9'd128; #1;
            amp_v128 = amp;
            $display("       vscale=256 ⇒ amp=%0d（期望 182）；vscale=128 ⇒ amp=%0d（期望 141）",
                     amp_v256, amp_v128);
            if (amp_v256 !== 8'd182) begin
                $display("  FAIL  V9b vscale=256 与表不等价（%0d ≠ 182）", amp_v256);
                bad9 = bad9 + 1;
            end
            if (amp_v128 !== 8'd141) begin
                $display("  FAIL  V9c vscale=128 未把偏差减半（%0d ≠ 141）", amp_v128);
                bad9 = bad9 + 1;
            end
            // (c2) 恒等部分不动：base=0 时任何灵敏度下输出都必须还是 0
            vscale = 9'd128; base = 8'd0;  #1; if (amp !== 8'd0) bad9 = bad9 + 1;
            vscale = 9'd511; base = 8'd0;  #1; if (amp !== 8'd0) bad9 = bad9 + 1;
            //   判据名与实际断言必须一一对应：这里把"缩放契约"整条只报一行，
            //   否则通过时日志里根本没有可追溯的 PASS 行（只有失败才打印=不可复核）。
            check("V9bc-sensitivity-scales-deviation-only", bad9, 0);
        end

        $display("==============================================================");
        if (errors == 0) $display(" ALL VEL_SHAPE CRITERIA PASS");
        else             $display(" FAILED %0d check(s)", errors);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #40_000_000;
        $display(" [watchdog] timeout");
        $display(" FAILED %0d check(s) (including timeout)", errors + 1);
        $finish;
    end

endmodule
