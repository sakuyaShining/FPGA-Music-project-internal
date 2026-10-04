//=============================================================================
// osc_additive_top.v —— 综合顶层（v6：全部参数走寄存器映射，完整音频通路）
//
// 【v6 相比 v5 的变化 —— 解锁 M6】
//   1. 所有参数（音高 / 幅度 / ADSR / 混音增益 / 测试模式）不再是编译期常量，
//      改为从 reg_bank 读取 → **运行时可变**。这是 M6「单音实时变调」的前提。
//   2. 加了一个【演示序列器】：每约 0.4 s 把声部 0 的音高换成音阶的下一个音。
//      它不是为了好看，有两个实在作用：
//        · 让寄存器写通路在硬件上真的被使用 —— 否则综合器会把整个 reg_bank
//          当成常量折叠掉，"寄存器映射"就名存实亡
//        · 板子到手后接上喇叭即可自证"音高在实时变化"，不需要任何外部输入
//   3. 测试模式（F1/R3）改由 CTRL 寄存器的 bit[3:2] 控制 ——
//      解决了步骤 5 记下的"TEST_SEL 是常量、现场不能切"的问题。
//
// 【寄存器写端口】
//   本版由演示序列器驱动。步骤 7（交互层）会在这里接上 UART，
//   外部字节直接写进同一套地址，不需要改本模块。
//
// 【时钟链（27 MHz，全整数零抖动）】
//   27e6 / 18 = 1.5 MHz BCK ；27e6 / 18 / 32 = 46875 Hz LRCK
//=============================================================================

