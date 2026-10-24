`timescale 1ns/1ps
//=============================================================================
// tb_audio_clk_en —— 音频时钟链判据（采样率定稿的守门人）
//
// 为什么必须做这一台：
//   采样率是整个音频链路里唯一"错了就整体错"的参数。`audio_clk_en.v` 的注释
//   引用过 "tb_audio_clk_en 已补 S6 断言"，但**这个文件从来不存在** ——
//   也就是说采样率一直没有判据，只靠注释和人工数拍子。
//   更糟的是注释本身是旧的（写 18 分频 / 46875 Hz），而产品顶层传的是 16 分频。
//
// 定稿结论（2026-10-25）：
//   **52734.375 Hz = 27 MHz ÷ 16 ÷ 32**，整数分频、零抖动。
//   48 kHz 需要 PLL 或换晶振，而本项目设计纪律是"不用 PLL"，故不采用。
//
// 判据（两个配置都要过）：
//   A. DIV_BCK=16 —— 产品配置（tdm_top / tdm_top_owned / tdm_top_rh）
//   B. DIV_BCK=18 —— 旧配置（osc_additive_top 仍在用，不能悄悄坏掉）
//   对每个配置分别量：
//     [1] sample_en 周期 == DIV_BCK × BCK_PER_LRCK
//     [2] lrck 完整周期 == 同上（量【完整周期】，不是量翻转间隔 ——
//         历史 bug 就是把翻转率当成字时钟，导致整体低一个八度）
//     [3] lrck 高电平宽度 == (BCK_PER_LRCK/2) × DIV_BCK（50% 占空比）
//     [4] bck 引脚周期 == DIV_BCK
//     [5] 由实测拍数反算采样率，与 27e6/周期 一致
//     [6] 【对齐契约】每个 sample_en 必须与 lrck 的 1→0 翻转、以及那一拍
//         bck_en 同拍（i2s_tx 靠这条把"新样本装载"对到"左声道帧起始"）。
//         只查周期查不出这条：把 sample_en 挪到半周期末，采样率不变、
//         周期判据全绿，但整帧错位半个字 —— 必须单独守。
//=============================================================================
module tb_audio_clk_en;

    // 仿真时钟与真实 27 MHz 无关：这里只数【拍数】，不数时间
    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;

    //---- A：产品配置 DIV_BCK=16 → 27e6/512 = 52734.375 Hz ----
    localparam integer DA = 16;
    wire a_bck_en, a_bck, a_lrck, a_se;
    audio_clk_en #(.DIV_BCK(DA), .BCK_PER_LRCK(32)) ua (
        .clk(clk), .rst_n(rst_n),
        .bck_en(a_bck_en), .bck(a_bck), .lrck(a_lrck), .sample_en(a_se)
    );

    //---- B：旧配置 DIV_BCK=18 → 27e6/576 = 46875 Hz ----
    localparam integer DB = 18;
    wire b_bck_en, b_bck, b_lrck, b_se;
    audio_clk_en #(.DIV_BCK(DB), .BCK_PER_LRCK(32)) ub (
        .clk(clk), .rst_n(rst_n),
        .bck_en(b_bck_en), .bck(b_bck), .lrck(b_lrck), .sample_en(b_se)
    );

    localparam integer EA_PERIOD = DA * 32;      // 512
    localparam integer EB_PERIOD = DB * 32;      // 576
    localparam real    CLK_HZ    = 27000000.0;

    //-------------------------------------------------------------------------
    // 测量：一个 always 块里统一数拍，避免跨块竞争
    //-------------------------------------------------------------------------
    integer cyc = 0;

    integer se_prev [0:1];
    integer se_per  [0:1];
    integer lr_prev [0:1];
    integer lr_per  [0:1];
    integer lr_hi   [0:1];
    integer lr_hi_l [0:1];
    integer bc_prev [0:1];
    integer bc_per  [0:1];
    integer se_cnt  [0:1];      // sample_en 脉冲总数
    integer se_align[0:1];      // 其中"与 lrck 1→0 翻转 + bck_en 同拍"的个数
    reg     lr_q    [0:1];
    reg     bc_q    [0:1];

    wire [1:0] se_w = {b_se,   a_se};
    wire [1:0] lr_w = {b_lrck, a_lrck};
    wire [1:0] bc_w = {b_bck,  a_bck};
    wire [1:0] be_w = {b_bck_en, a_bck_en};

    integer i;

    initial begin
        for (i = 0; i < 2; i = i + 1) begin
            se_prev[i] = -1; se_per[i] = -1;
            lr_prev[i] = -1; lr_per[i] = -1;
            lr_hi[i]   = 0;  lr_hi_l[i] = -1;
            bc_prev[i] = -1; bc_per[i] = -1;
            se_cnt[i]  = 0;  se_align[i] = 0;
            lr_q[i]    = 1'b0; bc_q[i] = 1'b0;
        end
    end

    always @(posedge clk) begin
        cyc = cyc + 1;
        for (i = 0; i < 2; i = i + 1) begin
            // sample_en 周期
            if (se_w[i]) begin
                if (se_prev[i] >= 0) se_per[i] = cyc - se_prev[i];
                se_prev[i] = cyc;
                // 对齐契约：此刻（观测的是上一拍更新的值）必须同时满足
                //   · lrck 上一拍为 1、本拍为 0  → 正是 1→0 翻转那一拍
                //   · bck_en 为 1                 → 是第 BCK_PER_LRCK 个 bck_en
                se_cnt[i] = se_cnt[i] + 1;
                if (lr_q[i] === 1'b1 && lr_w[i] === 1'b0 && be_w[i] === 1'b1)
                    se_align[i] = se_align[i] + 1;
            end
            // lrck：上升沿量周期，同时收下上一周期的高电平宽度
            if (lr_w[i] && !lr_q[i]) begin
                if (lr_prev[i] >= 0) begin
                    lr_per[i]  = cyc - lr_prev[i];
                    lr_hi_l[i] = lr_hi[i];
                end
                lr_prev[i] = cyc;
                lr_hi[i]   = 1;               // 本拍就是高电平的第一拍
            end else if (lr_w[i]) begin
                lr_hi[i] = lr_hi[i] + 1;
            end
            lr_q[i] = lr_w[i];
            // bck 引脚周期
            if (bc_w[i] && !bc_q[i]) begin
                if (bc_prev[i] >= 0) bc_per[i] = cyc - bc_prev[i];
                bc_prev[i] = cyc;
            end
            bc_q[i] = bc_w[i];
        end
    end

    //-------------------------------------------------------------------------
    // 判据记账
    //-------------------------------------------------------------------------
    integer checks = 0;
    integer errors = 0;

    task fail(input [1023:0] msg);
        begin
            errors = errors + 1;
            $display("      [FAIL] %0s", msg);
        end
    endtask

    // 一个配置的 5 项检查
    task chk(input integer ch, input [127:0] tag, input integer divb, input integer period);
        real sr;
        begin
            // [1] sample_en 周期
            checks = checks + 1;
            if (se_per[ch] !== period) begin
                $display("      [FAIL] %0s sample_en 周期 = %0d 拍，应为 %0d", tag, se_per[ch], period);
                errors = errors + 1;
            end else
                $display("      %0s [1] sample_en 周期 = %0d 拍                  OK", tag, se_per[ch]);

            // [2] lrck 完整周期
            checks = checks + 1;
            if (lr_per[ch] !== period) begin
                $display("      [FAIL] %0s lrck 完整周期 = %0d 拍，应为 %0d", tag, lr_per[ch], period);
                errors = errors + 1;
            end else
                $display("      %0s [2] lrck 完整周期 = %0d 拍（量完整周期）   OK", tag, lr_per[ch]);

            // [3] lrck 高电平宽度 = 16 × divb
            checks = checks + 1;
            if (lr_hi_l[ch] !== 16 * divb) begin
                $display("      [FAIL] %0s lrck 高电平 = %0d 拍，应为 %0d", tag, lr_hi_l[ch], 16 * divb);
                errors = errors + 1;
            end else
                $display("      %0s [3] lrck 高电平 = %0d 拍（占空比 50%%）     OK", tag, lr_hi_l[ch]);

            // [4] bck 引脚周期
            checks = checks + 1;
            if (bc_per[ch] !== divb) begin
                $display("      [FAIL] %0s bck 周期 = %0d 拍，应为 %0d", tag, bc_per[ch], divb);
                errors = errors + 1;
            end else
                $display("      %0s [4] bck 引脚周期 = %0d 拍                    OK", tag, bc_per[ch]);

            // [5] 反算采样率
            sr = CLK_HZ / period;
            checks = checks + 1;
            if (sr < 40000.0 || sr > 60000.0) begin
                $display("      [FAIL] %0s 反算采样率 = %0.3f Hz，不在 40..60 kHz", tag, sr);
                errors = errors + 1;
            end else
                $display("      %0s [5] 反算采样率 = %0.3f Hz                  OK", tag, sr);

            // [6] 对齐契约：sample_en 必须与 lrck 1→0 + 该拍 bck_en 同拍
            checks = checks + 1;
            if (se_cnt[ch] == 0 || se_align[ch] !== se_cnt[ch]) begin
                $display("      [FAIL] %0s 对齐契约 %0d/%0d（sample_en 未与 lrck 1→0 及 bck_en 同拍）",
                         tag, se_align[ch], se_cnt[ch]);
                errors = errors + 1;
            end else
                $display("      %0s [6] 对齐契约 %0d/%0d 脉冲同拍          OK", tag,
                         se_align[ch], se_cnt[ch]);
        end
    endtask

    initial begin
        $dumpfile("tb_audio_clk_en.vcd");
        $dumpvars(0, tb_audio_clk_en);

        $display("");
        $display("================================================================");
        $display(" tb_audio_clk_en —— 音频时钟链判据（采样率定稿 52734.375 Hz）");
        $display("================================================================");
        $display("  27 MHz ÷ DIV_BCK ÷ 32 = 采样率；量【完整周期】，不量翻转间隔");
        $display("");

        repeat (4) @(negedge clk);
        rst_n = 1'b1;

        // 跑满 4 个 LRCK 周期（取两个配置的较大者）
        repeat (5 * EB_PERIOD) @(negedge clk);

        // 下标约定：se_w/lr_w/bc_w = {b_*, a_*} ⇒ bit0 = A 配置，bit1 = B 配置
        $display("  A 配置 DIV_BCK=16（产品：tdm_top / tdm_top_owned / tdm_top_rh）");
        chk(1'b0, "A", DA, EA_PERIOD);
        $display("");
        $display("  B 配置 DIV_BCK=18（旧：osc_additive_top，不能悄悄坏掉）");
        chk(1'b1, "B", DB, EB_PERIOD);

        $display("");
        $display("  定稿：产品采样率 = 27e6/512 = %0.3f Hz", CLK_HZ / EA_PERIOD);
        $display("        48 kHz 需 PLL 或换晶振，本项目「不用 PLL」，故不采用。");

        $display("");
        $display("================================================================");
        if (errors == 0)
            $display(" PASS —— %0d 项检查全部通过", checks);
        else
            $display(" FAIL —— %0d / %0d 项检查失败", errors, checks);
        $display("================================================================");
        $display("");
        $finish;
    end

    initial begin
        #(2_000_000);
        $display("[TIMEOUT] 仿真超时退出");
        $finish;
    end

endmodule
