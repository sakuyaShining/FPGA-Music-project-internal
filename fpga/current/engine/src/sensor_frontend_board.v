//=============================================================================
// sensor_frontend_board.v —— 载板电极前端顶层（6 路 SENSE + 595/165 扫描链）
//
// 【这个模块解决什么问题】
//   仓库里已经有 `rc_mux_scan`（扫描状态机）、`scan_shift595`（输出移位）、
//   `rc_delta_store` / `rc_strip_positions`（基线与重心）、`instrument_sensor_probe`
//   （集成层）。但它们从来没有被接进产品顶层 `tdm_top_owned` ——
//   那里只例化了 v1 的 `pad_scan`。
//
//   而且 `rc_mux_scan` 的 `bus_grant` 端口在整个仓库里没有任何驱动者：
//   所有 testbench 都把它常量绑成 1'b1。这在"只有一个请求者"时能跑，
//   一旦加上 165 输入链就会出问题（两个时钟源打同一根 SCK）。
//
//   本模块把这三块补齐成一个可综合、可上板的整体：
//     scan_bus_arbiter  —— 仲裁 SCK 归属
//     rc_mux_scan       —— 595 输出侧扫描（6 lane × 16 地址）
//     scan_shift165     —— 165 输入侧读取（按键 / 预置）
//
// 【通道账本】
//   6 lane × 16 地址 = 96 个物理通道
//   载板实际接 14 个地址（`L0_E00`..`L5_E13`）⇒ 6 × 14 = **84 个电极**
//   地址 14 / 15 在载板上悬空，扫到它们会读到固定电平，属于正常现象，
//   不要当成故障。判定方式：`row_fault` 在地址 14/15 上恒为某固定值。
//
// 【为什么不直接输出音符事件】
//   `pad_scan` 的语义是"16 个按键 → 音符事件"；载板是"25 个音位 × 3 电极
//   → 重心位置 0..256"，是连续位置语义，不是按键语义。
//   注意：25 是**音位（半音格）数**，不是滑条数。物理上只有 3 根条：
//   A 音位条（通道 0..11 = C3..B3）、B 音位条（通道 12..23 = C4..B4）、
//   八度档条（通道 25..29，5 档离散）。详见 PITCH-MAP-DEFINITION-20261024.md。
//   把音位硬塞进按键接口等于在 RTL 里替产品层做了映射决策（哪个音位对应
//   哪个音、位置怎么量化成音高），那是 PRODUCT-SPEC 的事，不该在驱动层拍板。
//
//   所以本模块只输出**规范化后的原始行数据**（地址 + 6 路计数 + 故障位
//   + 帧序号）和**按键位图**，映射交给上层。这样它可测、可复用、可换映射。
//=============================================================================

