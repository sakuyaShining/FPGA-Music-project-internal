from pathlib import Path
R=Path(__file__).resolve().parent
S=R.parent/'left_hand_events_20261016'
ports='''
    input wire [3:0] layer_selection,
    input wire cfg_valid,cfg_commit,
    input wire [1:0] cfg_slot,
    input wire [3:0] cfg_part,
    input wire [47:0] cfg_word,
    output wire cfg_ready,cfg_applied,cfg_error,layer_protocol_error,layer_selection_error,
'''
connections='''.layer_selection(layer_selection),.cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),.layer_protocol_error(layer_protocol_error),.layer_selection_error(layer_selection_error),'''
s=(S/'rtl/left_music_probe.v').read_text(encoding='utf-8').replace('module left_music_probe #(','module left_layer_music_probe #(')
s=s.replace('    input wire left_valid,',ports+'    input wire left_valid,',1)
insert='''    wire child_valid,child_ready,child_on,child_result,child_result_owned,child_result_on,child_success;
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
'''
s=s.replace('    left_contact_bridge #(',insert+'    left_contact_bridge #(',1)
# Bridge group is a virtual contact handle. Exact child ownership is in layers.
before,after=s.split('    rh_performance_control control(',1)
before=before.replace('.voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),.finger_group(finger_group),.finger_position(finger_position),',
    ".voice_valid(1'b0),.voice_on(1'b0),.voice_group(5'd0),.finger_valid(bf_valid),.finger_cmd(bf_cmd),.finger_id(bf_id),.finger_group(bf_group),.finger_position(bf_position),",1)
after=after.replace('.OWNED_EVENTS(1)', '.OWNED_EVENTS(1),.OWNER_W(15),.MULTI_BIND(1)')
for a,b in [('own_valid','child_valid'),('own_ready','child_ready'),('own_on','child_on'),('own_note','child_note'),('own_vel','child_vel'),('own_instance','child_instance'),('result_valid','child_result'),('result_owned','child_result_owned'),('result_on','child_result_on'),('result_success','child_success'),('result_instance','child_result_instance'),('result_group','child_group')]:
    after=after.replace('.'+a+'('+a+')','.'+a+'('+b+')')
after=after.replace('.own_valid(child_valid)', '.cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),.own_preset(child_preset),.own_valid(child_valid)')
(R/'rtl/left_layer_music_probe.v').write_text(before+'    rh_performance_control control('+after,encoding='utf-8')
s=(S/'rtl/instrument_owned_probe.v').read_text(encoding='utf-8').replace('module instrument_owned_probe(','module instrument_layer_probe(').replace('    input wire [5:0] sense_n,',ports+'    input wire [5:0] sense_n,').replace('left_music_probe music(','left_layer_music_probe music('+connections).replace(".layer_mask(4'b0001)",'.layer_mask(layer_selection)')
(R/'rtl/instrument_layer_probe.v').write_text(s,encoding='utf-8')
s=(S/'candidate/compat_music_probe.v').read_text(encoding='utf-8').replace('.clk(clk),.rst_n(rst_n),.uart_rx_pin(uart_rx_pin),.uart_tx_pin(uart_tx_pin),.preset(preset)',".cfg_valid(1'b0),.cfg_commit(1'b0),.cfg_slot(2'd0),.cfg_part(4'd0),.cfg_word(48'd0),.own_preset(2'd0),.clk(clk),.rst_n(rst_n),.uart_rx_pin(uart_rx_pin),.uart_tx_pin(uart_tx_pin),.preset(preset)")
(R/'candidate/compat_music_probe.v').write_text(s,encoding='utf-8')
(R/'tb_compat_music.v').write_bytes((S/'tb_compat_music.v').read_bytes())
print('Prepared layer music and combined resource wrappers')
