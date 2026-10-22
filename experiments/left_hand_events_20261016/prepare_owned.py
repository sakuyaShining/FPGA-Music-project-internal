"""Derive opt-in owned-event allocator/top; original modules remain beside them."""
from pathlib import Path
import re
R=Path(__file__).resolve().parent;D=R/'candidate';D.mkdir(exist_ok=True)
def once(s,a,b):
    assert s.count(a)==1,a[:100]
    return s.replace(a,b)
s=(R/'engine/note_map.v').read_text(encoding='utf-8')
s=once(s,'module note_map #(','module note_map_owned #(')
s=once(s,'    parameter SPEC_STAGED = 0','    parameter SPEC_STAGED = 0,\n    parameter OWNED_EVENTS = 0,\n    parameter OWNER_W = 13')
s=once(s,'    //---- 音色选择 ----','''    // Dedicated instance identity; legacy events remain in their own domain.
    input wire ev_owned,
    input wire [OWNER_W-1:0] ev_instance,
    output wire result_valid,result_owned,result_on,result_success,
    output wire [OWNER_W-1:0] result_instance,
    output wire [$clog2(NG)-1:0] result_group,

    //---- 音色选择 ----''')
s=once(s,'    reg [NG-1:0]  gact;', '''    reg [NG-1:0] group_owned;
    reg [OWNER_W-1:0] group_instance[0:NG-1];
    reg owned_hold;
    reg [OWNER_W-1:0] instance_hold;
    reg [NG-1:0]  gact;''')
s=once(s,'            group_start_tag[gi] = 0;', '            group_start_tag[gi] = 0;\n            group_instance[gi] = 0;')
s=once(s,"        gact_q = {NG{1'b0}};", "        gact_q = {NG{1'b0}};\n        group_owned=0;")
s=once(s,'    assign voice_note = n_hold;', '''    assign voice_note = n_hold;
    assign result_valid=(st==ST_GLIDE);
    assign result_owned=owned_hold;
    assign result_instance=instance_hold;
    assign result_on=on_cur;
    assign result_success=on_cur||match_r;
    assign result_group=gsel_r[$clog2(NG)-1:0];''')
s=once(s,'    assign voice_note = n_hold;', '    assign voice_note = (OWNED_EVENTS&&owned_hold&&!on_cur)?gtab[gsel_r]:n_hold;')
s=once(s,'if (!found_match && gact[n] && (gtab[n] == n_hold)) begin', '''if (!found_match && gact[n] &&
                (OWNED_EVENTS ? (owned_hold ? (group_owned[n]&&group_instance[n]==instance_hold) :
                (!group_owned[n]&&gtab[n]==n_hold)) : (gtab[n]==n_hold))) begin''')
s=once(s,"            gact <= {NG{1'b0}};", "            gact <= {NG{1'b0}};\n            group_owned<=0;owned_hold<=0;instance_hold<=0;")
s=once(s,'                group_start_tag[reset_group] <= 0;', '                group_start_tag[reset_group] <= 0;\n                group_instance[reset_group]<=0;')
s=once(s,'                        n_hold <= ev_note;', '''                        n_hold <= ev_note;
                        owned_hold<=OWNED_EVENTS && ev_owned;
                        instance_hold<=(OWNED_EVENTS && ev_owned)?ev_instance:{OWNER_W{1'b0}};''')
s=once(s,'                        gtab[gsel_r] <= n_hold;', '''                        gtab[gsel_r] <= n_hold;
                        group_owned[gsel_r]<=owned_hold;
                        group_instance[gsel_r]<=instance_hold;''')
s=once(s,"                        gact[gsel_r] <= 1'b0;", "                        gact[gsel_r] <= 1'b0;\n                        group_owned[gsel_r]<=0;")
(D/'note_map_owned.v').write_text(s,encoding='utf-8')
t=(R/'engine/tdm_top_rh.v').read_text(encoding='utf-8')
t=once(t,'module tdm_top_rh #(','module tdm_top_owned #(')
t=once(t,'    parameter integer LEGACY_PAD = 1','    parameter integer LEGACY_PAD = 1,\n    parameter integer OWNED_EVENTS = 0')
t=once(t,'    //---- 模式 ----','''    input wire own_valid,own_on,
    input wire [6:0] own_note,
    input wire [3:0] own_vel,
    input wire [12:0] own_instance,
    output wire own_ready,
    output wire result_valid,result_owned,result_on,result_success,
    output wire [12:0] result_instance,
    output wire [4:0] result_group,

    //---- 模式 ----''')
t=once(t,'.out_ready(nm_ev_ack), .level(ev_q_level)', '.out_ready(legacy_ev_ack), .level(ev_q_level)')
t=once(t,'    wire        nm_ev_ack;', '    wire legacy_ev_ack;\n    wire        nm_ev_ack;')
t=once(t,'    wire        ev_valid_r = ev_q_valid && !spec_commit_pending;','''    reg prefer_owned;
    wire select_owned=OWNED_EVENTS && !test_mode_eff && own_valid && (!ev_q_valid||prefer_owned);
    assign own_ready=select_owned&&nm_ev_ack;
    assign legacy_ev_ack=nm_ev_ack&&!select_owned;
    always @(posedge clk or negedge rst_n)
        if(!rst_n)prefer_owned<=1;
        else if(nm_ev_ack)prefer_owned<=!select_owned;
    wire        ev_valid_r = (select_owned?own_valid:ev_q_valid) && !spec_commit_pending;''')
