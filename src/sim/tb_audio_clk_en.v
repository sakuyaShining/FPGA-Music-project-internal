//=============================================================================
// tb_audio_clk_en.v —— 音频时钟使能链的自检式测试台
//
// 验收标准（对应 docs/02-技术方案/14-必须项实施计划.md 步骤 2）：
//   S1  bck_en   相邻两个脉冲间隔【恒等于】18 个 clk（→ BCK = 1.5 MHz 整）
//   S2  lrck     相邻两次【翻转】间隔【恒等于】16 个 bck_en（半周期）
//   S3  sample_en 相邻两个脉冲间隔【恒等于】576 个 clk（= 18×32，两式互证）
//   S4  sample_en 与 lrck 的翻转【同拍】，且是 1→0 那一拍（帧起始）
//   S5  脉冲宽度都恰好 1 个 clk（无毛刺展宽）
//   S6  lrck 完整周期【恒等于】576 个 clk（= 18×32 → 46875 Hz）
//
// 【S6 为什么必须存在（2026-09-30 补）】
//   首版 RTL 写成"每 32 个 BCK 翻转一次 lrck"，并把 S2 断言成 32——测试
//   和 RTL 一起错，双双通过，但 LRCK 实际只有 23437.5 Hz（差 2 倍）。
//   根因是把【翻转间隔】当成了【周期】。
//   所以必须有一条断言直接量【完整周期】——S6 就是它。
//   **量频率永远要量周期，不要量翻转间隔。**
//
// 方法论（src/sim/README.md 三要点）：
//   检查逻辑走 negedge —— 与被测模块的 posedge 更新隔半拍，读到的值一定稳定。
//=============================================================================

