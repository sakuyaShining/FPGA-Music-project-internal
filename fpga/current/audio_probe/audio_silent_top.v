//=============================================================================
// audio_silent_top.v —— 静音版：能证明码流在跑，但不出声
//
// 【为什么需要它】
//   build_02 那个自测码流上电就发 512 个音，太吵，不适合长期留在板子里。
//   但直接烧产品码流（tdm_ship_owned）也不行：它默认 LEGACY_PAD=1，
//   pad[15:0] 悬空时 pad_scan 可能被浮空噪声误判成"按下"，随机出音。
//
//   本顶层把两件事同时关掉，才是真静音：
//     TEST_MODE  = 0  -> 不走内置测试加载器（不主动发任何音）
//     LEGACY_PAD = 0  -> 不例化 pad_scan，pad 被赋 16'bz，所有 pad 事件恒 0
//   剩下 ev_* 在 audio_selftest_top 里本来就是常量 0。
//   ⇒ 没有任何音符事件 => TDM 引擎跑但输出静音，led[5] 心跳照旧。
//
// 【用途】烧进外部 flash，上电自动加载，板子保持"活着且安静"。
//=============================================================================
module audio_silent_top (
    input  wire        clk,
    input  wire        btn_rst,
    input  wire        uart_rx_pin,
    output wire        uart_tx_pin,
    output wire [5:0]  led,
    output wire        dac_din,
    output wire        dac_ws,
    output wire        dac_bck,
    output wire        pa_en,
    inout  wire [15:0] pad
);

    audio_selftest_top #(
        .TEST_MODE  (0),
        .LEGACY_PAD (0),
        .BEACON     (0)
    ) u_core (
        .clk         (clk),
        .btn_rst     (btn_rst),
        .uart_rx_pin (uart_rx_pin),
        .uart_tx_pin (uart_tx_pin),
        .led         (led),
        .dac_din     (dac_din),
        .dac_ws      (dac_ws),
        .dac_bck     (dac_bck),
        .pa_en       (pa_en),
        .pad         (pad)
    );

endmodule