t=once(t,'wire        ev_on_r    = ev_q_on;', 'wire        ev_on_r    = select_owned?own_on:ev_q_on;')
t=once(t,'wire [6:0]  ev_note_r  = ev_q_note;', 'wire [6:0]  ev_note_r  = select_owned?own_note:ev_q_note;')
t=once(t,'wire [3:0]  ev_vel_r   = ev_q_vel;', 'wire [3:0]  ev_vel_r   = select_owned?own_vel:ev_q_vel;')
t=once(t,'    note_map #(', '    note_map_owned #(')
t=once(t,".GLIDE_EN(1'b1), .SPEC_STAGED(1)",".GLIDE_EN(1'b1), .SPEC_STAGED(1), .OWNED_EVENTS(OWNED_EVENTS)")
t=once(t,'        .ev_vel({ev_vel_r, 4\'b0000}),', '''        .ev_owned(select_owned),.ev_instance(own_instance),
        .result_valid(result_valid),.result_owned(result_owned),.result_on(result_on),.result_success(result_success),.result_instance(result_instance),.result_group(result_group),
        .ev_vel({ev_vel_r, 4'b0000}),''')
(D/'tdm_top_owned.v').write_text(t,encoding='utf-8')
probe=(R/'rtl/rh_music_probe.v').read_text(encoding='utf-8')
probe=once(probe,'module rh_music_probe #(parameter integer LEGACY_PAD=1)(', 'module left_music_probe #(parameter integer NF=26,BAD_FRAMES=8,FRAME_TIMEOUT=2700000,LINK_TIMEOUT=8192)(')
probe=once(probe,'    input wire clk,rst_n,uart_rx_pin,','''    input wire left_valid,
    output wire left_ready,
    input wire [NF-1:0] left_contact,left_invalid,
    input wire [NF*9-1:0] left_position,
    input wire [31:0] left_sequence,
    input wire left_calibration,
    input wire [NF*7-1:0] left_note_map,
    input wire [3:0] left_velocity,
    output wire frame_error,link_error,sensor_error,watchdog_error,
    output wire [NF-1:0] bound_contacts,blocked_contacts,
    input wire clk,rst_n,uart_rx_pin,''')
probe=once(probe,'    input wire finger_valid,', '    output wire finger_valid,')
probe=once(probe,'    input wire [1:0] finger_cmd,', '    output wire [1:0] finger_cmd,')
probe=once(probe,'    input wire [4:0] finger_id,finger_group,', '    output wire [4:0] finger_id,finger_group,')
probe=once(probe,'    input wire signed [11:0] finger_position,', '    output wire signed [11:0] finger_position,')
probe=once(probe,'    rh_performance_control control(','''    wire own_valid,own_ready,own_on,result_valid,result_owned,result_on,result_success;
    wire [6:0] own_note;
    wire [3:0] own_vel;
    wire [12:0] own_instance,result_instance;
    wire [4:0] result_group;
    left_contact_bridge #(.NF(NF),.BAD_FRAMES(BAD_FRAMES),.FRAME_TIMEOUT(FRAME_TIMEOUT),.LINK_TIMEOUT(LINK_TIMEOUT)) bridge(
        .clk(clk),.rst_n(rst_n),.frame_valid(left_valid),.frame_ready(left_ready),.contact(left_contact),.invalid(left_invalid),.position(left_position),.frame_sequence(left_sequence),.frame_calibration(left_calibration),.note_map(left_note_map),.velocity(left_velocity),
        .own_valid(own_valid),.own_ready(own_ready),.own_on(own_on),.own_note(own_note),.own_vel(own_vel),.own_instance(own_instance),
        .result_valid(result_valid),.result_owned(result_owned),.result_on(result_on),.result_success(result_success),.result_instance(result_instance),.result_group(result_group),
        .voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),.finger_group(finger_group),.finger_position(finger_position),
        .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound_contacts),.blocked_contacts(blocked_contacts));
    rh_performance_control control(''')
probe=once(probe,'    tdm_top_rh #(', '    tdm_top_owned #(')
probe=once(probe,'.LEGACY_PAD(LEGACY_PAD)', '.LEGACY_PAD(0),.OWNED_EVENTS(1)')
probe=once(probe,'        .ev_valid(ev_valid),', '''        .own_valid(own_valid),.own_ready(own_ready),.own_on(own_on),.own_note(own_note),.own_vel(own_vel),.own_instance(own_instance),
        .result_valid(result_valid),.result_owned(result_owned),.result_on(result_on),.result_success(result_success),.result_instance(result_instance),.result_group(result_group),
        .ev_valid(ev_valid),''')
(R/'rtl/left_music_probe.v').write_text(probe,encoding='utf-8')
print('Prepared identity-aware candidates; original queues and modules retained')
