//=============================================================================
// test_mode.v —— RTL 内置测试模式（现场自证用）
//
// 【它解决赛题的哪两条】
//   形式项 F1：「支持测试模式下输出多路不同频率音频，频谱可观测对应数量独立谱峰」
//   红线   R3：「现场需自证无预录音频播放行为」
//
// 【核心思路：让每个泛音占一个独立的频率格】
//   正常演奏时，一个声部的 8 个泛音是同一条谐波列（f, 2f, 3f...）。
//   测试模式下把它们【拆开】，让 32 个泛音各占一个等间隔的频率格：
//
//       泛音序号 i (0..31)  →  频率 = (i+1) × 400 Hz
//       400, 800, 1200, ..., 12800 Hz        （全部在 Nyquist 23.4 kHz 以内）
//
//   于是频谱上出现的峰数【就是振荡器数】—— 评委可以一个一个数。
//   这比"我说我有 32 个振荡器"强得多：数字可以在频谱仪上直接验。
//
// 【两种子模式】
//   模式 1「谱峰计数」：32 个泛音全部等幅发声 → 频谱恰好 32 个峰，稳定可数。
//   模式 2「随机自证」：LFSR 随机开关每个泛音，每 ~50 ms 变一次。
//                       频谱持续随机变化 → **预录音频在原理上无法匹配**：
//                       没法提前录一段你都不知道会响成什么样的音频。
//   种子取自一个【不受复位清零】的自由计数器，所以每次上电/复位时刻不同，
//     序列起点就不同。现场可以当场复位给评委看："峰变了，预录做不到这个。"
//
// 【为什么测试模式不旁路引擎】
//   它仍然走完整通路：相位累加器 → 查表 → 乘幅度 → 包络 → 加法树 → 混音 → I2S。
//   测试模式只是【换了一组频率与幅度参数】。
//   这一点很关键：若测试模式走旁路，它就证明不了正常通路是纯硬件实时合成的。
//=============================================================================

`timescale 1ns/1ps

module test_mode #(
    parameter NV      = 4,
    parameter NPART   = 8,
    parameter PHASE_W = 24,
    // 相邻谱峰的频率间隔：400 Hz @ fs=46875 → inc = round(400 × 2^24 / 46875)
    parameter [PHASE_W-1:0] STEP_INC = 24'd143166,
    // 测试模式下每个泛音的幅度（等幅，便于数峰）
    parameter [7:0]         TONE_AMP = 8'd60,
    // 随机模式的变换周期：50 ms @ 46875 Hz ≈ 2344 拍
    parameter integer       RND_PERIOD = 2344
)(
    input  wire clk,
    input  wire rst_n,
    input  wire [1:0]  mode,        // 0=关闭  1=固定谱峰  2=随机自证
    input  wire [31:0] seed_free,   // 自由计数器（不受复位影响）→ 播种用
    output wire [NV*NPART*PHASE_W-1:0] inc_out,
    output wire [NV*NPART*8-1:0]       amp_out,
    output wire        rnd_active   // 随机模式进行中（供观察脚用）
);

    localparam NTONE = NV * NPART;      // 泛音总数

    //-------------------------------------------------------------------------
    // 1) LFSR（32 位最大长度，抽头 32/22/2/1）
    //    声明放在 generate 之前 —— Verilog 要求先声明后使用
    //-------------------------------------------------------------------------
    reg  [31:0] lfsr;
    reg         seeded;
    reg  [15:0] rnd_cnt;

    wire fb = lfsr[31] ^ lfsr[21] ^ lfsr[1] ^ lfsr[0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr    <= 32'hDEAD_BEEF;       // 临时值，下一个时钟就播种
            seeded  <= 1'b0;
            rnd_cnt <= 16'd0;
        end
        else if (!seeded) begin
            // 播种：复位释放的时刻不同 → 序列起点不同
            lfsr   <= seed_free ^ 32'hA5A5_5A5A;
            seeded <= 1'b1;
        end
        else if (mode == 2'd2) begin
            if (rnd_cnt == RND_PERIOD - 1) begin
                rnd_cnt <= 16'd0;
                lfsr    <= {lfsr[30:0], fb};
            end
            else
                rnd_cnt <= rnd_cnt + 16'd1;
        end
    end

    //-------------------------------------------------------------------------
    // 2) 每个泛音的频率与幅度（纯组合，不占时序资源）
    //-------------------------------------------------------------------------
    genvar gi;
    generate
        for (gi = 0; gi < NTONE; gi = gi + 1) begin : G_TONE
            // 频率：等间隔格子。gi 是常量，所以这个乘法在综合时就是常量。
            assign inc_out[gi*PHASE_W +: PHASE_W] = STEP_INC * (gi + 1);

            // 幅度：模式1 全部等幅；模式2 由 LFSR 的对应位决定开/关
            assign amp_out[gi*8 +: 8] =
                   (mode == 2'd2) ? (lfsr[gi] ? TONE_AMP : 8'd0)
                                  : TONE_AMP;
        end
    endgenerate

    assign rnd_active = (mode == 2'd2) & seeded;

endmodule
