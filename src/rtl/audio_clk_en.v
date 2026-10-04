//=============================================================================
// audio_clk_en.v —— I2S 音频时钟【使能脉冲】发生器（单时钟域，零派生时钟）
//
// 【它产生什么】（27 MHz 主时钟下）
//   bck_en   : 每 DIV_BCK(18) 拍一拍   → 1.5 MHz 位时钟使能（27e6/18）
//   lrck     : 每 HALF(16) 个 BCK 翻转一次 → 一个完整周期 = 32 个 BCK
//                                          → LRCK = 1.5MHz/32 = 46875 Hz
//   sample_en: 每个完整 LRCK 周期的末尾一拍 → 46875 Hz，"新样本开始"
//
//   27e6 / 18 / 32 = 46875 Hz，全整数 → 零抖动（这是 27 MHz 方案的核心账）。
//
// 【★ 2026-09-30 修正：一个差 2 倍的 bug，务必看懂再改】
//   首版写成"每 32 个 BCK 翻转一次 lrck"，并注释成"LRCK = 46875 Hz"。
//   这是把【翻转率】当成了【字时钟频率】：
//       每 32 个 BCK 翻转 → 翻转率 1.5e6/32 = 46875 次/秒
//       但一个完整 LRCK 周期 = 两次翻转 → LRCK = 46875/2 = 23437.5 Hz  ✗
//   而 sample_en 仍是每 32 个 BCK 一拍 = 46875 Hz，于是【引擎跑 46875，
//   而 I2S 帧率只有 23437.5】——正好差 2 倍。
//   上板后果：MAX98357A 看到的 BCK/LRCK = 64 而不是 32，每帧只能塞进
//   一半的样本，音高整整差一个八度。
//   正确关系（16bit × 2 声道 = 32 BCK/帧）：
//       翻转间隔 = 16 个 BCK（半周期）
//       完整周期 = 32 个 BCK = 1/46875 s
//   教训：**验证"频率"必须量"完整周期"，不能量"翻转间隔"。**
//   tb_audio_clk_en 已补 S6 断言（LRCK 周期 = 576 clk = 18×32）专门守这条。
//
// 【设计纪律】
//   单时钟域铁律：绝不分频出真实的慢时钟去驱动别的模块，只用使能脉冲
//   （src/sim/README.md「不要分频出慢时钟」）。I2S 移位寄存器在 bck_en
//   拍移位，输出引脚的物理翻转频率自然就是 1.5 MHz——不用派生时钟，
//   时序分析只需约束 27 MHz 一根。
//
// 【对齐关系（I2S 步骤要用，已由 tb_audio_clk_en 实测验证）】
//   lrck 的 1→0 翻转、sample_en、每个 LRCK 周期的第 32 个 bck_en
//   三者在【同一个 posedge】更新。i2s_tx 依赖此契约把"新样本装载"与
//   "左声道帧起始"对齐。
//   另一坑（首版已踩）：第二级若读 bck_en 这个寄存器判断，会比
//   第 32 个 bck_en 晚一拍——必须用 bck_cnt == DIV_BCK-1 同条件判断。
//=============================================================================

