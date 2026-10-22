// Desktop analysis configuration. Music remains full32; UART is 460800 8N1.
module tdm_live_test (
    input wire clk, rst_n, uart_rx_pin,
    output wire uart_tx_pin,
    output wire [5:0] led,
    output wire dac_din, dac_ws, dac_bck, pa_en,
    inout wire [15:0] pad
);
    tdm_board_test #(.LIVE_MONITOR(1), .UART_BAUD(460800), .LIVE_DECIMATE(4)) u_board (
        .clk(clk), .rst_n(rst_n), .uart_rx_pin(uart_rx_pin), .uart_tx_pin(uart_tx_pin),
        .led(led), .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck), .pa_en(pa_en), .pad(pad)
    );
endmodule