`timescale 1ns/1ps

module sensor_frontend_board #(
    parameter integer LANES            = 6,
    parameter integer CW               = 12,
    parameter integer DISCHARGE_CYCLES = 512,
    parameter integer TIMEOUT_CYCLES   = 2047,
    parameter integer SPI_HALF_PERIOD  = 8,
    // 165 输入位宽。载板是 **2 片 SN74LV165ADR 级联 = 16 位**
    // （02_Shift_and_memory.esch2 型号统计：SN74LV165ADR ×2，且只有一根
    //  BUS_RETURN，故必然级联）。默认 8 只适合单片裸板验证；
    // 接载板时必须传 16，否则高 8 位（第二片）读不到。
    //
    // ⚠ 未验证点：哪一片是主片（QH 直连 BUS_RETURN）在原理图网络名里
    //   看不出来。若主片是低 8 位，则 data[7:0] = 第一片、data[15:8] = 第二片；
    //   若反了，整个 16 位会高低互换。载板到货后用「只按一个已知键、
    //   看哪一位翻转」即可确定，不要在仿真里假定。
    parameter integer KEY_WIDTH        = 8,
    // 165 读取周期（clk 拍数）。27 MHz 下 27000 ≈ 1 ms。
    // 按键是人手速度，1 ms 已经远快于需要；再快只是白占总线。
    parameter integer KEY_PERIOD       = 27000
)(
    input  wire                 clk,
    input  wire                 rst_n,
    input  wire                 calibrate,

    //---------------- 载板物理接口 ----------------
    input  wire [LANES-1:0]     sense_n,       // SENSE_0..5，施密特反相输出
    output wire                 bus_sck,       // 595 与 165 共用
    output wire                 bus_mosi,      // 仅 595
    output wire                 scan_latch,    // 仅 595
    output wire                 input_load_n,  // 仅 165，低有效
    input  wire                 bus_return,    // 仅 165，串行回读

    //---------------- 电极扫描结果 ----------------
    output wire                 row_valid,
    input  wire                 row_ready,
    output wire [3:0]           row_address,   // 0..13 有效，14/15 悬空
    output wire [LANES*CW-1:0]  row_count,     // 每 lane 一个计数
    output wire [LANES-1:0]     row_fault,     // 该 lane 起始极性异常
    output wire [31:0]          row_sequence,  // 帧序号，扫完 16 地址 +1
    output wire                 frame_tick,    // 每扫完一整轮一个单拍

    //---------------- 按键 / 预置 ----------------
    output wire [KEY_WIDTH-1:0] keys,
    output wire                 keys_valid,    // 单拍

    //---------------- 状态 ----------------
    output wire                 scan_grant_error,
    output wire                 key_grant_error
);

    //=====================================================================
    // 总线仲裁
    //   request[0] = 165（优先，低频单次）
    //   request[1] = 595（高频，可等，rc_mux_scan 有 waiting 兜底）
    //=====================================================================
    wire req165, req595;
    wire grant165, grant595;

    scan_bus_arbiter #(.REQ(2)) u_arb (
        .clk     (clk),
        .rst_n   (rst_n),
        .request ({req595, req165}),    // bit0=165, bit1=595
        .grant   ({grant595, grant165})
    );

    //=====================================================================
    // 595 输出侧：扫描状态机（内部已含 scan_shift595）
    //=====================================================================
    wire        sck595, mosi595, latch595;

    rc_mux_scan #(
        .LANES            (LANES),
        .CW               (CW),
        .DISCHARGE_CYCLES (DISCHARGE_CYCLES),
        .TIMEOUT_CYCLES   (TIMEOUT_CYCLES),
        .SPI_HALF_PERIOD  (SPI_HALF_PERIOD)
    ) u_scan (
        .clk            (clk),
        .rst_n          (rst_n),
        .sense_n        (sense_n),
        .bus_request    (req595),
        .bus_grant      (grant595),
        .bus_sck        (sck595),
        .bus_mosi       (mosi595),
        .scan_latch     (latch595),
        .row_valid      (row_valid),
        .row_ready      (row_ready),
        .row_address    (row_address),
        .row_count      (row_count),
        .row_fault      (row_fault),
        .row_sequence   (row_sequence),
        .grant_error    (scan_grant_error)
    );

    //=====================================================================
    // 165 输入侧：周期触发读取
    //=====================================================================
    wire             sck165, load165;
    wire [KEY_WIDTH-1:0] key_data;
    wire             key_dv;
    wire             ready165;

    reg [15:0] key_timer;
    wire       key_tick = (key_timer == 16'd0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            key_timer <= KEY_PERIOD[15:0] - 16'd1;
        else if (key_tick)
            key_timer <= KEY_PERIOD[15:0] - 16'd1;
        else
            key_timer <= key_timer - 16'd1;
    end

    // 只在 165 空闲时给 start，避免丢一次请求（丢了下个周期再来）
    wire key_start = key_tick && ready165;

    scan_shift165 #(
        .HALF_PERIOD (SPI_HALF_PERIOD),
        .WIDTH       (KEY_WIDTH),
        .MSB_FIRST   (1)
    ) u_keys (
        .clk         (clk),
        .rst_n       (rst_n),
        .start       (key_start),
        .ready       (ready165),
        .bus_request (req165),
        .bus_grant   (grant165),
        .sck         (sck165),
        .load_n      (load165),
        .serial_in   (bus_return),
        .data        (key_data),
        .data_valid  (key_dv),
        .grant_error (key_grant_error)
    );

    //=====================================================================
    // 物理总线合并
    //   仲裁器保证同一时刻只有一个请求者持有 grant，因此 sck 可以用或门合并。
    //   若仲裁失效，这里会出现两个时钟源同时驱动 —— 上板表现为 595 输出的
    //   地址字错位、或按键位序整体翻转。`grant_error` 是它的直接指示。
    //=====================================================================
    assign bus_sck     = sck595 | sck165;
    assign bus_mosi    = mosi595;
    assign scan_latch  = latch595;
    assign input_load_n = load165;

    //=====================================================================
    // 输出
    //=====================================================================
    assign keys       = key_data;
    assign keys_valid = key_dv;

    // 帧结束：row_sequence 进位那一拍
    reg [31:0] seq_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) seq_q <= 32'd0;
        else        seq_q <= row_sequence;
    end
    assign frame_tick = (row_sequence != seq_q);

endmodule
