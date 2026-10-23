//=============================================================================
// tdm_ship_owned.v —— 出货顶层包装（面向 tdm_top_owned）
//
// 【为什么需要】
//   旧的 `tdm_ship.v` 例化的是 `tdm_top`，而当前产品模块叫 `tdm_top_owned`
//   （端口从 21 个扩到 40+ 个）。直接拿 `tdm_top_owned` 当顶层会把
//   ev_*/cfg_*/finger_*/own_*/timbre_* 全部暴露成顶层输入，
//   PnR 会把它们随机分配到板上引脚 ⇒ 幽灵事件（tdm_ship.v 头注释记过这个坑）。
//
//   所以这里把每一个 input 都显式接常量，output 悬空。
//   **一个都不能漏** —— 悬空的 input 读到 z，比接错更危险。
//
// 【端口】严格等于 src/constr/tdm_top.cst 的 11 组：
//   clk / btn_rst / uart_rx_pin / uart_tx_pin / led[5:0] /
//   dac_din / dac_ws / dac_bck / pa_en / pad[15:0]
//
//   ★ 引脚 87 在 2026-10-23 由板上实测确定为「高有效」：
//     空闲读 0（beacon 探针 0xA8/0xAA），官方 20K 例程亦注明
//     "switches are pulled down ... logic one when you press"。
//     旧 cst 全按低有效处理 ⇒ 内核被永久按在复位里 ⇒ 产品顶层从未启动。
//     现在改名为 btn_rst（高有效），并交给 rst_gen 生成内部 rst_n。
//     复位不再依赖按键：POR 保证确定性启动。
//
// 【与旧 tdm_ship 的差异】
//   · 旧版只接了 21 个端口（tdm_top 时代），新版接满 40+ 个
//   · `timbre_gain_q8` / `timbre_voice_mask` 接 0 是安全的：
//     RIGHT_TIMBRE 参数默认 0，`generate if (RIGHT_TIMBRE)` 不启用时
//     这两个输入不参与任何逻辑（tdm_engine_rh.v:486）。
//   · 音符一律走 pad / UART 0x60-0x61 / 定序器，ev_* 恒 0
//   · preset 恒 0（音色走寄存器 0x37 + CTRL[3]）
//   · test_mode 恒 0（测试模式由寄存器 CTRL[0] 进入）
//=============================================================================