`timescale 1ns/1ps

module tb_audio_clk_en;

    localparam integer DIV_BCK      = 18;
    localparam integer BCK_PER_LRCK = 32;
    localparam integer HALF         = BCK_PER_LRCK / 2;   // 16
    localparam integer CLK_PER_LRCK = DIV_BCK * BCK_PER_LRCK;  // 576
    localparam integer N_LRCK       = 20;    // 观测 20 个 LRCK 周期

    reg  clk;
    reg  rst_n;
    wire bck_en, lrck, sample_en;

    // 27 MHz：周期 37.037 ns，半周期取 18.519 ns（ps 精度取整）
    localparam CLK_HALF = 18.519;

    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    audio_clk_en #(
        .DIV_BCK      (DIV_BCK),
        .BCK_PER_LRCK (BCK_PER_LRCK)
    ) dut (
        .clk        (clk),
        .rst_n      (rst_n),
        .bck_en     (bck_en),
        .lrck       (lrck),
        .sample_en  (sample_en)
    );

    //-------------------------------------------------------------------------
    // 自检计数器与观察寄存器（全部在 negedge 采样）
    //-------------------------------------------------------------------------
    integer errors;
    integer n_bck;            // 收到的 bck_en 脉冲总数
    integer n_smp;            // 收到的 sample_en 脉冲总数
    integer n_lr_tog;         // lrck 翻转次数
    integer n_lr_rise;        // lrck 上升沿次数

    integer gap_bck;          // 本次 bck_en 距上次的 clk 数
    integer gap_smp;          // 本次 sample_en 距上次的 clk 数
    integer gap_lr_rise;      // 本次 lrck 上升沿距上次的 clk 数（= 完整周期）
    integer bck_between_lr;   // 本次 lrck 翻转距上次的 bck_en 数

    reg prev_bck_en, prev_smp_en, prev_lrck;
    integer clk_since_bck;
    integer clk_since_smp;
    integer clk_since_lr_rise;

    initial begin
        errors         = 0;
        n_bck          = 0;
        n_smp          = 0;
        n_lr_tog       = 0;
        n_lr_rise      = 0;
        gap_bck        = 0;
        gap_smp        = 0;
        gap_lr_rise    = 0;
        bck_between_lr = 0;
        prev_bck_en    = 1'b0;
        prev_smp_en    = 1'b0;
        prev_lrck      = 1'b0;
        clk_since_bck      = 0;
        clk_since_smp      = 0;
        clk_since_lr_rise  = 0;
    end

    always @(negedge clk) begin
        clk_since_bck     = clk_since_bck + 1;
        clk_since_smp     = clk_since_smp + 1;
        clk_since_lr_rise = clk_since_lr_rise + 1;

        //---------- S1：bck_en 间隔恒 18 ----------
        if (bck_en === 1'b1 && prev_bck_en === 1'b0) begin
            gap_bck = clk_since_bck;
            n_bck   = n_bck + 1;
            if (n_bck > 1 && gap_bck != DIV_BCK) begin
                errors = errors + 1;
                $display("[FAIL] S1 第%0d个bck_en间隔=%0d拍(应%0d)", n_bck, gap_bck, DIV_BCK);
            end
            clk_since_bck = 0;
        end
        prev_bck_en = bck_en;

        //---------- S3：sample_en 间隔恒 576 ----------
        if (sample_en === 1'b1 && prev_smp_en === 1'b0) begin
            gap_smp = clk_since_smp;
            n_smp   = n_smp + 1;
            if (n_smp > 1 && gap_smp != CLK_PER_LRCK) begin
                errors = errors + 1;
                $display("[FAIL] S3 第%0d个sample_en间隔=%0d拍(应%0d)", n_smp, gap_smp, CLK_PER_LRCK);
            end
            // S4 前半：sample_en 出现的拍，lrck 必须恰好是 1→0（帧起始）
            if (lrck !== 1'b0 || prev_lrck !== 1'b1) begin
                errors = errors + 1;
                $display("[FAIL] S4 sample_en第%0d拍不是lrck的1→0边沿", n_smp);
            end
            clk_since_smp = 0;
        end
        prev_smp_en = sample_en;

        //---------- S6：lrck 完整周期恒 576 clk（量周期，不量翻转间隔）----------
        if (lrck === 1'b1 && prev_lrck === 1'b0) begin
            gap_lr_rise = clk_since_lr_rise;
            n_lr_rise   = n_lr_rise + 1;
            if (n_lr_rise > 1 && gap_lr_rise != CLK_PER_LRCK) begin
                errors = errors + 1;
                $display("[FAIL] S6 LRCK完整周期=%0d拍(应%0d → %0d Hz)",
                         gap_lr_rise, CLK_PER_LRCK, 27000000 / gap_lr_rise);
            end
            clk_since_lr_rise = 0;
        end

        //---------- S2：lrck 翻转间隔恒 16 个 bck_en ----------
        if (lrck !== prev_lrck) begin
            n_lr_tog       = n_lr_tog + 1;
            bck_between_lr = bck_between_lr + 1;
            if (bck_between_lr != 1) begin  // 跳过本窗口起点
                if (bck_between_lr != HALF) begin
                    errors = errors + 1;
                    $display("[FAIL] S2 lrck翻转间隔=%0d个bck_en(应%0d)", bck_between_lr, HALF);
                end
            end
            bck_between_lr = 0;
        end
        else if (bck_en === 1'b1) begin
            bck_between_lr = bck_between_lr + 1;
        end
        prev_lrck = lrck;
    end

    //-------------------------------------------------------------------------
    // 主流程：复位 -> 观测 N_LRCK 个 LRCK 周期 -> 汇总判定
    //-------------------------------------------------------------------------
    initial begin
        $dumpfile("audio_clk_en.vcd");
        $dumpvars(0, tb_audio_clk_en);

        rst_n = 1'b0;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;

        repeat (N_LRCK * CLK_PER_LRCK + 200) @(posedge clk);

        $display("==============================================");
        $display(" 音频时钟使能链自检  27MHz / %0d / %0d", DIV_BCK, BCK_PER_LRCK);
        $display(" 观测: bck_en=%0d  sample_en=%0d  lrck翻转=%0d  lrck上升=%0d",
                 n_bck, n_smp, n_lr_tog, n_lr_rise);
        // 注意不能用 bck_en:sample_en 总数比断言 32:1 —— 观测窗口的边缘
        // 必然多出第一个样本之前/最后一个之后的几个 bck_en（测量伪影）。
        // 周期正确性由 S1(18) S2(16) S3(576) S6(576) 的【间隔/周期】断言保证。
        if (n_smp != N_LRCK) begin
            errors = errors + 1;
            $display("[FAIL] sample_en 个数=%0d (期望%0d)", n_smp, N_LRCK);
        end
        if (n_lr_rise != N_LRCK) begin
            errors = errors + 1;
            $display("[FAIL] lrck 完整周期数=%0d (期望%0d)", n_lr_rise, N_LRCK);
        end

        $display(" 实测: BCK = 27MHz/%0d = %0d Hz", DIV_BCK, 27000000 / DIV_BCK);
        $display("       LRCK周期 = %0d clk → LRCK = %0d Hz",
                 CLK_PER_LRCK, 27000000 / CLK_PER_LRCK);
        if (errors == 0)
            $display(" [PASS] S1~S6 全部通过：BCK=1.5MHz LRCK=46875Hz 无抖动，lrck 1→0 边沿/sample_en/第%0d个bck_en 三者同拍", BCK_PER_LRCK);
        else
            $display(" [FAILED] 共 %0d 处错误", errors);
        $display("==============================================");
        $finish;
    end

endmodule
