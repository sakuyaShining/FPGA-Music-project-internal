// Internal logical interfaces, not a physical GPIO allocation or shipping top.
module storage_probe #(parameter CONFIG_DUAL_SOURCE=0,CONFIG_SERIAL=1,INSTRUMENT_ENV=1)(

    input wire rec_clear,rec_enable,rec_ready,play_clear,play_enable,
    input wire feed_valid,input wire [15:0] feed_data,
    output wire feed_ready,rec_valid,rec_overflow,play_valid,play_underflow,play_miss,
    output wire [15:0] rec_data,play_data,
    output wire [10:0] rec_level,play_level,

    input wire [3:0] layer_selection,
    input wire cfg_valid,cfg_commit,
    input wire [1:0] cfg_slot,
    input wire [3:0] cfg_part,
    input wire [87:0] cfg_word,
    output wire cfg_ready,cfg_applied,cfg_error,layer_protocol_error,layer_selection_error,
    input wire [5:0] sense_n,
    input wire calibrate,scan_bus_grant,
    output wire sensor_report_ready,
    input wire [181:0] left_note_map,
    input wire [3:0] left_velocity,
    output wire frame_error,link_error,sensor_error,watchdog_error,
    output wire [25:0] bound_contacts,blocked_contacts,
    input wire [13:0] threshold_on,threshold_off,
    output wire scan_bus_request,scan_bus_sck,scan_bus_mosi,scan_latch,
    output wire sensor_report_valid,sensor_report_calibration,sensor_protocol_error,sensor_grant_error,
    output wire [25:0] sensor_contact,sensor_invalid,
    output wire [233:0] sensor_position,
    output wire [31:0] sensor_sequence,
    input wire clk,rst_n,uart_rx_pin,
    output wire uart_tx_pin,
    input wire ev_valid,ev_on,
    input wire [6:0] ev_note,
    input wire [3:0] ev_vel,
    input wire [1:0] preset,
    output wire finger_valid,
    output wire [1:0] finger_cmd,
    output wire [4:0] finger_id,finger_group,
    output wire signed [11:0] finger_position,
    inout wire [15:0] pad,
    input wire touch_valid,
    output wire touch_ready,
    input wire [4:0] touch_active,
    input wire [49:0] touch_x,touch_y,
    input wire [19:0] touch_id,
    input wire [9:0] radius,slew_step,
    input wire [47:0] part_to_control,
    input wire restore_valid,
    input wire [31:0] voice_mask,
    output wire [79:0] fader_y,
    output wire [159:0] gains,
    output wire touch_done,gain_done,control_error,
    output wire [5:0] led,
    output wire dac_din,dac_ws,dac_bck,pa_en,
    output wire voice_valid,voice_on,
    output wire [4:0] voice_group,
    output wire [6:0] voice_note,
    output wire pcm_valid,
    output wire signed [23:0] pcm,
    output wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc,
    output wire [31:0] rendered_frames,late_frames,analysis_gaps,spectrum_sequence
);
left_layer_music_probe #(.CONFIG_DUAL_SOURCE(CONFIG_DUAL_SOURCE),.CONFIG_SERIAL(CONFIG_SERIAL),.INSTRUMENT_ENV(INSTRUMENT_ENV)) music(.layer_selection(layer_selection),.cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),.layer_protocol_error(layer_protocol_error),.layer_selection_error(layer_selection_error),
    .left_valid(sensor_report_valid),.left_ready(sensor_report_ready),.left_contact(sensor_contact),.left_invalid(sensor_invalid),.left_position(sensor_position),.left_sequence(sensor_sequence),.left_calibration(sensor_report_calibration),.left_note_map(left_note_map),.left_velocity(left_velocity),
    .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound_contacts),.blocked_contacts(blocked_contacts),.clk(clk),.rst_n(rst_n),.uart_rx_pin(uart_rx_pin),.uart_tx_pin(uart_tx_pin),.ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.preset(preset),.finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),.finger_group(finger_group),.finger_position(finger_position),.pad(pad),.touch_valid(touch_valid),.touch_ready(touch_ready),.touch_active(touch_active),.touch_x(touch_x),.touch_y(touch_y),.touch_id(touch_id),.radius(radius),.slew_step(slew_step),.part_to_control(part_to_control),.restore_valid(restore_valid),.voice_mask(voice_mask),.fader_y(fader_y),.gains(gains),.touch_done(touch_done),.gain_done(gain_done),.control_error(control_error),.led(led),.dac_din(dac_din),.dac_ws(dac_ws),.dac_bck(dac_bck),.pa_en(pa_en),.voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_note(voice_note),.pcm_valid(pcm_valid),.pcm(pcm));
music_visualizer visualizer(.clk(clk),.rst_n(rst_n),.pcm_valid(pcm_valid),.pcm(pcm[23:8]),
    .layer_mask(layer_selection),.base_note(7'd48),.note_valid(voice_valid),.note_on(voice_on),.note_id(voice_group),.note_number(voice_note),
    .pitch_valid(1'b0),.pitch_id(5'd0),.pitch_q8(16'sd0),.lcd_reset_n(lcd_reset_n),.lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),.lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc),
    .rendered_frames(rendered_frames),.late_frames(late_frames),.analysis_gap_samples(analysis_gaps),.spectrum_sequence(spectrum_sequence));
instrument_sensor_probe sensor(.clk(clk),.rst_n(rst_n),.calibrate(calibrate),.sense_n(sense_n),
    .bus_request(scan_bus_request),.bus_grant(scan_bus_grant),.bus_sck(scan_bus_sck),.bus_mosi(scan_bus_mosi),.scan_latch(scan_latch),
    .threshold_on(threshold_on),.threshold_off(threshold_off),.report_valid(sensor_report_valid),.report_ready(sensor_report_ready),
    .contact(sensor_contact),.invalid(sensor_invalid),.position(sensor_position),.report_sequence(sensor_sequence),.report_calibration(sensor_report_calibration),.protocol_error(sensor_protocol_error),.grant_error(sensor_grant_error));

assign feed_ready=0;assign rec_valid=0;assign rec_overflow=0;assign play_valid=0;
assign play_underflow=0;assign play_miss=0;assign rec_data=0;assign play_data=0;
assign rec_level=0;assign play_level=0;

endmodule