`timescale 1ns/1ps

module tdm_ship_owned #(
    // 与 tdm_top_owned 的默认值保持一致；改这里必须同步改 tdm_top_owned
    parameter integer OWNER_W = 13,
    parameter integer FINGER_EXPR = 0,
    parameter integer RIGHT_TIMBRE = 0,
    parameter integer LEGACY_PAD = 1,
    parameter integer UART_BAUD = 115200,
    // BEACON=1 时用 uart_tx_pin 发心跳（诊断用），默认 0 不影响产品行为
    parameter integer BEACON = 0
)(
    input  wire        clk,
    input  wire        btn_rst,      // 引脚 87：高有效（板上外部下拉）

    input  wire        uart_rx_pin,
    output wire        uart_tx_pin,

    output wire [5:0]  led,
    output wire        dac_din,
    output wire        dac_ws,
    output wire        dac_bck,
    output wire        pa_en,

    inout  wire [15:0] pad
);

    wire top_tx;

    //-------------------------------------------------------------------------
    // 复位生成：POR + 按键消抖（详见 rst_gen.v 头注释）
    //   rst_n  = por_done & ~btn_stable
    //   上电 1.21 ms 后自动释放，与按键状态无关。
    //-------------------------------------------------------------------------
    wire rst_n;
    wire por_done;
    wire btn_state;

    rst_gen #(.POR_BITS(16), .DB_BITS(14)) u_rst (
        .clk(clk),
        .btn(btn_rst),
        .rst_n(rst_n),
        .por_done(por_done),
        .btn_state(btn_state)
    );

    generate
        if (BEACON) begin: diag_beacon
            // 心跳优先：证明"板子在跑这份码流"
            // 探针字节 = {4'b1010, 慢位, por_done, btn_state, rst_n}
            //   慢位 = bc_div[19]，27 MHz 下约 25.7 Hz 翻转 ⇒ 证明时钟在跑
            //   0xA1 / 0xA5  正常（por 完成、按键未按、复位已释放）
            //   0xA0 / 0xA4  POR 没走完（时钟没跑或计数器被卡）
            //   0xA2 / 0xA6  按键被判为按住（复位保持中）
            //   其它值       位序或波特率不对
            reg [19:0] bc_div;
            initial bc_div = 20'd0;
            always @(posedge clk) bc_div <= bc_div + 1'b1;
            wire [7:0] beacon_byte = {4'b1010, bc_div[19], por_done, btn_state, rst_n};
            uart_beacon #(.CLK_HZ(27000000), .BAUD(UART_BAUD), .GAP(200))
                u_bc (.clk(clk), .byte_i(beacon_byte), .tx(uart_tx_pin));
        end
        else begin: normal_tx
            assign uart_tx_pin = top_tx;
        end
    endgenerate

    tdm_top_owned #(
        .OWNER_W(OWNER_W),
        .FINGER_EXPR(FINGER_EXPR),
        .RIGHT_TIMBRE(RIGHT_TIMBRE),
        .LEGACY_PAD(LEGACY_PAD),
        .UART_BAUD(UART_BAUD)
    ) u_top (
        .clk(clk),
        .rst_n(rst_n),

        //---- 调试/测试口：全部接常量，不进网表 ----
        .ev_valid(1'b0),
        .ev_on(1'b0),
        .ev_note(7'd0),
        .ev_vel(4'd0),
        .preset(2'd0),
        .test_mode(1'b0),

        //---- 实例化演奏接口（OWNED_EVENTS=0 时不用）----
        .own_valid(1'b0),
        .own_on(1'b0),
        .own_note(7'd0),
        .own_vel(4'd0),
        .own_instance({OWNER_W{1'b0}}),
        .own_preset(2'd0),
        .own_ready(),

        //---- 板级状态回写（BOARD_DIAG=0 时不用）----
        .board_status(8'd0),
        .board_case(8'd0),
        .board_wr_en(),
        .board_wr_addr(),
        .board_wr_data(),

        //---- 运行时音色配置口（走 UART 时不用）----
        .cfg_valid(1'b0),
        .cfg_commit(1'b0),
        .cfg_slot(2'd0),
        .cfg_part(4'd0),
        .cfg_word(88'd0),
        .cfg_ready(),
        .cfg_applied(),
        .cfg_error(),

        //---- 结果回执 ----
        .result_valid(),
        .result_owned(),
        .result_on(),
        .result_success(),
        .result_instance(),
        .result_group(),

        //---- 板级 ----
        .uart_rx_pin(uart_rx_pin),
        .uart_tx_pin(top_tx),
        .led(led),
        .dac_din(dac_din),
        .dac_ws(dac_ws),
        .dac_bck(dac_bck),
        .pa_en(pa_en),
        .pad(pad),

        //---- 逐指表情（FINGER_EXPR=0 时不用）----
        .finger_valid(1'b0),
        .finger_cmd(2'd0),
        .finger_id(5'd0),
        .finger_group(5'd0),
        .finger_position(12'sd0),
        .voice_valid(),
        .voice_on(),
        .voice_group(),
        .voice_note(),

        //---- 右手音色注入（RIGHT_TIMBRE=0 时不参与逻辑）----
        .timbre_gain_q8(160'd0),
        .timbre_voice_mask(32'd0),

        //---- 实时监听（LIVE_MONITOR=0 时不用）----
        .monitor_valid(),
        .monitor_pcm()
    );

endmodule
