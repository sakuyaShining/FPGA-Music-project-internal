// Independent fallback image: all amplifier/I2S outputs LOW, no music engine.
module board_mute_top(
    input wire clk,reset_button,uart_rx_pin,
    output wire uart_tx_pin,
    output wire [5:0] led,
    output wire dac_din,dac_ws,dac_bck,pa_en
);
    reg [24:0] heartbeat=0;
    always @(posedge clk or posedge reset_button)
        if(reset_button)heartbeat<=0;else heartbeat<=heartbeat+1'b1;
    assign led=~{heartbeat[24],uart_rx_pin,reset_button,3'b001};
    assign uart_tx_pin=1'b1;
    assign dac_din=0;assign dac_ws=0;assign dac_bck=0;assign pa_en=0;
endmodule
