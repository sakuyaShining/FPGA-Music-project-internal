//=============================================================================
// osc_core.v —— 加法合成【无状态运算核】
//
// 【它是什么】
//   把一次"泛音组求和"的全部【运算】打包成独立模块：
//   查表 → 乘幅度 → 加法树。它自己【不拥有任何随时间变化的状态】——
//   相位从外面进来（phase_in），推进后的相位组合逻辑导出（phase_adv），
//   存不存、存哪里（寄存器 / 将来 TDM 的 BSRAM），是外部的事。
//
// 【为什么这样拆（纪律 1：状态与运算分离）】
//   v2 版里 phase[] 寄存器和运算通路熔在同一模块里。全并行时无所谓，
//   但上 TDM 时相位要搬进 BSRAM 做"读-改-写"，状态内嵌就意味着整个
//   引擎重写。拆开之后，TDM 只是换一个状态持有层，运算核一行不改。
//
// 【接口契约】
//   输入  phase_in : 各泛音【当前】相位（外部状态，本拍取表地址用）
//   输出  phase_adv: phase_in + inc（组合逻辑）。外部在 sample_en 拍寄存它
//                    即完成相位推进；TDM 场景在时隙末写回存储器即可。
//   输出  sum_out  : 8 路泛音的加权和（27bit 有符号，【未饱和】）。
//                    饱和刻意不在核内做——包络必须乘在"求和之后、饱和
//                    之前"，核内饱和会堵死包络的插入点（声部级 ADSR）。
//
// 【位精确承诺】
//   数据通路与 v2（archive/osc_additive_v2_状态内嵌.v）逐级相同：
//   地址取推进【前】的相位、表 256×16、乘法 >>>8、加法树 8→4→2→1。
//   由 tb_osc_additive + synth_engine.py verify 兜底：样本序列必须
//   逐位不变（回归基线备份在 sim_build/additive/_baseline_step0/）。
//
// 【限制】
//   加法树按 8 路硬编码（与 v2 相同）。地板阶段 = 每声部 8 泛音固定；
//   TDM 时隙核（每拍 1 个泛音）将来另立模块，不复用这棵树。
//=============================================================================

`timescale 1ns/1ps

module osc_core #(
    parameter NUM_PARTIALS = 8,      // 泛音个数（加法树按 8 硬编码，改它要同步改树）
    parameter PHASE_W      = 24,     // 相位累加器位宽
    parameter TAB_AW       = 8,      // 正弦表地址位宽（8 -> 256 项）
    parameter AMP_W        = 8       // 每个泛音的幅度位宽
)(
    input  wire                            clk,
    input  wire                            rst_n,
    input  wire                            sample_en,   // 拉高一拍 = 处理一个样本
    input  wire [NUM_PARTIALS*PHASE_W-1:0] phase_in,    // 【外部状态】当前相位（拼接）
    input  wire [NUM_PARTIALS*PHASE_W-1:0] inc_flat,    // 各泛音频率增量（拼接）
    input  wire [NUM_PARTIALS*AMP_W-1:0]   amp_flat,    // 各泛音幅度（拼接）
    output wire [NUM_PARTIALS*PHASE_W-1:0] phase_adv,   // 推进后的相位（组合，外部寄存）
    output wire signed [26:0]              sum_out      // 加权和（未饱和，27bit 有符号）
);

    //-------------------------------------------------------------------------
    // 0) 相位推进（组合）：这是核里唯一的"时序语义"，
    //    但它只是个加法器——状态寄存器在外面的壳层。
    //-------------------------------------------------------------------------
    genvar gp;
    generate
        for (gp = 0; gp < NUM_PARTIALS; gp = gp + 1) begin : G_PHASE_ADV
            assign phase_adv[gp*PHASE_W +: PHASE_W] =
                phase_in[gp*PHASE_W +: PHASE_W] + inc_flat[gp*PHASE_W +: PHASE_W];
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 1) 正弦查找表：256 项 × 16 bit（Q1.15）—— ROM 常量，不是状态。
    //    只在"级 2"被同步读，才能映射到 BSRAM（v2 教训：异步读会退化成
    //    LUT 选择树，LUT 爆炸 + 路径深）。
    //-------------------------------------------------------------------------
    reg signed [15:0] sine_tab [0:(1<<TAB_AW)-1];

    initial begin
        $readmemh("sine256.hex", sine_tab);
    end

    //-------------------------------------------------------------------------
    // 流水线寄存器（级 1~3 每泛音一份，级 4~6 是加法树）
    //-------------------------------------------------------------------------
    reg [TAB_AW-1:0]  addr_r [0:NUM_PARTIALS-1];   // 级1：表地址
    reg signed [15:0] s_val  [0:NUM_PARTIALS-1];   // 级2：表数据
    reg signed [23:0] prod   [0:NUM_PARTIALS-1];   // 级3：乘幅度

    reg signed [24:0] sum1 [0:3];                  // 级4：8 -> 4
    reg signed [25:0] sum2 [0:1];                  // 级5：4 -> 2
    reg signed [26:0] sum3;                        // 级6：2 -> 1（= sum_out）

    //-------------------------------------------------------------------------
    // 幅度取自输入端口（组合）
    //-------------------------------------------------------------------------
    wire [AMP_W-1:0] a_val [0:NUM_PARTIALS-1];

    genvar ga;
    generate
        for (ga = 0; ga < NUM_PARTIALS; ga = ga + 1) begin : G_AMP
            assign a_val[ga] = amp_flat[ ga*AMP_W +: AMP_W ];
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 级 1：锁存表地址 —— 用【推进前】的相位（与 v2、与 Python 模型一致）
    //-------------------------------------------------------------------------
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                addr_r[i] <= {TAB_AW{1'b0}};
        end
        else if (sample_en) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                // 取该泛音相位 slice 的【高】TAB_AW 位（与 v2 的
                // phase[PHASE_W-1 -: TAB_AW] 等价，从扁平向量的第 i 段取）
                addr_r[i] <= phase_in[i*PHASE_W + PHASE_W - 1 -: TAB_AW];
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
    // 级 3：乘幅度
    //   显式给 32 位中间量。AMP_W 由 8 扩到 16（为包络留小数位）后，
    //     乘积最大 32767×65535 ≈ 2.1e9，原来的 24 位上下文会溢出。
    //     先算 32 位乘积、再算术右移 AMP_W 位。
    //   当幅度是"整数 << 8"（包络满幅）时，(x*(a<<8))>>>16 ≡ (x*a)>>>8，
    //     所以这条改动对原有行为是【逐位无影响】的（回归基线可证）。
    //-------------------------------------------------------------------------
    wire signed [31:0] mul_tmp [0:NUM_PARTIALS-1];

    genvar gm;
    generate
        for (gm = 0; gm < NUM_PARTIALS; gm = gm + 1) begin : G_MUL
            assign mul_tmp[gm] = s_val[gm] * $signed({1'b0, a_val[gm]});
        end
    endgenerate

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                prod[i] <= 24'sd0;
        end
        else if (sample_en) begin
            for (i = 0; i < NUM_PARTIALS; i = i + 1)
                prod[i] <= mul_tmp[i] >>> AMP_W;
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
    // 级 6：加法树第三层（2 -> 1），输出【未饱和】的和
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            sum3 <= 27'sd0;
        else if (sample_en)
            sum3 <= sum2[0] + sum2[1];
    end

    assign sum_out = sum3;

endmodule