`timescale 1ns/1ps

module audio_clk_en #(
    parameter integer DIV_BCK      = 18,   // 27MHz ÷ 18 = 1.5 MHz BCK
    parameter integer BCK_PER_LRCK = 32    // 一个【完整】LRCK 周期含多少个 BCK
                                           // = 每个声道位数(16) × 声道数(2)
)(
    input  wire clk,
    input  wire rst_n,
    output reg        bck_en,      // 位时钟使能（每 18 拍一拍）
    output wire       bck,         // 位时钟【引脚】（每 18 拍一个完整周期 = 1.5 MHz）
    output reg        lrck,        // 字时钟 WS（每 16 个 BCK 翻转，周期 32 BCK）
    output reg        sample_en    // 样本使能（每 32 个 BCK 一拍 = 46875 Hz）
);

    localparam integer HALF = BCK_PER_LRCK / 2;   // 半周期 = 16 个 BCK

    //-------------------------------------------------------------------------
    // 0) 位时钟【引脚】：把 bck_en 的"每拍一个位"摊开成真正的方波
    //    bck_cnt 在一个 BCK 周期内数 0..17：
    //        0..8  低（9 拍）
    //        9..17 高（9 拍）
    //    → 完整周期 18 拍 = 27MHz/18 = 1.5 MHz，50% 占空比。
    //    ★ 相位关系（i2s_tx 依赖它，别再改）：
    //        bck 的【上升沿】在 bck_cnt==9
    //        bck 的【下降沿】在 bck_cnt==17 = bck_en 置位那一拍
    //      发送方在 bck_en 拍改数据（= 下降沿），接收方在上升沿采样，
    //      正好是 I2S 规定的"发方踩下降沿、收方踩上升沿"。
    //-------------------------------------------------------------------------
    reg [7:0] bck_cnt;               // 计到 DIV_BCK-1

    // 50% 占空比：低 DIV_BCK/2 拍、高 DIV_BCK/2 拍
    //   ★ 原来硬写 `bck_cnt >= 9`（只对 DIV_BCK=18 成立）。改成参数化，
    //     这样换分频比（例如 18 → 16）时占空比仍然是对称的。
    assign bck = (bck_cnt >= DIV_BCK[7:0] / 8'd2);

    //-------------------------------------------------------------------------
    // 第一级：clk -> bck_en（÷18）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            bck_cnt <= 8'd0;
            bck_en  <= 1'b0;
        end
        else if (bck_cnt == DIV_BCK - 1) begin
            bck_cnt <= 8'd0;
            bck_en  <= 1'b1;
        end
        else begin
            bck_cnt <= bck_cnt + 1'b1;
            bck_en  <= 1'b0;
        end
    end

    //-------------------------------------------------------------------------
    // 第二级：LRCK / sample_en
    //   lr_cnt 在【一个完整 LRCK 周期】内数 0..BCK_PER_LRCK-1（0..31）
    //     · 计到 HALF-1(15)  → lrck 翻转（0→1，进入右声道半周期）
    //     · 计到 31          → lrck 翻转（1→0，新一轮帧起始）+ sample_en
    //   这样翻转间隔 = 16 个 BCK，完整周期 = 32 个 BCK。
    //
    //   ★ 判断条件用 bck_cnt == DIV_BCK-1 而不是读 bck_en —— bck_en 是
    //     上一拍才置位的寄存器，读它会让翻转整体晚一拍（首版实测 bug）。
    //-------------------------------------------------------------------------
    reg [5:0] lr_cnt;                // 0 .. BCK_PER_LRCK-1

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lr_cnt    <= 6'd0;
            lrck      <= 1'b0;
            sample_en <= 1'b0;
        end
        else if (bck_cnt == DIV_BCK - 1) begin
            lr_cnt <= (lr_cnt == BCK_PER_LRCK - 1) ? 6'd0 : (lr_cnt + 1'b1);

            // 半周期末(15) 与 整周期末(31) 各翻转一次 → 翻转间隔 16 个 BCK
            //   ★ 两处【缺一不可】。只写 15 那一处的话，一个 32-BCK 周期
            //     只翻一次，LRCK 反而变成 23437.5 Hz（与原版 bug 同症状）。
            if (lr_cnt == HALF - 1 || lr_cnt == BCK_PER_LRCK - 1)
                lrck <= ~lrck;

            // 完整周期末 → 新样本；与上面 31 那一处翻转【同拍】(lrck 1→0)
            sample_en <= (lr_cnt == BCK_PER_LRCK - 1);
        end
        else
            sample_en <= 1'b0;           // 其余拍必须清掉脉冲
    end

endmodule
