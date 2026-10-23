`timescale 1ns/1ps
//=============================================================================
// tdm_ship_beacon —— 诊断顶层：与出货顶层完全相同的连线，只把 uart_tx 换成心跳
//
// 判据用法：
//   1) 烧这个码流，若 COM6 能收到连续的 0x5A ⇒ 码流/引脚/时钟/复位全部正常，
//      问题一定在 tdm_top_owned 内部（寄存器读回路径或引擎）。
//   2) 若连 0x5A 都收不到 ⇒ 问题在更底层（引脚约束、时钟源、下载未生效），
//      此时不要去改 RTL。
//=============================================================================
module tdm_ship_beacon (
    input  wire        clk,
    input  wire        btn_rst,      // 引脚 87，高有效（板上外部下拉）
    input  wire        uart_rx_pin,
    output wire        uart_tx_pin,
    output wire [5:0]  led,
    output wire        dac_din,
    output wire        dac_ws,
    output wire        dac_bck,
    output wire        pa_en,
    inout  wire [15:0] pad
);

    tdm_ship_owned #(
        .OWNER_W(13),
        .FINGER_EXPR(0),
        .RIGHT_TIMBRE(0),
        .LEGACY_PAD(1),
        .UART_BAUD(115200),
        .BEACON(1)
    ) u_ship (
        .clk(clk), .btn_rst(btn_rst),
        .uart_rx_pin(uart_rx_pin), .uart_tx_pin(uart_tx_pin),
        .led(led), .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck),
        .pa_en(pa_en), .pad(pad)
    );

endmodule
