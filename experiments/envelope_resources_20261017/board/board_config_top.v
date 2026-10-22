// Diagnostic wrapper for the existing Nano20K + speaker only.
// Configuration ABI 75/1; no physical touch/display claims or automatic notes.
module board_config_top #(
 parameter UART_BAUD=115200,WARM_CYCLES=27000000,DIAG_CAPTURE_SAMPLES=2048
)(
 input wire clk,reset_button,uart_rx_pin,
 output wire uart_tx_pin,
 output wire [5:0] led,
 output wire dac_din,dac_ws,dac_bck,pa_en
);
 // S2/pin87: asynchronous active-high assertion, synchronized release.
 reg [1:0] reset_release=0;
 always @(posedge clk or posedge reset_button)
  if(reset_button)reset_release<=0;else reset_release<={reset_release[0],1'b1};
 wire rst_n=reset_release[1];
 localparam WW=$clog2(WARM_CYCLES+1);
 reg [WW-1:0] warm_count=0;
 wire warm=warm_count>=WARM_CYCLES;
 always @(posedge clk or negedge rst_n)
  if(!rst_n)warm_count<=0;else if(!warm)warm_count<=warm_count+1'b1;
 wire raw_din,raw_pa;wire [5:0] raw_led;
 wire pcm_valid;wire signed [23:0] pcm;
 assign dac_din=warm?raw_din:1'b0;
 assign pa_en=warm&&raw_pa;
 assign led={raw_led[5:1],~warm};
 tri [15:0] internal_pad;
 tdm_top_owned #(.CONFIG_DUAL_SOURCE(0),.CONFIG_SERIAL(1),.INSTRUMENT_ENV(1),
  .BOARD_DIAG(1),.BOARD_BOOT_SCRUB(1),.DIAG_FINGER(0),.DIAG_CAPTURE_SAMPLES(DIAG_CAPTURE_SAMPLES),
  .UART_BAUD(UART_BAUD),.LEGACY_PAD(0),.LIVE_MONITOR(0),.FINGER_EXPR(0),.RIGHT_TIMBRE(0),.OWNED_EVENTS(0)) core(
  .clk(clk),.rst_n(rst_n),.uart_rx_pin(uart_rx_pin),.uart_tx_pin(uart_tx_pin),.test_mode(1'b0),.preset(2'd0),.pad(internal_pad),
  // C0 remains diagnostic profile72; C2=76 distinguishes this wrapper.
  .board_status(warm?8'h19:8'h10),.board_case(8'h76),
  .cfg_valid(1'b0),.cfg_commit(1'b0),.cfg_slot(2'd0),.cfg_part(4'd0),.cfg_word(88'd0),
  .own_valid(1'b0),.own_on(1'b0),.own_note(7'd0),.own_vel(4'd0),.own_instance(13'd0),.own_preset(2'd0),
  .ev_valid(1'b0),.ev_on(1'b0),.ev_note(7'd0),.ev_vel(4'd0),
  .finger_valid(1'b0),.finger_cmd(2'd0),.finger_id(5'd0),.finger_group(5'd0),.finger_position(12'sd0),
  .timbre_gain_q8(160'd0),.timbre_voice_mask(32'd0),
  .led(raw_led),.dac_din(raw_din),.dac_ws(dac_ws),.dac_bck(dac_bck),.pa_en(raw_pa),.monitor_valid(pcm_valid),.monitor_pcm(pcm));
endmodule
