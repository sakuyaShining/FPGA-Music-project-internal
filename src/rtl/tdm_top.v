//=============================================================================
// tdm_top.v —— TDM 合成引擎的顶层（可演奏 + 可测试 + 运行时参数可写）
//
// 【两种模式，共用同一套引擎】
//   test_mode = 0  演奏模式：note_map 把音符事件展开成时隙装载
//   test_mode = 1  测试模式：512 个时隙各占一个等间隔频率，用于数谱峰
//
//   ★ 为什么必须保留测试模式：
//     赛题"核心评分规则·现场验证要求"明确要求
//     "支持测试模式下输出多路不同频率音频，频谱可观测对应数量独立谱峰"。
//     接上音符映射之后如果只剩"演奏"，这条现场验证就没了 ——
//     所以是【加一条通路】，不是替换。
//
// 【资源与时隙】
//   NG = 32 组 × P = 16 泛音 = NSLOT 512
//   每样本 576 拍（27 MHz / 46875 Hz），TDM 流水线要 LAT=4 拍排空
//   => 最多 572 个时隙，取 2 的幂 = 512 —— 正好用满 89% 的时间预算
//   => 最大复音 32 音（对应赛题拓展要求 1 的"复音数 ≥32"）
//
// 【演奏接口】
//   音符事件由外部驱动（测试台 / 交互层）。顶层只认"音符事件"这个抽象，
//   换传感器不用动这里。
//
// 【2026-10-01 改动】
//   原来是一段"开机自动装载固定频率栅格"的 boot 序列器，且驱动着
//   boot_clr / boot_pclr —— 而这两个信号在引擎里早已没有逻辑。
//   现在改成：演奏走 note_map，测试走显式栅格装载器，两者都是活代码。
//
// 【2026-10-02 改动：运行时参数通道】
//   接上 reg_bank + uart_rx，"表情调制参数"与"音色"从编译期常量变成
//   运行时可写 —— 这是拓展 E2（≥3 维表情：力度/滑音/颤音）与
//   E3（≥2 音色切换）从"结构存在"变成"演奏时可操控"的关键一步，
//   同时也是必须项 M1/M9（交互层）的地基：交互层只要
//   "写寄存器 + 发音符事件"两件事。
//   默认值刻意与加这条通路之前【完全一致】（滑音开、颤音关、音色走引脚）。
//=============================================================================

