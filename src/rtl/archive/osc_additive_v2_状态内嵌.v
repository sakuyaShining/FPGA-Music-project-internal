//=============================================================================
// osc_additive.v —— 加法合成振荡器组（v2：流水线 + 同步读表）
//
// v1 的两个问题（由综合暴露，见 docs/02-技术方案/11-综合结果与课题覆盖审计.md）：
//   问题1：`assign s_val = sine_tab[phase[..]]` 是【异步读】，
//          而块 RAM 是【同步读】的 —— 综合器无法把它放进 BSRAM，
//          只能退化成 LUT 搭的多级选择树（浪费大量 LUT，且路径极深）。
//   问题2：`sum_comb` 用组合 always + for 循环，综合成【串行 8 级加法链】，
//          单这一条就占约 5.6 ns。结果 SETUP slack = −2.987 ns（时序违例）。
//
// v2 的改法（只改"怎么摆硬件"，不改算法）：
//   · 表地址寄存一拍、同步读数据        → 表能进 BSRAM，路径短
//   · 8 路求和改成加法树 + 逐级打拍     → 路径从 O(N) 降到 O(log N)
//
// 算法一字未改：同样的相位累加、同样的表、同样的定点乘移位、同样的饱和。
// 因此仿真输出的【样本序列】应当与 v1 完全一致，只是整体延迟多几拍。
//
// 关键实现细节：所有流水线寄存器都必须由 sample_en 使能。
//    否则每个系统时钟都会推进一级流水线，把样本之间的空闲拍也当数据处理，
//    结果会完全错误（而且是那种"看起来在跑但音不对"的错误）。
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
    // 1) 正弦查找表：256 项 × 16 bit（Q1.15）
    //    【v2 关键】它只在下面"级 2"被同步读，这样才能映射到 BSRAM。
    //-------------------------------------------------------------------------
    reg signed [15:0] sine_tab [0:(1<<TAB_AW)-1];

    initial begin
        $readmemh("sine256.hex", sine_tab);
    end

    //-------------------------------------------------------------------------
    // 2) 相位累加器：每个泛音一个，互不影响 —— "独立振荡器"的物理体现
    //-------------------------------------------------------------------------
    reg [PHASE_W-1:0] phase [0:NUM_PARTIALS-1];

    //-------------------------------------------------------------------------
    // 流水线寄存器（7 级）
    //-------------------------------------------------------------------------
    reg [TAB_AW-1:0]  addr_r [0:NUM_PARTIALS-1];   // 级1：表地址
    reg signed [15:0] s_val  [0:NUM_PARTIALS-1];   // 级2：表数据
    reg signed [23:0] prod   [0:NUM_PARTIALS-1];   // 级3：乘幅度

    reg signed [24:0] sum1 [0:3];                  // 级4：8 -> 4
    reg signed [25:0] sum2 [0:1];                  // 级5：4 -> 2
    reg signed [26:0] sum3;                        // 级6：2 -> 1
                                                   // 级7：饱和输出

    //-------------------------------------------------------------------------
    // 幅度取自输入端口（组合）
    //-------------------------------------------------------------------------
    wire [AMP_W-1:0] a_val [0:NUM_PARTIALS-1];

    genvar g;
    generate
        for (g = 0; g < NUM_PARTIALS; g = g + 1) begin : G_AMP
            assign a_val[g] = amp_flat[ g*AMP_W +: AMP_W ];
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 级 1：推进相位 + 锁存表地址
    //-------------------------------------------------------------------------
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1) begin
                phase[i]  <= {PHASE_W{1'b0}};
                addr_r[i] <= {TAB_AW{1'b0}};
            end
        end
        else if (sample_en) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1) begin
                phase[i]  <= phase[i] + inc_flat[i*PHASE_W +: PHASE_W];
                addr_r[i] <= phase[i][PHASE_W-1 -: TAB_AW];   // 用推进前的相位
            end
        end
    end

    //-------------------------------------------------------------------------
    // 级 2：同步读表（这一步让表能进 BSRAM）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                s_val[i] <= 16'sd0;
        end
        else if (sample_en) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                s_val[i] <= sine_tab[addr_r[i]];
        end
    end

    //-------------------------------------------------------------------------
    // 级 3：乘幅度（用算术右移代替除法：>>> 8 等价于 ÷256）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                prod[i] <= 24'sd0;
        end
        else if (sample_en) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                prod[i] <= (s_val[i] * $signed({1'b0, a_val[i]})) >>> 8;
        end
    end

    //-------------------------------------------------------------------------
    // 级 4：加法树第一层（8 -> 4）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sum1[0] <= 25'sd0; sum1[1] <= 25'sd0;
            sum1[2] <= 25'sd0; sum1[3] <= 25'sd0;
        end
        else if (sample_en) begin
            sum1[0] <= prod[0] + prod[1];
            sum1[1] <= prod[2] + prod[3];
            sum1[2] <= prod[4] + prod[5];
            sum1[3] <= prod[6] + prod[7];
        end
    end

    //-------------------------------------------------------------------------
    // 级 5：加法树第二层（4 -> 2）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sum2[0] <= 26'sd0;
            sum2[1] <= 26'sd0;
        end
        else if (sample_en) begin
            sum2[0] <= sum1[0] + sum1[1];
            sum2[1] <= sum1[2] + sum1[3];
        end
    end

    //-------------------------------------------------------------------------
    // 级 6：加法树第三层（2 -> 1）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            sum3 <= 27'sd0;
        else if (sample_en)
            sum3 <= sum2[0] + sum2[1];
    end

    //-------------------------------------------------------------------------
    // 级 7：饱和限幅并输出
    //   用饱和而不是截断：截断会让大信号"回绕"成反相噪声，听起来很刺耳。
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            sample_out <= {OUT_W{1'b0}};
        else if (sample_en) begin
            if (sum3 > 27'sd8388607)
                sample_out <=  24'sd8388607;
            else if (sum3 < -27'sd8388608)
                sample_out <= -24'sd8388608;
            else
                sample_out <= sum3[OUT_W-1:0];
        end
    end

endmodule