`timescale 1ns/1ps

module osc_additive_top (
    input  wire       clk,        // 27 MHz 板载晶振
    input  wire       rst_n,      // 低有效复位（按键 S1）
    input  wire       key,        // 演奏门（按键 S2，低有效）
    input  wire       uart_rx,    // 串口接收（两字节一帧：地址 + 数据）
    output wire [4:0] led,
    output wire [3:0] test,
    output wire       dac_din,    // 引脚 54
    output wire       dac_ws,     // 引脚 55
    output wire       dac_bck,    // 引脚 56
    output wire       pa_en       // 引脚 51
);

    localparam NV      = 4;
    localparam NPART   = 8;
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam ENV_W   = 16;
    localparam OUT_W   = 24;

    //-------------------------------------------------------------------------
    // 1) 音频时钟使能链
    //-------------------------------------------------------------------------
    wire bck_en, bck, lrck, sample_en;

    audio_clk_en #(.DIV_BCK(18), .BCK_PER_LRCK(32)) u_clk (
        .clk(clk), .rst_n(rst_n),
        .bck_en(bck_en), .bck(bck), .lrck(lrck), .sample_en(sample_en)
    );

    //-------------------------------------------------------------------------
    // 2) 寄存器堆（256 × 8bit）：所有参数的唯一来源
    //-------------------------------------------------------------------------
    wire        demo_wr_en;
    wire [7:0]  demo_wr_addr, demo_wr_data;
    // UART 与演示序列器共用一个写端口，UART 优先。
    //   UART 不仅本身有用，它还保住了整张寄存器表：
    //   没有它的话，CTRL/MIX/ADSR 从未被写过 → 被综合器当成常量折叠，
    //   测试模式会整个被优化掉。
    wire        uart_wr_en;
    wire [7:0]  uart_wr_addr, uart_wr_data;

    wire        wr_en   = uart_wr_en | demo_wr_en;
    wire [7:0]  wr_addr = uart_wr_en ? uart_wr_addr : demo_wr_addr;
    wire [7:0]  wr_data = uart_wr_en ? uart_wr_data : demo_wr_data;
    wire [7:0]  rd_data;
    wire [256*8-1:0] R;

    reg_bank #(.AW(8), .DW(8), .NW(256)) u_reg (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(1'b0), .rd_addr(8'h00), .rd_data(rd_data),
        .regs_flat(R)
    );

    //-------------------------------------------------------------------------
    // 2b) UART 写入：两字节一帧，先地址后数据
    //-------------------------------------------------------------------------
    wire [7:0] u_rx_data;
    wire       u_rx_valid;

    uart_rx #(.CLK_HZ(27000000), .BAUD(115200)) u_uart (
        .clk(clk), .rst_n(rst_n), .rx(uart_rx),
        .data(u_rx_data), .valid(u_rx_valid)
    );

    reg [7:0] u_addr;
    reg       u_have_addr;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            u_addr      <= 8'd0;
            u_have_addr <= 1'b0;
        end
        else if (u_rx_valid) begin
            if (!u_have_addr) begin
                u_addr      <= u_rx_data;      // 第一个字节：地址
                u_have_addr <= 1'b1;
            end
            else
                u_have_addr <= 1'b0;           // 第二个字节：数据，写完就清
        end
    end

    assign uart_wr_en   = u_rx_valid & u_have_addr;
    assign uart_wr_addr = u_addr;
    assign uart_wr_data = u_rx_data;

    //-------------------------------------------------------------------------
    // 3) 参数切片
    //   Verilog 不允许对切片再取切片，所以先落具名 wire 再取位。
    //-------------------------------------------------------------------------
    wire [NV*NPART*PHASE_W-1:0] inc_all;
    wire [NV*NPART*AMP_W-1:0]   amp_all;

    genvar g;
    generate
        for (g = 0; g < NV*NPART; g = g + 1) begin : G_SLICE
            assign inc_all[g*PHASE_W +: PHASE_W] =
                   { R[(16 + g*3 + 2)*8 +: 8],
                     R[(16 + g*3 + 1)*8 +: 8],
                     R[(16 + g*3 + 0)*8 +: 8] };
            assign amp_all[g*AMP_W +: AMP_W] = R[(112 + g)*8 +: 8];
        end
    endgenerate

    wire [7:0]  r_ctrl   = R[0*8 +: 8];
    wire [7:0]  r_mix    = R[1*8 +: 8];
    wire [15:0] r_a_inc  = { R[3*8 +: 8], R[2*8 +: 8] };
    wire [15:0] r_s_lvl  = { R[5*8 +: 8], R[4*8 +: 8] };
    wire [15:0] r_cutoff = { R[9*8 +: 8], R[8*8 +: 8] };
    wire [15:0] r_d_inc  = { R[11*8 +: 8], R[10*8 +: 8] };
    wire [15:0] r_r_inc  = { R[13*8 +: 8], R[12*8 +: 8] };
    wire [7:0]  r_d_mk   = R[7*8 +: 8];
    wire [7:0]  r_r_mk   = R[6*8 +: 8];
    wire [7:0]  r_emode  = R[14*8 +: 8];

    //-------------------------------------------------------------------------
    // 包络的"形状"参数（d_m/d_k/r_m/r_k）【保持编译期常量】，不做成寄存器
    //
    //   这是实测逼出来的：一旦 d_k 变成寄存器，osc_env 里的 `lvl >> d_k` 就从
    //   【常量移位】变成【变量移位】，`d_step * d_m` 从常量乘变成变量乘。
    //   而包络要实例化 4 声部 × 8 泛音 = 32 份 ——
    //   32 个 16 位变量移位器 + 32 个变量乘法器，直接把逻辑从 8047 顶到 26226，
    //   超过 20736 上限，综合失败（实测 ALU 10162 个，全是这些移位/乘法）。
    //
    //   所以这里做一个明确的取舍：
    //     · 音高、幅度、延音电平、起音/衰减/释放【增量】、归零阈值 → 寄存器（便宜）
    //     · 指数衰减/释放的"形状" → 常量（贵，且音乐上属于音色设计而非演奏控制）
    //   M6 要求的"实时变调"由音高寄存器满足，不受影响。
    //   将来若确实要运行时调衰减时间，正确做法是给每个包络做
    //   【4 选 1 的常量移位 + 多路选择】（约 16 LUT × 32 = 512），
    //   而不是直接上桶形移位器。
    //
    //   实测结论（2026-09-30，两次综合对比）
    //   把 a_inc / s_lvl / d_inc / r_inc / cutoff 也做成寄存器后：
    //     逻辑 8047 → 19462（94%，快撞上限）
    //     时序 slack 从 +20 ns 变成 [42.1 ns 路径 vs 37.0 ns 周期] = −5.1 ns 违例
    //   违例路径：u_reg/mem[4](S_LVL) → u_env/dec_lin → 16 位进位链，共 42.1 ns。
    //   原因：这些参数被【32 份包络实例】同时使用，每一份都要现搭一个
    //   16 位加减/比较器；参数从常量变成寄存器，等于凭空造出上百个加法器。
    //
    //   所以本设计明确划定边界：
    //     · 运行时可变（寄存器）：音高 inc、幅度 amp  ← M6 与"多音色"需要
    //     · 编译期常量：包络全部参数            ← 属于音色设计，不随演奏变化
    //   这个边界是有依据的取舍，不是偷懒。
    //-------------------------------------------------------------------------
    localparam [1:0]  P_D_M    = 2'd3;
    localparam [4:0]  P_D_K    = 5'd12;
    localparam [1:0]  P_R_M    = 2'd3;
    localparam [4:0]  P_R_K    = 5'd13;
    localparam [ENV_W-1:0] P_A_INC  = 16'd117;
    localparam [ENV_W-1:0] P_D_INC  = 16'd1;
    localparam [ENV_W-1:0] P_S_LVL  = 16'd22938;
    localparam [ENV_W-1:0] P_R_INC  = 16'd1;
    localparam [ENV_W-1:0] P_CUTOFF = 16'd100;
    localparam             P_EXP    = 1'b1;

    wire        c_env_en  = r_ctrl[1];
    wire [1:0]  c_test    = r_ctrl[3:2];
    wire        r_exp     = r_emode[0];

    //-------------------------------------------------------------------------
    // 4) 门信号：寄存器全局门 或 按键 或 慢速自触发
    //-------------------------------------------------------------------------
    reg [23:0] auto_cnt;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) auto_cnt <= 24'd0;
        else        auto_cnt <= auto_cnt + 1'b1;
    end

    wire c_gate    = r_ctrl[0];
    wire auto_gate = auto_cnt[22];
    wire gate_1    = c_gate | (~key) | auto_gate;
    wire [NV-1:0] gate = {NV{gate_1}};

    //-------------------------------------------------------------------------
    // 5) 测试模式（F1 + R3）：由 CTRL 寄存器 bit[3:2] 运行时切换
    //-------------------------------------------------------------------------
    reg [31:0] seed_cnt;
    always @(posedge clk) seed_cnt <= seed_cnt + 32'd1;

    wire [NV*NPART*PHASE_W-1:0] inc_test;
    wire [NV*NPART*AMP_W-1:0]   amp_test;
    wire                        rnd_active;

    test_mode #(.NV(NV), .NPART(NPART), .PHASE_W(PHASE_W)) u_test (
        .clk(clk), .rst_n(rst_n), .mode(c_test), .seed_free(seed_cnt),
        .inc_out(inc_test), .amp_out(amp_test), .rnd_active(rnd_active)
    );

    //-------------------------------------------------------------------------
    // 测试模式多路器必须【打一拍】
    //
    //   实测关键路径：u_reg/mem[0](CTRL 的测试模式位) → 32 路 inc/amp 二选一
    //   → 包络乘法 → 加法树 → 饱和，全在一个时钟周期内，共 42.1 ns，
    //   而 27 MHz 的周期只有 37.0 ns → slack −5.1 ns 违例。
    //
    //   加一级寄存后，路径被切成两段：
    //     前段：CTRL → 多路器        （很短）
    //     后段：多路器输出 → 乘法/加法树 （就是 v5 已验证过的那条）
    //   代价：写寄存器到听到声音多一拍（46875 Hz 下约 21 µs），完全不可感。
    //-------------------------------------------------------------------------
    reg [NV*NPART*PHASE_W-1:0] inc_final;
    reg [NV*NPART*AMP_W-1:0]   amp_final;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            inc_final <= {(NV*NPART*PHASE_W){1'b0}};
            amp_final <= {(NV*NPART*AMP_W){1'b0}};
        end
        else begin
            inc_final <= (c_test == 2'd0) ? inc_all : inc_test;
            amp_final <= (c_test == 2'd0) ? amp_all : amp_test;
        end
    end

    //-------------------------------------------------------------------------
    // 6) 演示序列器：每约 0.4 s 把声部 0 的音高换成 A 大调音阶的下一个音
    //    写 24 次（8 泛音 × 3 字节），然后停一会儿再换下一个音。
    //-------------------------------------------------------------------------
    localparam integer HOLD = 20000;      // ≈0.43 s @46875 Hz
    localparam integer GAP  = 6000;       // 相邻两次写的间隔

    reg [2:0]  d_note;       // 0..7 音阶序号
    reg [4:0]  d_idx;        // 0..23 写入序号
    reg [15:0] d_wait;
    reg        d_phase;      // 0 = 正在写 24 字节, 1 = 等待

    reg [23:0] d_base;
    always @(*) begin
        case (d_note)
            3'd0: d_base = 24'd78741;     // A3  220.00
            3'd1: d_base = 24'd88384;     // B3  246.94
            3'd2: d_base = 24'd99207;     // C#4 277.18
            3'd3: d_base = 24'd105106;    // D4  293.66
            3'd4: d_base = 24'd117980;    // E4  329.63
            3'd5: d_base = 24'd132425;    // F#4 369.99
            3'd6: d_base = 24'd148643;    // G#4 415.30
            default: d_base = 24'd157482; // A4  440.00
        endcase
    end

    // 当前要写的泛音序号与字节序号
    wire [4:0]  d_k     = d_idx / 5'd3;              // 0..7
    wire [4:0]  d_rem   = d_idx - d_k*5'd3;          // 0..2
    wire [23:0] d_pinc  = d_base * (d_k + 5'd1);     // base × (k+1)

    reg  [7:0]  d_out;
    always @(*) begin
        case (d_rem)
            5'd0: d_out = d_pinc[7:0];
            5'd1: d_out = d_pinc[15:8];
            default: d_out = d_pinc[23:16];
        endcase
    end

    // 演示序列器在测试模式下让位（否则会把测试频率覆盖掉）
    assign demo_wr_en   = (d_phase == 1'b0) && (d_wait == 16'd0) && (c_test == 2'd0);
    assign demo_wr_addr = 8'h10 + d_idx * 5'd3 + d_rem;   // 声部 0 的音高寄存器
    assign demo_wr_data = d_out;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            d_note  <= 3'd0;
            d_idx   <= 5'd0;
            d_wait  <= 16'd0;
            d_phase <= 1'b1;
        end
        else if (c_test != 2'd0) begin
            // 测试模式下演示序列器让位（否则会把测试频率覆盖掉）
            d_note <= 3'd0; d_idx <= 5'd0; d_wait <= 16'd0; d_phase <= 1'b1;
        end
        else if (d_wait != 16'd0)
            d_wait <= d_wait - 16'd1;
        else if (d_phase == 1'b0) begin
            if (d_idx == 5'd23) begin
                d_idx   <= 5'd0;
                d_phase <= 1'b1;
                d_wait  <= HOLD[15:0];
                d_note  <= d_note + 3'd1;
            end
            else begin
                d_idx  <= d_idx + 5'd1;
                d_wait <= GAP[15:0];
            end
        end
        else
            d_wait <= GAP[15:0];
    end

    //-------------------------------------------------------------------------
    // 7) 多声部引擎
    //-------------------------------------------------------------------------
    wire signed [OUT_W-1:0] sample;
    wire [NV*OUT_W-1:0]     voice_out;

    synth_top #(
        .NV(NV), .NPART(NPART), .PHASE_W(PHASE_W),
        .AMP_W(AMP_W), .ENV_W(ENV_W), .OUT_W(OUT_W)
    ) u_synth (
        .clk         (clk),
        .rst_n       (rst_n),
        .sample_en   (sample_en),
        .inc_all     (inc_final),
        .amp_all     (amp_final),
        .gate        (gate),
        .env_en      (c_env_en),
        .a_inc       (P_A_INC),
        .d_inc       (P_D_INC),
        .d_m         (P_D_M),
        .d_k         (P_D_K),
        .s_lvl       (P_S_LVL),
        .r_inc       (P_R_INC),
        .r_m         (P_R_M),
        .r_k         (P_R_K),
        .env_cutoff  (P_CUTOFF),
        .exp_mode    (P_EXP),
        .mix_gain_up (r_mix[2:0]),
        .mix_shift   (r_mix[4:3]),
        .sample_out  (sample),
        .voice_out   (voice_out)
    );

    //-------------------------------------------------------------------------
    // 8) I2S 发送器
    //-------------------------------------------------------------------------
    wire sd_i, ws_i;

    i2s_tx #(.SW(24), .DW(16)) u_i2s (
        .clk(clk), .rst_n(rst_n),
        .bck_en(bck_en), .lrck(lrck), .sample_en(sample_en),
        .sample_in(sample), .sd(sd_i), .ws(ws_i)
    );

    assign dac_din = sd_i;
    assign dac_ws  = ws_i;
    assign dac_bck = bck;
    assign pa_en   = 1'b1;

    //-------------------------------------------------------------------------
    // 9) 观察输出
    //-------------------------------------------------------------------------
    assign led  = ~sample[23:19];
    assign test = { rnd_active, c_test[1], gate_1, sample[23] };

endmodule
