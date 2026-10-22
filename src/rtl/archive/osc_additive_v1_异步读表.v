//=============================================================================
// osc_additive.v —— 加法合成振荡器组（候选架构方案 v1 的核心）
//
// 设计要点：
//   · NUM_PARTIALS 个【完全独立】的相位累加器 —— 这是赛题对"独立振荡器"的定义
//   · 共用一张正弦查找表（256 项 × 16 bit，Q1.15）
//   · 每个泛音有独立的频率增量 inc 与幅度 amp
//   · 求和后做饱和限幅，防止溢出回绕产生刺耳噪声
//
// 为什么这个结构适合"只能靠仿真"的开发方式：
//   全部是确定性数字逻辑 —— 同样的输入必得同样的输出，不依赖任何模拟器件。
//   仿真出来的样本可以直接写成 WAV 听，也可以做 FFT 验证。
//
// 端口用"展平向量"而不是数组，是为了兼容 Verilog-2001（iverilog -g2005）
//=============================================================================

module osc_additive #(
    parameter NUM_PARTIALS = 8,      // 泛音个数
    parameter PHASE_W      = 24,     // 相位累加器位宽
    parameter TAB_AW       = 8,      // 正弦表地址位宽（8 -> 256 项）
    parameter AMP_W        = 8,      // 每个泛音的幅度位宽
    parameter OUT_W        = 24      // 输出样本位宽（有符号）
)(
    input  wire                            clk,
    input  wire                            rst_n,
    input  wire                            sample_en,   // 拉高一拍 = 产生一个样本
    input  wire [NUM_PARTIALS*PHASE_W-1:0] inc_flat,    // 各泛音频率增量（拼接）
    input  wire [NUM_PARTIALS*AMP_W-1:0]   amp_flat,    // 各泛音幅度（拼接）
    output reg  signed [OUT_W-1:0]         sample_out
);

    //-------------------------------------------------------------------------
    // 1) 正弦查找表
    //    256 项，16 bit 有符号（Q1.15，即 -1.0 ~ +0.99997）
    //    内容由 $readmemh 从 sine256.hex 载入（该文件由 Python 生成）
    //-------------------------------------------------------------------------
    reg signed [15:0] sine_tab [0:(1<<TAB_AW)-1];

    initial begin
        $readmemh("sine256.hex", sine_tab);
    end

    //-------------------------------------------------------------------------
    // 2) 相位累加器：每个泛音一个，互不影响
    //    这就是"独立振荡器"的物理体现
    //-------------------------------------------------------------------------
    reg [PHASE_W-1:0] phase [0:NUM_PARTIALS-1];

    //-------------------------------------------------------------------------
    // 3) 组合读取：用相位的高 TAB_AW 位做表地址
    //-------------------------------------------------------------------------
    wire signed [15:0] s_val [0:NUM_PARTIALS-1];
    wire [AMP_W-1:0]   a_val [0:NUM_PARTIALS-1];

    genvar g;
    generate
        for (g = 0; g < NUM_PARTIALS; g = g + 1) begin : G_READ
            assign s_val[g] = sine_tab[ phase[g][PHASE_W-1 -: TAB_AW] ];
            assign a_val[g] = amp_flat[ g*AMP_W +: AMP_W ];
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 4) 组合求和
    //    每个泛音的贡献 = (正弦值 × 幅度) >>> 8
    //    （幅度是 8 bit 无符号，除以 256 后当作 0..1 的增益）
    //-------------------------------------------------------------------------
    reg signed [31:0] sum_comb;
    integer k;
    always @(*) begin
        sum_comb = 32'sd0;
        for (k = 0; k < NUM_PARTIALS; k = k + 1)
            sum_comb = sum_comb + ((s_val[k] * $signed({1'b0, a_val[k]})) >>> 8);
    end

    //-------------------------------------------------------------------------
    // 5) 时序更新：只在 sample_en 有效时推进相位、输出新样本
    //    注：s_val 读的是"上一拍的相位"，所以整体有 1 个样本的固定延迟。
    //        这是流水线延迟，不是错误。
    //-------------------------------------------------------------------------
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                phase[i] <= {PHASE_W{1'b0}};
            sample_out <= {OUT_W{1'b0}};
        end
        else if (sample_en) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                phase[i] <= phase[i] + inc_flat[i*PHASE_W +: PHASE_W];

            // 饱和限幅（比直接截断安全：截断会让大信号"回绕"成反相噪声）
            if (sum_comb > 32'sd8388607)
                sample_out <=  24'sd8388607;
            else if (sum_comb < -32'sd8388608)
                sample_out <= -24'sd8388608;
            else
                sample_out <= sum_comb[OUT_W-1:0];
        end
    end

endmodule
