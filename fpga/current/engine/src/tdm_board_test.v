// Integration-derived controlled UART board test, full 32-group expression.
// Physical RC input ignored; internal samples are not external DAC measurements.
module tdm_board_test #(parameter LIVE_MONITOR=0, parameter UART_BAUD=115200, parameter LIVE_DECIMATE=1) (
    input wire clk, rst_n,
    input wire uart_rx_pin,
    output wire uart_tx_pin,
    output wire [5:0] led,
    output wire dac_din, dac_ws, dac_bck, pa_en,
    inout wire [15:0] pad
);
    // Board S1 is active high; asynchronously assert, synchronously release.
    reg [1:0] reset_release;
    initial reset_release=0;
    always @(posedge clk or posedge rst_n) begin
        if (rst_n) reset_release<=0;
        else reset_release<={reset_release[0],1'b1};
    end
    tdm_top #(.BOARD_DIAG(1), .FINGER_EXPR(1), .LIVE_MONITOR(LIVE_MONITOR), .LIVE_DECIMATE(LIVE_DECIMATE), .UART_BAUD(UART_BAUD)) u_top (
        .clk(clk), .rst_n(reset_release[1]),
        .ev_valid(1'b0), .ev_on(1'b0), .ev_note(7'd0), .ev_vel(4'd0),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx_pin), .uart_tx_pin(uart_tx_pin),
        .led(led), .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck), .pa_en(pa_en), .pad(pad),
        .finger_valid(1'b0), .finger_cmd(2'd0), .finger_id(5'd0),
        .finger_group(5'd0), .finger_position(12'sd0),
        .voice_valid(), .voice_on(), .voice_group(), .voice_note()
    );
endmodule