`timescale 1ns/1ps

module tdm_top (
    input  wire       clk,
    input  wire       rst_n,

    //---- 演奏接口（交互层接这里）----
    //   ★ ev_vel 用 4 位（16 级力度）而不是 8 位：
    //     板上的 40-pin 排针只有 18 根可用（27-42/48/77），而
    //     valid(1)+on(1)+note(7)+preset(2)+test_mode(1) 已占 12 根，
    //     8 位力度会超出。4 位在音乐上完全够用，内部左移 4 位补齐。
    //     这样 note_map 与所有测试台都保持 8 位不变，改动面最小。
    input  wire       ev_valid,
    input  wire       ev_on,        // 1 = 音符开, 0 = 音符关
    input  wire [6:0] ev_note,      // MIDI 音符号 0..127
    input  wire [3:0] ev_vel,       // 力度（16 级）
    input  wire [1:0] preset,       // 音色预设（引脚；可被寄存器覆盖，见 CTRL[3]）

    //---- 模式 ----
    input  wire       test_mode,    // 0 = 演奏, 1 = 测试（频率栅格）；寄存器也可置起

    //---- 运行时参数通道（UART，115200 8N1，两字节一帧：地址 + 数据）----
    //   引脚见 src/constr/tdm_top.cst：uart_rx = 70（BL616 板载 USB 串口）
    input  wire       uart_rx_pin,
    output wire       uart_tx_pin,   // ★ E8：串口发送（BL616 板载 USB 串口，引脚 69）

    //---- 状态与音频 ----
    output wire [5:0] led,          // ★ 板上是 6 个 LED（官方 blink_leds.cst）
    output wire       dac_din,
    output wire       dac_ws,
    output wire       dac_bck,
    output wire       pa_en,

    //-------------------------------------------------------------------------
    // 16 路电容触摸电极（步①b，docs/02-技术方案/20-pad扫描规格书.md）
    //   左手 pad[7:0]  = 音高键（五声音阶 C4 D4 E4 G4 A4 C5 D5 E5）
    //   右手 pad[15:8] = 泛音键（→ 0x5B HARM_PADS，步③ 接上）
    //   ★ 必须是 inout：同一根线分时做 推高充电 / 高阻放电 / 读回
    //   ★ 引脚 27..42（40P 排针）——而 ev_*/preset/test_mode 的 IO_LOC 因此在 cst 里
    //     改为"只保留 PULL_MODE=DOWN、不指定引脚"（A6：ev_* 不上引脚；
    //     A2：test_mode 下拉）⇒ 悬空输入一律读 0，不会产生幽灵事件 ✓
    //-------------------------------------------------------------------------
    inout  wire [15:0] pad
);

    localparam NSLOT   = 512;
    localparam NG      = 32;
    localparam P       = 16;
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam ENV_W   = 16;
    localparam OUT_W   = 24;

    //=========================================================================
    // 运行时参数：reg_bank + UART + 开机自举
    //
    // 【为什么要有"开机自举写入"这一段】
    //   寄存器表只要有一个字节永远不被写，那一块逻辑就有被综合器
    //   常量折叠吃掉的风险（教训记在 uart_rx.v 顶部）。
    //   开机自举让每个用到的寄存器都经由【真实写端口】写过一次，
    //   既给出确定的默认值，又保证通路活着。
    //
    // 【地址映射（本顶层）】
    //   0x00      CTRL      [0]测试模式 [1]颤音开 [2]滑音开 [3]音色源(0=引脚 1=寄存器)
    //   0x30-32   VIB_INC   LFO 频率字（小端 24 位）= f × 2^24 / fs
    //   0x33-34   VIB_DEPTH 颤音深度（小端 16 位，Q16 比例）
    //   0x35-36   GLIDE_STEP 滑音速率（小端 16 位，Q16/样本）
    //              时长 = |初值| / 该值；例：12 个半音(32768) / 10 ≈ 3277 样本 ≈ 62 ms
    //   0x37      PRESET    [1:0]音色
    //   0x40      FX_CTRL   [0]干声 [1]延迟 [2]合唱 [5:3]湿声右移(增益 1/2^n)
    //   0x41-42   DELAY_LEN 延迟抽头（小端 16 位，样本）
    //   0x43      FEEDBACK  延迟反馈（Q8）
    //   0x44-45   CHORUS_RATE 合唱 LFO 频率字（小端 16 位）
    //   0x46-47   CHORUS_DEPTH 合唱深度（小端 16 位，样本）
    //   0x50      SEQ_CTRL  [0]定序器使能 [1]暂停/复位（电平）
    //   0x51-53   TEMPO_INC 每样本拍数（小端 24 位，Q24）
    //              = (BPM/60) × 2^24 / fs；BPM=120、fs=52734.375 → 636
    //   0x54      SEQ_VEL  定序器发的力度（0..255）
    //   其余保留（256 字节地址空间，多留不花钱）
    //
    // 【默认值 = 与加寄存器通路之前完全一致】
    //   test_mode=0（演奏档）、颤音关、滑音开、音色走引脚
    //   ⇒ 测试模式的 512 谱峰不会被颤音抹开（现场自证要求）；
    //     演奏档的既有行为不变。
    //=========================================================================
    wire        u_rx_valid;
    wire [7:0]  u_rx_data;
    reg  [7:0]  u_addr;
    reg         u_have_addr;

    uart_rx #(.CLK_HZ(27000000), .BAUD(115200)) u_uart (
        .clk(clk), .rst_n(rst_n), .rx(uart_rx_pin),
        .data(u_rx_data), .valid(u_rx_valid)
    );

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

    wire        uart_wr_en   = u_rx_valid & u_have_addr;
    wire [7:0]  uart_wr_addr = u_addr;
    wire [7:0]  uart_wr_data = u_rx_data;

    //---- 开机自举序列（复位释放后逐个写入默认值）----
    reg [5:0]  b_idx;    // ★ 4→5→6 位：引导序列现在 44 条（新增 16 次谱 RAM 清零）
    reg        b_done;
    reg        b_wr_en;
    reg [7:0]  b_addr, b_data;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            b_idx   <= 5'd0;
            b_done  <= 1'b0;
            b_wr_en <= 1'b0;
            b_addr  <= 8'd0;
            b_data  <= 8'd0;
        end
        else begin
            b_wr_en <= 1'b0;
            if (!b_done) begin
                b_wr_en <= 1'b1;
                case (b_idx)
                    5'd0:  begin b_addr <= 8'h00; b_data <= 8'h02; end // CTRL（A4）：测试关 / VIB_EN=1（深度 0 ⇒ inert）/ GLIDE_EN=0 / preset_src=0
                    5'd1:  begin b_addr <= 8'h30; b_data <= 8'h00; end // VIB_INC   = 0（19 号 §3 默认 0）
                    5'd2:  begin b_addr <= 8'h31; b_data <= 8'h00; end
                    5'd3:  begin b_addr <= 8'h32; b_data <= 8'h00; end
                    5'd4:  begin b_addr <= 8'h33; b_data <= 8'h00; end // VIB_DEPTH = 0（★ VP7"颤音关"✓；原来默认 950 ✗）
                    5'd5:  begin b_addr <= 8'h34; b_data <= 8'h00; end
                    5'd6:  begin b_addr <= 8'h35; b_data <= 8'h00; end // GLIDE_STEP= 0（★ 19 号 §3 默认 0；原来 10 ✗）
                    5'd7:  begin b_addr <= 8'h36; b_data <= 8'h00; end
                    5'd8:  begin b_addr <= 8'h37; b_data <= 8'h00; end // PRESET = 0（19 号 §3 默认 0；★ 原来写 1 ✗）
                    // ---- 效果器默认值：干声直通、两个效果都关 ----
                    //   ⇒ 顶层旁路 mux 让音频完全绕开 fx_delay，
                    //     于是旁路时输出与"没有效果器"逐位相同。
                    5'd9:  begin b_addr <= 8'h40; b_data <= 8'h01; end // FX_CTRL: 仅干声
                    6'd10: begin b_addr <= 8'h41; b_data <= 8'hDC; end // DELAY_LEN = 1500（必须 < 2^AW=2048，
                    6'd11: begin b_addr <= 8'h42; b_data <= 8'h05; end //   (0x05DC=1500 ≈ 28 ms；
                    6'd12: begin b_addr <= 8'h43; b_data <= 8'h60; end // FEEDBACK = 0x60 (0.375)
                    6'd13: begin b_addr <= 8'h44; b_data <= 8'hAE; end // CHORUS_RATE = 430
                    6'd14: begin b_addr <= 8'h45; b_data <= 8'h01; end //   (0x01AE ≈ 1.35 Hz)
                    6'd15: begin b_addr <= 8'h46; b_data <= 8'h40; end // CHORUS_DEPTH = 64 样本
                    6'd16: begin b_addr <= 8'h47; b_data <= 8'h00; end
                    // ---- 定序器默认值：使能位为 0（保持"外部演奏"语义）----
                    6'd17: begin b_addr <= 8'h50; b_data <= 8'h00; end // SEQ_CTRL: 关
                    6'd18: begin b_addr <= 8'h51; b_data <= 8'h7C; end // TEMPO_INC = 636
                    6'd19: begin b_addr <= 8'h52; b_data <= 8'h02; end //   (0x027C ≈ 120 BPM)
                    6'd20: begin b_addr <= 8'h53; b_data <= 8'h00; end
                    6'd21: begin b_addr <= 8'h48; b_data <= 8'h80; end // REV_FB = 0x80 (0.5) ★ 第 9 轮：0xC0 会让线缓冲饱和削顶（实测 91.9% ✗）
                    6'd22: begin b_addr <= 8'h49; b_data <= 8'h03; end // REV_DAMP = 3
                    6'd23: begin b_addr <= 8'h54; b_data <= 8'h80; end // SEQ_VEL = 128
                    // ★ 步③：塑谱模式显式上电默认 = 0x02（bit1 自动刷新开、bit0=0 叠加）
                    //   ⇒ 上电有声、不塑形时与未加塑谱逐位相同 ✓
                    //   ★ 不写 0x61（NOTE_TRIG）：那会触发一次幽灵音符事件 ✗
                    //   ★ 0x60 NOTE_NUM 写 0（无待发音符 ✓）
                    6'd24: begin b_addr <= 8'h5A; b_data <= 8'h02; end // SPEC_MODE = 叠加+自动刷新
                    6'd25: begin b_addr <= 8'h60; b_data <= 8'h00; end // NOTE_NUM = 0
                    // ★★ 0x5B HARM_PADS 必须显式清零！reg_bank 里那一片是【并行版的紧凑
                    //    泛音表】遗留垃圾 ✗，其中 3 位为 1 ⇒ 会被当成"右手摸到 3 根电极"
                    //    ⇒ 那 3 个泛音被 boost 到 255 ⇒ 闸口 E3 实测"预设只匹配 13/16" ✗✗
                    //    （这正是 ZCode 的审计发现 A1："上电状态从未被定义过" 的现行犯 ✓）
                    6'd26: begin b_addr <= 8'h5B; b_data <= 8'h00; end // HARM_PADS = 0
                    // ★★ 塑谱 RAM 显式清零（17 条：0x58 指针归零 + 16 次 0x59 写 0）
                    //   为什么必须在引导里做：谱 RAM 的 `initial` 初值只在仿真里有效 ✗，
                    //   而综合后**未初始化的 RAM 读出来是 x** ✗ ⇒ 一旦某个测试台没写谱
                    //   （或上电后主机还没写谱），幅度整条链就是 x ✗✗。
                    //   实测教训：这正是"闸口 E3 只匹配 13/16 → 后来整片 x"的根源 ✓
                    //   ⇒ 显式写 0 之后：任何构建（含不带 -DSIM_INIT 的）都是确定的 ✓✓
                    6'd27: begin b_addr <= 8'h58; b_data <= 8'h00; end // SPEC_IDX = 0
                    6'd28: begin b_addr <= 8'h59; b_data <= 8'h00; end // 谱[0]  = 0
                    6'd29: begin b_addr <= 8'h59; b_data <= 8'h00; end // 谱[1]  = 0
                    6'd30: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd31: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd32: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd33: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd34: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd35: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd36: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd37: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd38: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd39: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd40: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd41: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd42: begin b_addr <= 8'h59; b_data <= 8'h00; end
                    6'd43: begin b_addr <= 8'h59; b_data <= 8'h00; end // 谱[15] = 0
                    6'd44: begin b_wr_en <= 1'b0; b_done <= 1'b1; end
                    default: begin b_wr_en <= 1'b0; b_done <= 1'b1; end
                endcase
                if (b_idx != 6'd44) b_idx <= b_idx + 6'd1;
            end
        end
    end

    //---- 写端口仲裁：自举 > 主机 UART > 遥测（第 7 轮加的第三源）----
    //   遥测优先级最低 ⇒ 撞上时丢掉一次遥测写（下一轮会补 ✓），
    //   绝不会干扰自举序列或主机命令 ✓
    //   ★ 遥测相关的声明必须在这里（使用前）✓ 详见下方"电极遥测寄存器"一节
    wire [3:0]   r_pad_sel;      // 0x66 PAD_SEL：主机选通道 0–15
    wire [11:0]  pad_raw_sel;    // 来自 pad_scan：该通道裸计数
    wire [11:0]  pad_base_sel;   // 来自 pad_scan：该通道基线
    reg  [12:0]  pmon_cnt;
    reg  [2:0]   pmon_st;
    reg          pmon_we;
    reg  [7:0]   pmon_addr, pmon_data;

    wire        wr_en   = b_wr_en | uart_wr_en | pmon_we;
    wire [7:0]  wr_addr = b_wr_en ? b_addr : (uart_wr_en ? uart_wr_addr : pmon_addr);
    wire [7:0]  wr_data = b_wr_en ? b_data : (uart_wr_en ? uart_wr_data : pmon_data);

    // ★ 寄存器堆保持 256 项：曾试过收到 128（想省回读 mux 的 LUT），
    //   但 reg_bank.v 里有一段【并行设计遗留的 256 项初值】，
    //   综合直接报 EX3784 "Index 128 is out of range" ✗。
    //   那个模块是全并行版共用的，不适合为省 LUT 去动它的初值 —— 于是回退。
    // ★ 2026-10-03（第 7 轮）：NW 256 → **128**（地址 0x00–0x7F）
    //   动机：`regs_flat` 的**每个切片**都会综合出一棵 NW:1 读 mux ✗，
    //     全设计有几十个切片 ⇒ 256 项时这是一笔巨大的布线/查找表开销 ✓。
    //     加遥测后未布线一度涨到 187 条 ✗✗（设计贴着布线悬崖）。
    //   安全性：全工程**没有任何寄存器使用 0x80 以上** ✓
    //     （0x00–0x7F 已覆盖 §3 全部冻结地址，含 0x7F 协议版本 ✓；
    //      0x80+ 只是"E8 录音缓冲"的预留语义，尚无实现 ✓）
    //   历史障碍已消失 ✓：当年缩到 128 会被 reg_bank 里【256 项并行版初值】顶到
    //     EX3784 "Index 128 is out of range" ✗ —— 那张表已在第 5 轮 ④ 按 §3 重写 ✓
    wire [1023:0] R;      // 128 × 8

    reg_bank #(.AW(8), .DW(8), .NW(128)) u_reg (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(1'b0), .rd_addr(8'd0), .rd_data(),
        .regs_flat(R)
    );

    //---- 参数切片（Verilog 不允许对切片再取切片 → 先落具名 wire）----
    wire [7:0]  r_ctrl     = R[8'h00*8 +: 8];
    wire [23:0] r_vib_inc  = { R[8'h32*8 +: 8], R[8'h31*8 +: 8], R[8'h30*8 +: 8] };
    wire [15:0] r_vib_dep  = { R[8'h34*8 +: 8], R[8'h33*8 +: 8] };
    wire [15:0] r_gstep    = { R[8'h36*8 +: 8], R[8'h35*8 +: 8] };
    wire [1:0]  r_preset   = R[8'h37*8 +: 2];   // ★ 切片宽度要写成目标宽度，
                                                //   否则 Gowin 报 EX3791（8→2 截断）

    wire        test_mode_eff = test_mode | r_ctrl[0];   // 引脚或寄存器都能进测试档
    wire        vib_en        = r_ctrl[1];
    wire        glide_en      = r_ctrl[2];
    wire        preset_src    = r_ctrl[3];               // 0 = 引脚, 1 = 寄存器
    wire [1:0]  preset_eff    = preset_src ? r_preset : preset;

    // 表情调制参数总线（位序与 tdm_engine 的 pmod_cfg 一致，58 位）
    wire [57:0] pmod_cfg = { r_vib_inc, r_vib_dep, r_gstep, vib_en, glide_en };

    //---- 效果器参数（拓展 E4）----
    wire [7:0]  r_fxctrl = R[8'h40*8 +: 8];
    wire [15:0] r_dlylen = { R[8'h42*8 +: 8], R[8'h41*8 +: 8] };
    wire [7:0]  r_fb     = R[8'h43*8 +: 8];
    wire [15:0] r_chrate = { R[8'h45*8 +: 8], R[8'h44*8 +: 8] };
    wire [15:0] r_chdep  = { R[8'h47*8 +: 8], R[8'h46*8 +: 8] };

    wire        fx_dry_en = r_fxctrl[0];
    wire        fx_dly_en = r_fxctrl[1];
    wire        fx_cho_en = r_fxctrl[2];
    wire        fx_rev_en = r_fxctrl[6];      // ★ 混响使能
    wire [2:0]  fx_wet_sh = r_fxctrl[5:3];
    wire [7:0]  r_rev_fb  = R[8'h48*8 +: 8];
    wire [2:0]  r_rev_dmp = R[8'h49*8 +: 3];
    // 两个效果都关 → 音频绕开 fx_delay（零延迟组合 mux）
    wire        fx_active = fx_dly_en | fx_cho_en | fx_rev_en;

    //---- 定序器参数（拓展 E7）----
    wire [7:0]  r_seqctrl = R[8'h50*8 +: 8];
    wire [23:0] r_tempo   = { R[8'h53*8 +: 8], R[8'h52*8 +: 8], R[8'h51*8 +: 8] };

    //-------------------------------------------------------------------------
    // 左手音符事件（19 号 §3/§4，步① 串行化）
    //   0x60 NOTE_NUM : [7]=on/off，[6:0]=MIDI 音符号
    //   0x61 NOTE_TRIG: [3:0]=力度，**写入即触发**（valid 脉冲）
    //   两次写之间无时序要求；触发在下一个样本边界原子生效 ✓
    //   ★ 0x60 原来是回读触发器，按 A3 已让给本用途（回读移到 0x0F）✓
    //-------------------------------------------------------------------------
    wire [7:0]  r_note_num = R[8'h60*8 +: 8];
    wire [7:0]  r_seqvel  = R[8'h54*8 +: 8];
    wire        seq_en    = r_seqctrl[0];
    wire        seq_hold  = r_seqctrl[1];
    wire        seq_useram= r_seqctrl[2];    // ★ E8：0 = 内置曲谱, 1 = 下载曲谱

    //-------------------------------------------------------------------------
    // E8 的 FPGA 侧：UART 发送 + 寄存器回读 + 曲谱下载
    //
    //   回读协议【A3 冻结】：上位机往 0x0F 写一个寄存器地址 → FPGA 依次发【该地址】【该值】
//     ★ 原实现把触发器放在 0x60，而 0x60 已被冻结为 NOTE_NUM（左手音符号）⇒ 撞车：
//       每写一次音符都会顺带触发一次回读，TX 上莫名多出字节、上位机丢帧同步 ✗。
//       现在让出 0x60，触发器按修正案 A3 落到 0x0F（保留区）。
    //             两个字节（与写入的"地址+数据"两字节帧完全对称，上位机好写）。
    //   曲谱下载：往 0x70 写音高、往 0x71 写拍数（写完拍数索引自动 +1），
    //             往 0x72 写起始索引，往 0x73 写步数；再把 SEQ_CTRL[2] 置 1。
    //-------------------------------------------------------------------------
    wire [7:0]  r_snote  = R[8'h70*8 +: 8];
    wire [7:0]  r_sbeat  = R[8'h71*8 +: 8];
    wire [5:0]  r_slen   = R[8'h73*8 +: 6];

    reg  [5:0]  s_idx;                     // 曲谱写入索引
    wire        s_we_note  = wr_en && (wr_addr == 8'h70);
    wire        s_we_beats = wr_en && (wr_addr == 8'h71);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                        s_idx <= 6'd0;
        else if (wr_en && wr_addr == 8'h72) s_idx <= wr_data[5:0];   // 设索引
        else if (s_we_beats)                s_idx <= s_idx + 6'd1;   // 写完拍数自动 +1
    end

    //---- 串口发送：回读两个字节 ----
    reg  [2:0]  rb_st;
    reg  [7:0]  rb_addr, tx_data;
    reg         tx_start;
    wire        tx_done;

    uart_tx #(.CLK_HZ(27000000), .BAUD(115200)) u_tx (
        .clk(clk), .rst_n(rst_n),
        .tx_data(tx_data), .tx_start(tx_start),
        .tx(uart_tx_pin), .busy(), .done(tx_done)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rb_st <= 3'd0; tx_start <= 1'b0; rb_addr <= 8'd0; tx_data <= 8'd0;
        end
        else begin
            tx_start <= 1'b0;
            case (rb_st)
                3'd0: if (wr_en && wr_addr == 8'h0F) begin
                          rb_addr <= wr_data;
                          rb_st   <= 3'd1;
                      end
                3'd1: begin tx_data <= rb_addr; tx_start <= 1'b1; rb_st <= 3'd2; end
                3'd2: if (tx_done) rb_st <= 3'd3;
                3'd3: begin
                          tx_data  <= R[{rb_addr, 3'b000} +: 8];   // 组合读寄存器
                          tx_start <= 1'b1;
                          rb_st    <= 3'd4;
                      end
                3'd4: if (tx_done) rb_st <= 3'd0;
                default: rb_st <= 3'd0;
            endcase
        end
    end

    //-------------------------------------------------------------------------
    // 片上曲目定序器（拓展 E7）：不接电脑也能自己演奏 + 给 LED 指引
    //-------------------------------------------------------------------------
    // ★ 音频时钟声明必须放在这里（而不是下面例化处）：
    //   Verilog 里端口连线引用的 net 必须【先声明】——
    //   否则 iverilog 报 "Unable to bind wire/reg/memory `sample_en'"。
    wire        bck_en, bck, lrck, sample_en;

    wire        sq_ev_valid, sq_ev_on, sq_beat;
    wire [6:0]  sq_ev_note, sq_cur_note;
    wire [7:0]  sq_ev_vel;
    wire [7:0]  sq_step;

    song_seq #(.NB(7), .NSTEP(15)) u_seq (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .enable(seq_en), .hold(seq_hold),
        .tempo_inc(r_tempo), .vel(r_seqvel),
        // ★ E8：曲谱下载端口（默认 use_ram=0 → 用内置曲谱，行为不变）
        //   ★★ 数据源必须用【进来的字节 wr_data】，不能用寄存器 R[0x70]：
        //      reg_bank 的寄存器是同步更新的，在写使能那一拍 R[0x70] 还是
        //      【上一次写入的旧值】—— 第一版就栽在这里，曲谱写进去全是错位的。
        .ram_we(s_we_note | s_we_beats), .ram_sel(s_we_beats),
        .ram_note(wr_data[6:0]), .ram_beats(wr_data), .ram_idx(s_idx),
        .use_ram(seq_useram), .ram_len(r_slen),
        .ev_valid(sq_ev_valid), .ev_on(sq_ev_on),
        .ev_note(sq_ev_note), .ev_vel(sq_ev_vel),
        .beat_pulse(sq_beat), .cur_note(sq_cur_note), .step_dbg(sq_step)
    );

    // 事件源二选一：定序器使能时用曲谱，否则用外部演奏事件
    //   ★ 默认 seq_en = 0 → 与加定序器之前【完全一致】（既有证据继续有效）
    //-------------------------------------------------------------------------
    // ★ 三事件源并立（步①）：UART 串行事件 / 定序器 / 排针 ev_*
    //   优先级：**UART（0x61 写脉冲）> 定序器 > 排针**
    //   三者互为兜底；note_map 侧有 busy 门控，冲突时后到者被忽略（与既有行为一致）
    //   ★ 关键：u_ev_valid=0 时整条表达式与加入本功能之前【逐位相同】
    //     ⇒ 既有全部证据（R0/E1–E7）继续有效 ✓
    //   ★ 力度必须取【写入的字节 wr_data】，不能读 R[0x61]（同一拍还是旧值 ——
    //     本项目在 E8 曲谱下载上犯过这个错）
    //-------------------------------------------------------------------------
    wire        u_ev_valid = wr_en && (wr_addr == 8'h61);
    wire        u_ev_on    = r_note_num[7];
    wire [6:0]  u_ev_note  = r_note_num[6:0];
    wire [3:0]  u_ev_vel   = wr_data[3:0];

    //-------------------------------------------------------------------------
    // ★ 步①b：pads 作为第 4 个事件源（左手音高键 → note 事件）
    //   优先级：UART > 定序器 > **pads** > 排针 ev_*
    //   ★ 测试台不接 pad 端口 ⇒ 线浮空读 z ⇒ pad_scan 的计数恒 0
    //     ⇒ 基线 0、阈值 0 ⇒ 既不会"触摸"也不会"释放" ⇒ **零事件** ✓
    //     所以既有 15 个测试台的行为完全不变 ✓
    //   ★ nm_busy 必须在【使用前】声明（本项目惯犯陷阱：先声明后使用 ✗）
    //-------------------------------------------------------------------------
    wire        nm_busy;                   // note_map 忙（在下面例化时接上）
    wire        pd_ev_valid, pd_ev_on;
    wire [6:0]  pd_ev_note;
    wire [15:0] pad_state;                 // 位图：bit0-7 左手音高，bit8-15 右手泛音
    wire [15:0] pad_harm_state = pad_state[15:8];

    pad_scan #(.NCH(16)) u_pad (
        .clk(clk), .rst_n(rst_n),
        .pad(pad),
        .note_busy(nm_busy),
        .oct_up(1'b0),                     // v1 固定不升八度（S2 留 v2）
        .state(pad_state),
        .ev_note(pd_ev_note), .ev_on(pd_ev_on), .ev_valid(pd_ev_valid),
        .dbg_raw0(), .dbg_base0(), .dbg_phase(),
        .dbg_sel(r_pad_sel),                   // ★ 第 7 轮遥测：主机选通道
        .dbg_raw_sel(pad_raw_sel),
        .dbg_base_sel(pad_base_sel)
    );

    //-------------------------------------------------------------------------
    // ★ 步③ 塑谱寄存器（19 号 §3/§4 + 修正案 A1）
    //   0x58 SPEC_IDX  谱 RAM 写指针 0–15（写 0x59 后自动 +1）
    //   0x59 SPEC_VAL  谱 RAM 数据（写入即生效）
    //   0x5A SPEC_MODE [0] 1=替换(只用谱)/0=叠加(预设+谱)  [1] 谱/pad 变化后自动刷新在响声部
    //                  ★ 默认取 0x02 ⇒ bit0=0 ⇒ 叠加 ✓ 上电有声 ✓
    //                    （19 号 §3 的位定义文字与它自己的默认值矛盾 ✗，按默认值+注释实现 ✓ 已登记）
    //   0x5B HARM_PADS 右手电极软掩码（与物理 pad 按位或 ✓）
    //   0x63 SPEC_REFRESH 0–31 刷该声部 / 0xFF 全刷（写即触发 ✓ A1）
    //-------------------------------------------------------------------------
    wire [7:0]  r_spec_mode = R[8'h5A*8 +: 8];
    wire [7:0]  r_harm_pads = R[8'h5B*8 +: 8];
    wire        spec_replace = r_spec_mode[0];      // 1=替换 / 0=叠加
    wire        spec_autorf  = r_spec_mode[1];

    reg  [3:0]  spec_idx;
    reg         spec_we;
    reg  [3:0]  spec_addr;
    reg  [7:0]  spec_wdata;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spec_idx <= 4'd0; spec_we <= 1'b0; spec_addr <= 4'd0; spec_wdata <= 8'd0;
        end
        else begin
            spec_we <= 1'b0;                        // 1 拍脉冲
            if (wr_en && wr_addr == 8'h58) spec_idx <= wr_data[3:0];
            else if (wr_en && wr_addr == 8'h59) begin
                spec_we    <= 1'b1;
                spec_addr  <= spec_idx;
                spec_wdata <= wr_data;
                spec_idx   <= spec_idx + 4'd1;      // 写后自动 +1 ✓
            end
        end
    end

    // 右手泛音键掩码 = 软寄存器 0x5B ｜ 物理电极（pad_state[15:8]）
    wire [15:0] pad_mask_eff = {8'd0, (r_harm_pads | pad_state[15:8])};

    //-------------------------------------------------------------------------
    // ★★★ 第 7 轮：电极遥测寄存器（上板 bring-up 的唯一使能条件 ✓）
    //
    // 为什么必须做：`步骤16 §1` 的头号上板风险是"**RC 绝对量程未知**" ✗ ——
    //   内部下拉电阻与电极电容都不知道 ⇒ 放电可能太快（分辨不出）或
    //   计数器封顶（永远摸不着）✗✗。而这两个量以前**只有内部 dbg_* 线**，
    //   主机读不到 ⇒ 插上板也**没法量** ✗。本模块把它们搬到保留寄存器区 ✓。
    //
    // 协议（19 号 §5 的 0x64+ 预留区，不破坏 v1.0 冻结表 ✓）：
    //   0x66 PAD_SEL  [3:0] 选通道 0–15（**主机写**，遥测不碰它 ✓）
    //   0x64 PAD_BASE_LO   0x65 PAD_BASE_HI     该通道基线（12 位）
    //   0x67 PAD_RAW_LO    0x68 PAD_RAW_HI      该通道裸计数（12 位）
    //   0x69 PAD_ST_LO     0x6A PAD_ST_HI       16 路触摸位图
    // 上位机读法（A3 冻结协议 ✓）：写 [0x0F][0x64] ⇒ FPGA 回 [0x64][值] 两字节
    //   工具：`python tools/scripts/dsp_host.py padmon --port COMx`
    //
    // 节流：每 4096 拍刷一遍（≈152 µs ✓ 远快于手势 ✓，也不会挤占主机写带宽 ✓）
    //   （声明已在"写端口仲裁"处，因为仲裁要用 pmon_we ✓）
    //   ★ 关键：通道号用【专用寄存器】而**不是** `R[0x66]` ✗ ——
    //     `regs_flat` 的**每一个切片**都会综合出一棵 256:1 读 mux ✗，
    //     而本设计已贴着布线悬崖（实测：加遥测后未布线从 86 条涨到 187 条 ✗✗）
    //     ⇒ 走普通写通路存进 4 位寄存器，省掉一整棵 mux ✓
    //-------------------------------------------------------------------------
    reg [3:0] pad_sel_r;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) pad_sel_r <= 4'd0;
        else if (wr_en && wr_addr == 8'h66) pad_sel_r <= wr_data[3:0];

    assign r_pad_sel = pad_sel_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pmon_cnt <= 13'd0; pmon_st <= 3'd0; pmon_we <= 1'b0;
            pmon_addr <= 8'd0; pmon_data <= 8'd0;
        end
        else begin
            pmon_we <= 1'b0;
            if (pmon_st == 3'd0) begin
                // 空闲：等节流窗口到点再开始一轮
                if (pmon_cnt == 13'd4095) begin
                    pmon_cnt <= 13'd0;
                    pmon_st  <= 3'd1;
                end
                else pmon_cnt <= pmon_cnt + 13'd1;
            end
            else begin
                pmon_we <= 1'b1;                       // 每个状态写一个字节
                case (pmon_st)
                    3'd1: begin pmon_addr <= 8'h64; pmon_data <= pad_base_sel[7:0];   pmon_st <= 3'd2; end
                    3'd2: begin pmon_addr <= 8'h65; pmon_data <= {4'd0, pad_base_sel[11:8]}; pmon_st <= 3'd3; end
                    3'd3: begin pmon_addr <= 8'h67; pmon_data <= pad_raw_sel[7:0];    pmon_st <= 3'd4; end
                    3'd4: begin pmon_addr <= 8'h68; pmon_data <= {4'd0, pad_raw_sel[11:8]};  pmon_st <= 3'd5; end
                    3'd5: begin pmon_addr <= 8'h69; pmon_data <= pad_state[7:0];      pmon_st <= 3'd6; end
                    3'd6: begin pmon_addr <= 8'h6A; pmon_data <= pad_state[15:8];     pmon_st <= 3'd7; end
                    default: begin pmon_we <= 1'b0; pmon_st <= 3'd0; end
                endcase
            end
        end
    end

    //---- 刷新在响声部（D6）的触发与节流 ----
    reg         rf_pulse;
    reg  [6:0]  rf_lo_q;
    reg  [7:0]  rf_hi_q;
    reg  [12:0] rf_thr;
    reg         spec_dirty;
    reg  [7:0]  harm_q, pst8_q;
    reg         spec_we_q;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            rf_pulse <= 1'b0; rf_lo_q <= 7'd0; rf_hi_q <= 8'd0; rf_thr <= 13'd0;
            spec_dirty <= 1'b0; harm_q <= 8'd0; pst8_q <= 8'd0; spec_we_q <= 1'b0;
        end
        else begin
            spec_we_q <= spec_we;
            harm_q    <= r_harm_pads;
            pst8_q    <= pad_state[15:8];
            rf_pulse  <= 1'b0;

            // 谱或右手掩码变化 ⇒ 置脏（仅在自动刷新打开时）
            if (spec_autorf && (spec_we || (r_harm_pads != harm_q) || (pad_state[15:8] != pst8_q)))
                spec_dirty <= 1'b1;

            // 节流：每 4096 拍最多刷一次（≈6.6 kHz ≫ 手势带宽 ✓）
            if (rf_thr != 13'd4095) rf_thr <= rf_thr + 13'd1;
            else if (spec_dirty) begin
                rf_thr     <= 13'd0;
                spec_dirty <= 1'b0;
                rf_pulse   <= 1'b1;
                rf_lo_q    <= 7'd0;
                rf_hi_q    <= 8'd32;               // 全刷（note_map 只刷在响的组 ✓）
            end

            // 0x63 显式刷新：立即生效，不节流 ✓
            if (wr_en && wr_addr == 8'h63) begin
                rf_pulse <= 1'b1;
                if (wr_data == 8'hFF) begin
                    rf_lo_q <= 7'd0;
                    rf_hi_q <= 8'd32;
                end
                else begin
                    rf_lo_q <= {2'b00, wr_data[4:0]};
                    rf_hi_q <= {3'b000, wr_data[4:0]} + 8'd1;
                end
            end
        end
    end

    wire        ev_valid_i = u_ev_valid ? 1'b1      :
                             seq_en      ? sq_ev_valid :
                             pd_ev_valid ? 1'b1      : ev_valid;
    wire        ev_on_i    = u_ev_valid ? u_ev_on   :
                             seq_en      ? sq_ev_on    :
                             pd_ev_valid ? pd_ev_on    : ev_on;
    wire [6:0]  ev_note_i  = u_ev_valid ? u_ev_note :
                             seq_en      ? sq_ev_note  :
                             pd_ev_valid ? pd_ev_note  : ev_note;
    wire [3:0]  ev_vel_i   = u_ev_valid ? u_ev_vel  :
                             seq_en      ? sq_ev_vel[7:4] :
                             pd_ev_valid ? 4'd12       : ev_vel;   // pad 力度 v1 固定 12/15

    //-------------------------------------------------------------------------
    // ★ 事件打一拍再进 note_map（2026-10-02）
    //
    //   加定序器后 PnR 报 SETUP slack 只剩 +0.105 ns，关键路径是：
    //       u_reg/mem[80]（SEQ_CTRL）→ 事件源 mux → u_nm 的时隙分配逻辑
    //   也就是"一个寄存器直接串到 note_map 的组合分配网络里"。
    //   在中间加一级寄存器就把这条路切断：寄存器→mux→寄存器 变成短路径，
    //   而 寄存器→note_map 这条（加定序器之前就在的路径）本来就余量充足。
    //
    //   代价：音符事件晚 1 个时钟 = 37 ns，相对 5 ms 预算可忽略
    //        （E5 延迟从 2807 变 2808 拍，已重测）。
    //-------------------------------------------------------------------------
    reg        ev_valid_r, ev_on_r;
    reg [6:0]  ev_note_r;
    reg [3:0]  ev_vel_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ev_valid_r <= 1'b0; ev_on_r <= 1'b0; ev_note_r <= 7'd0; ev_vel_r <= 4'd0;
        end
        else begin
            ev_valid_r <= ev_valid_i;
            ev_on_r    <= ev_on_i;
            ev_note_r  <= ev_note_i;
            ev_vel_r   <= ev_vel_i;
        end
    end

    //-------------------------------------------------------------------------
    // 音频时钟链：27 MHz -> BCK -> LRCK，且【每样本拍数 = NSLOT】
    //
    //   ★ 2026-10-02 重要修正：原来是 ÷18×32 = 576 拍/样本，而 TDM 只有
    //     512 个时隙 —— 多出来的 64 拍里 sc 会【回卷重访 slot 4..67】，
    //     于是那 64 个时隙每样本推进两次，累加窗口与输出锁存也会在一个
    //     样本周期内触发两次（第二个是残窗，值是垃圾）。
    //     在"周期 = 时隙数"下这些问题根本不存在。
    //
    //   改法：DIV_BCK = 16 → 每样本 16×32 = 512 拍 = NSLOT ✓
    //        BCK = 27 MHz / 16 = 1.6875 MHz（整数分频，无抖动）
    //        fs  = 1.6875 MHz / 32 = 52734.375 Hz（MAX98357A 支持 8k~96k ✓）
    //-------------------------------------------------------------------------
    //   ⇒ 出货配置与所有功能验证用的配置【完全一致】，证据直接适用。
    //-------------------------------------------------------------------------
    // （wire 声明已提前到上面的定序器之前 —— 端口连线要求先声明）

    audio_clk_en #(.DIV_BCK(16), .BCK_PER_LRCK(32)) u_clk (
        .clk(clk), .rst_n(rst_n),
        .bck_en(bck_en), .bck(bck), .lrck(lrck), .sample_en(sample_en)
    );

    //-------------------------------------------------------------------------
    // 装载口（两种模式二选一）
    //-------------------------------------------------------------------------
    wire               nm_load_en;
    wire [8:0]         nm_load_slot;
    wire [PHASE_W-1:0] nm_load_inc;
    wire [AMP_W-1:0]   nm_load_amp;
    wire               nm_load_gate;
    wire [22:0]        nm_load_epar;

    wire               tm_load_en;
    wire [8:0]         tm_load_slot;
    wire [PHASE_W-1:0] tm_load_inc;
    wire [AMP_W-1:0]   tm_load_amp;
    wire               tm_load_gate;
    wire [22:0]        tm_load_epar;

    wire               load_en   = test_mode_eff ? tm_load_en   : nm_load_en;
    wire [8:0]         load_slot = test_mode_eff ? tm_load_slot : nm_load_slot;
    wire [PHASE_W-1:0] load_inc  = test_mode_eff ? tm_load_inc  : nm_load_inc;
    wire [AMP_W-1:0]   load_amp  = test_mode_eff ? tm_load_amp  : nm_load_amp;
    wire               load_gate = test_mode_eff ? tm_load_gate : nm_load_gate;
    wire [22:0]        load_epar = test_mode_eff ? tm_load_epar : nm_load_epar;

    // ---- 滑音初值（note_map → tdm_engine，随装载通路一起）----
    wire signed [17:0] nm_load_gq;

    // ★ 测试模式不做滑音（栅格是静态的，滑音会让谱峰位置漂移）
    wire signed [17:0] load_gq   = test_mode_eff ? 18'sd0 : nm_load_gq;

    //-------------------------------------------------------------------------
    // 演奏模式：音符映射
    //-------------------------------------------------------------------------
    wire [NG-1:0] nm_active;

    note_map #(
        .NG(NG), .P(P), .PHASE_W(PHASE_W), .AMP_W(AMP_W), .NB(7), .NPRE(4),
        // ★ 滑音初值照常算（真正"开不开"由 pitch_mod 的 glide_en 在应用处门控），
        //   这样 note_map 不必再吃一个运行时开关。
        .GLIDE_EN(1'b1)
    ) u_nm (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid_r), .ev_on(ev_on_r), .ev_note(ev_note_r),
        .ev_vel({ev_vel_r, 4'b0000}),      // 4 位 -> 8 位（16 级力度）
        .preset(preset_eff),               // ★ 引脚或寄存器（CTRL[3] 选择）
        // ★ 步③ 塑谱接口
        .spec_we(spec_we), .spec_addr(spec_addr), .spec_wdata(spec_wdata),
        .spec_replace(spec_replace),
        .pad_mask(pad_mask_eff),
        .refresh_valid(rf_pulse), .rf_lo(rf_lo_q), .rf_hi(rf_hi_q),
        .load_en(nm_load_en), .load_slot(nm_load_slot),
        .load_inc(nm_load_inc), .load_amp(nm_load_amp),
        .load_gate(nm_load_gate), .load_epar(nm_load_epar),
        .load_gq(nm_load_gq),
        .busy(nm_busy), .active(nm_active)
    );

    //-------------------------------------------------------------------------
    // 测试模式：一次性把 512 个时隙装成等间隔频率栅格
    //   inc = 71583 + slot*8800
    //   在 fs = 52734.375 Hz 下 → f = 225 Hz + slot*27.7 Hz（225 Hz ~ 14.4 kHz）
    //   写入 gate=1 即构成一次显式音符事件（门初值为 0 的语义），
    //   对齐到样本边界由引擎的"待生效装载区"负责。
    //-------------------------------------------------------------------------
    reg [9:0]  tm_cnt;
    reg        tm_done;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            tm_cnt  <= 10'd0;
            tm_done <= 1'b0;
        end
        else if (!test_mode_eff) begin
            tm_cnt  <= 10'd0;           // 离开测试模式：允许下次重新装一遍
            tm_done <= 1'b0;
        end
        else if (!tm_done) begin
            if (tm_cnt == NSLOT) tm_done <= 1'b1;
            else                 tm_cnt  <= tm_cnt + 10'd1;
        end
    end

    assign tm_load_en   = test_mode_eff & ~tm_done;
    assign tm_load_slot = tm_cnt[8:0];
    // ★ 位宽：tm_cnt 是 10 位，直接参与 * 会让表达式宽度不确定。
    //   显式取低 9 位并让常量带位宽，避免又一次"上下文宽度"事故。
    assign tm_load_inc  = 24'd71583 + {3'b000, tm_cnt[8:0]} * 24'd8800;
    // 测试模式每时隙幅度。
    //   ★ 2026-10-02（ZCode 的 F1 重制调查结论）：原来是 8'd60 —— 512 个等幅音
    //     叠加会顶到输出满量程 2^23，**饱和限幅本身产生互调**，频谱上出现
    //     2000+ 个"栅格外"假峰（实测 65.68% 能量落在栅格外 ✗）。
    //     那不是设计 bug，是病态激励。降到 8 之后叠加不再饱和，
    //     512 个谱峰干净可数（F1 取证的前提条件）。
    assign tm_load_amp  = 8'd8;
    assign tm_load_gate = 1'b1;
    // 测试模式给一个"几乎不衰减、保持"的包络，让谱峰稳定可测
    assign tm_load_epar = {16'd30000, 2'd3, 5'd20};

    //-------------------------------------------------------------------------
    // TDM 引擎
    //-------------------------------------------------------------------------
    wire signed [OUT_W-1:0] sample;

    tdm_engine #(
        .NSLOT(NSLOT), .PHASE_W(PHASE_W), .AMP_W(AMP_W),
        .ENV_W(ENV_W), .OUT_W(OUT_W), .GAIN_UP(4), .SHIFT(0),
        // ---- 表情调制 ----
        //   PART=16：组号 = slot/16（与 note_map 的固定分组一致）
        //   ★ 开关与深度不写在参数里，改由 pmod_cfg 运行时给（UART 可写）。
        //     默认值（开机自举写入）= 滑音开 + 颤音关：
        //     · 滑音开：组被复用时才真的滑，空闲组起音不滑
        //     · 颤音关：测试模式的 512 个谱峰若被颤音抹开就数不清（R3 现场自证）
        .PART(P)
    ) u_tdm (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .clr(1'b0), .pclr(1'b0), .gate_in(1'b1),
        .load_en(load_en), .load_slot(load_slot),
        .load_inc(load_inc), .load_amp(load_amp), .load_gate(load_gate),
        .load_epar(load_epar),
        .load_gq(load_gq),
        .pmod_cfg(pmod_cfg),
        .env_en(1'b1),
        .a_inc(16'd117), .d_inc(16'd1), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(16'd22938), .r_inc(16'd1), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(16'd100), .exp_mode(1'b1),
        .sample_out(sample), .sum_raw(), .slot_dbg()
    );

    //-------------------------------------------------------------------------
    // 效果器（拓展 E4）：并联湿声支路 + 零延迟旁路
    //   ★ 旁路时音频【完全绕开】本模块（组合 mux）：
    //       · 干声路径一拍都不多（纪律 D2）
    //       · 旁路输出与"没有效果器"逐位相同 → 既有回归证据继续有效
    //-------------------------------------------------------------------------
    wire signed [23:0] fx_out;

    fx_delay #(.DW(16), .AW(11), .CHO_BASE(1024)) u_fx (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .din(sample),
        .dry_en(fx_dry_en), .dly_en(fx_dly_en), .cho_en(fx_cho_en),
        .wet_sh(fx_wet_sh), .dly_len(r_dlylen), .fb_q8(r_fb),
        .cho_rate(r_chrate), .cho_depth(r_chdep),
        .rev_en(fx_rev_en), .rev_fb_q8(r_rev_fb), .rev_damp(r_rev_dmp),
        .dout(fx_out), .tap_dbg()
    );

    wire signed [23:0] audio = fx_active ? fx_out : sample;

    //-------------------------------------------------------------------------
    // I2S
    //-------------------------------------------------------------------------
    wire sd_i, ws_i;

    i2s_tx #(.SW(24), .DW(16)) u_i2s (
        .clk(clk), .rst_n(rst_n),
        .bck_en(bck_en), .lrck(lrck), .sample_en(sample_en),
        .sample_in(audio), .sd(sd_i), .ws(ws_i)
    );

    assign dac_din = sd_i;
    assign dac_ws  = ws_i;
    assign dac_bck = bck;
    assign pa_en   = 1'b1;

    //-------------------------------------------------------------------------
    // LED（拓展 E6 的"LED 指引"部分）
    //
    //   ★★ 极性修正（2026-10-02）：官方 blink_leds 的 cst 注释写得很清楚 ——
    //      "6 mono LEDs -- COMMON ANODE, so a LOW output lights them"
    //      而这里是【共阳极、低电平点亮】。原来写的是
    //          led = test_mode ? 6'b111111 : {1'b0, active[4:0]}
    //      即"用 1 点亮" —— 上板会【全反】：测试档全灭、在奏声部反而灭、
    //      空闲声部常亮。这里改成驱动取反。
    //
    //   三种显示：
    //     · 测试模式      → 6 个全亮（上一行代码里的常亮意图）
    //     · 定序器使能    → [5]=拍点闪, [4:0]=当前应弹音高编号（脱机曲目指引）
    //     · 否则          → 在奏声部数（低 5 位）
    //-------------------------------------------------------------------------
    wire [5:0] led_bits = test_mode_eff ? 6'b111111 :
                          (seq_en ? {sq_beat, sq_cur_note[4:0]}
                                  : {1'b0, nm_active[4:0]});

    assign led = ~led_bits;      // 共阳极：低电平点亮

endmodule
