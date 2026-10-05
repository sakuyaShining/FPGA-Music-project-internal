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
    wire [7:0]         amp;

    vel_shape #(.AW(8), .NFLOOR(8'd24), .NPART_PROTECT(4'd3)) dut (
        .clk(clk), .rst_n(rst_n), .vel(vel), .part(part), .base(base),
        .tilt_bias(tilt_bias), .tilt_gain(tilt_gain), .amp(amp)
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
        tilt_bias = -10'sd40;                   // 低力度偏暗
        tilt_gain = 8'd8;                      // 每档 +8
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
        ones = 0;
        for (v = 1; v < 16; v = v + 1) begin
            if (cen[v] <= cen[v-1]) begin
                $display("  FAIL  V3 谱心非单调：v=%0d (%0d) <= v=%0d (%0d)",
                         v, cen[v], v-1, cen[v-1]);
                errors = errors + 1;
            end else ones = ones + 1;
        end
        if (ones == 15) $display("  PASS  V3 15 次相邻比较全部递增");

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
        $display(" V6 gain=0 bias=0 => velocity has no timbre effect");
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
        //   用激进参数把高次泛音压到门限以下，验证"条数"真的会随力度增长。
        $display(" V7 muting path reachable (aggressive tilt)");
        tilt_bias = -10'sd300;  tilt_gain = 10'sd28;
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
