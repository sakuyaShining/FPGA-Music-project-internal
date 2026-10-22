module core_display_probe(
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
,
    input wire display_start, pixel_valid,
    input wire [8:0] x0,y0,x1,y1,
    input wire [15:0] pixel,
    output wire pixel_ready, display_busy, frame_done, window_error, init_done,
    output wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc
);
resource_core_probe u_core(
    .clk(clk),.rst_n(rst_n),.uart_rx_pin(uart_rx_pin),.uart_tx_pin(uart_tx_pin),.led(led),
    .dac_din(dac_din),.dac_ws(dac_ws),.dac_bck(dac_bck),.pa_en(pa_en),.pad(pad),
    .finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),
    .finger_group(finger_group),.finger_position(finger_position),
    .voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_note(voice_note));
ili9341_window u_display(.clk(clk),.rst_n(rst_n),.lcd_reset_n(lcd_reset_n),
    .lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),.lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc),
    .init_done(init_done),.start(display_start),.x0(x0),.y0(y0),.x1(x1),.y1(y1),
    .pixel_valid(pixel_valid),.pixel(pixel),.pixel_ready(pixel_ready),.busy(display_busy),
    .frame_done(frame_done),.window_error(window_error));
endmodule
