// Internal logical interfaces, not a physical GPIO allocation or shipping top.
module left_layer_music_probe #(parameter integer NF=26,BAD_FRAMES=8,FRAME_TIMEOUT=2700000,LINK_TIMEOUT=8192)(

    input wire [3:0] layer_selection,
    input wire cfg_valid,cfg_commit,
    input wire [1:0] cfg_slot,
    input wire [3:0] cfg_part,
    input wire [47:0] cfg_word,
    output wire cfg_ready,cfg_applied,cfg_error,layer_protocol_error,layer_selection_error,
    input wire left_valid,
    output wire left_ready,
    input wire [NF-1:0] left_contact,left_invalid,
    input wire [NF*9-1:0] left_position,
    input wire [31:0] left_sequence,
    input wire left_calibration,
    input wire [NF*7-1:0] left_note_map,
    input wire [3:0] left_velocity,
    output wire frame_error,link_error,sensor_error,watchdog_error,
    output wire [NF-1:0] bound_contacts,blocked_contacts,
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
    output wire signed [23:0] pcm
);
    wire own_valid,own_ready,own_on,result_valid,result_owned,result_on,result_success;
    wire [6:0] own_note;
    wire [3:0] own_vel;
    wire [12:0] own_instance,result_instance;
    wire [4:0] result_group;
    wire child_valid,child_ready,child_on,child_result,child_result_owned,child_result_on,child_success;
    wire [6:0] child_note;wire [3:0] child_vel;wire [1:0] child_preset;
    wire [14:0] child_instance,child_result_instance;wire [4:0] child_group;
    wire bf_valid;wire [1:0] bf_cmd;wire [4:0] bf_id,bf_group;wire signed [11:0] bf_position;
    layer_dispatch #(.NF(NF)) layers(.clk(clk),.rst_n(rst_n),.selection(layer_selection),
        .parent_valid(own_valid),.parent_ready(own_ready),.parent_on(own_on),.parent_note(own_note),.parent_vel(own_vel),.parent_instance(own_instance),
        .parent_result(result_valid),.parent_success(result_success),.parent_result_on(result_on),.parent_result_instance(result_instance),.parent_group(result_group),
        .child_valid(child_valid),.child_ready(child_ready),.child_on(child_on),.child_note(child_note),.child_vel(child_vel),.child_instance(child_instance),.child_preset(child_preset),
        .result_valid(child_result),.result_owned(child_result_owned),.result_on(child_result_on),.result_success(child_success),.result_instance(child_result_instance),.result_group(child_group),
        .voice_valid(voice_valid),.voice_group(voice_group),.in_finger_valid(bf_valid),.in_finger_cmd(bf_cmd),.in_finger_id(bf_id),.in_finger_position(bf_position),
        .finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),.finger_group(finger_group),.finger_position(finger_position),.protocol_error(layer_protocol_error),.selection_error(layer_selection_error));
    assign result_owned=1'b1;
    left_contact_bridge #(.NF(NF),.BAD_FRAMES(BAD_FRAMES),.FRAME_TIMEOUT(FRAME_TIMEOUT),.LINK_TIMEOUT(LINK_TIMEOUT)) bridge(
        .clk(clk),.rst_n(rst_n),.frame_valid(left_valid),.frame_ready(left_ready),.contact(left_contact),.invalid(left_invalid),.position(left_position),.frame_sequence(left_sequence),.frame_calibration(left_calibration),.note_map(left_note_map),.velocity(left_velocity),
        .own_valid(own_valid),.own_ready(own_ready),.own_on(own_on),.own_note(own_note),.own_vel(own_vel),.own_instance(own_instance),
        .result_valid(result_valid),.result_owned(result_owned),.result_on(result_on),.result_success(result_success),.result_instance(result_instance),.result_group(result_group),
        .voice_valid(1'b0),.voice_on(1'b0),.voice_group(5'd0),.finger_valid(bf_valid),.finger_cmd(bf_cmd),.finger_id(bf_id),.finger_group(bf_group),.finger_position(bf_position),
        .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound_contacts),.blocked_contacts(blocked_contacts));
    rh_performance_control control(.clk(clk),.rst_n(rst_n),.sample_ce(pcm_valid),
        .touch_valid(touch_valid),.touch_ready(touch_ready),.touch_active(touch_active),.touch_x(touch_x),.touch_y(touch_y),.touch_id(touch_id),
        .radius(radius),.part_to_control(part_to_control),.slew_step(slew_step),.restore_valid(restore_valid),
        .fader_y(fader_y),.current_gain(gains),.frame_done(touch_done),.gain_done(gain_done),.error(control_error));
    tdm_top_owned #(.FINGER_EXPR(1),.BOARD_DIAG(0),.LIVE_MONITOR(0),.RIGHT_TIMBRE(1),.LEGACY_PAD(0),.OWNED_EVENTS(1),.OWNER_W(15),.MULTI_BIND(1)) core(
        .clk(clk),.rst_n(rst_n),.uart_rx_pin(uart_rx_pin),.uart_tx_pin(uart_tx_pin),.preset(preset),.test_mode(1'b0),
        .cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),.own_preset(child_preset),.own_valid(child_valid),.own_ready(child_ready),.own_on(child_on),.own_note(child_note),.own_vel(child_vel),.own_instance(child_instance),
        .result_valid(child_result),.result_owned(child_result_owned),.result_on(child_result_on),.result_success(child_success),.result_instance(child_result_instance),.result_group(child_group),
        .ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.pad(pad),.led(led),
        .finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),.finger_group(finger_group),.finger_position(finger_position),
        .voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_note(voice_note),
        .timbre_gain_q8(gains),.timbre_voice_mask(voice_mask),.monitor_valid(pcm_valid),.monitor_pcm(pcm),
        .dac_din(dac_din),.dac_ws(dac_ws),.dac_bck(dac_bck),.pa_en(pa_en));
endmodule
