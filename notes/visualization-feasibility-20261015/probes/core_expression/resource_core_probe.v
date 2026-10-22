module resource_core_probe(
    input wire clk, rst_n, uart_rx_pin,
    output wire uart_tx_pin,
    output wire [5:0] led,
    output wire dac_din, dac_ws, dac_bck, pa_en,
    inout wire [15:0] pad,
    input wire finger_valid,
    input wire [1:0] finger_cmd,
    input wire [4:0] finger_id, finger_group,
    input wire signed [11:0] finger_position,
    output wire voice_valid, voice_on,
    output wire [4:0] voice_group,
    output wire [6:0] voice_note
);
    tdm_top #(.BOARD_DIAG(0), .FINGER_EXPR(1), .LIVE_MONITOR(0), .UART_BAUD(460800)) u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(1'b0), .ev_on(1'b0), .ev_note(7'd0), .ev_vel(4'd0),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx_pin), .uart_tx_pin(uart_tx_pin), .led(led),
        .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck), .pa_en(pa_en), .pad(pad),
        .finger_valid(finger_valid), .finger_cmd(finger_cmd),
        .finger_id(finger_id), .finger_group(finger_group), .finger_position(finger_position),
        .voice_valid(voice_valid), .voice_on(voice_on), .voice_group(voice_group), .voice_note(voice_note)
    );
endmodule
