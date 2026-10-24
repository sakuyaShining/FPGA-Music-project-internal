module note_resource_instrument_probe #(parameter TICKET_W=8)(
    input wire clk,rst_n,sample_en,
    input wire ev_valid,ev_on,
    output wire ev_ready,
    input wire [31:0] ev_token,
    input wire [6:0] ev_note,
    input wire [7:0] ev_velocity,
    input wire signed [17:0] ev_glide,
    input wire [3:0] layer_selection,
    input wire cancel_valid,
    input wire [31:0] cancel_token,
    output wire rsp_valid,
    input wire rsp_ready,
    output wire [2:0] rsp_code,
    output wire [31:0] rsp_token,rsp_groups,
    output wire [3:0] rsp_layers,
    output wire [19:0] rsp_map,
    input wire cfg_valid,cfg_commit,
    input wire [1:0] cfg_slot,
    input wire [3:0] cfg_part,
    input wire [87:0] cfg_word,
    output wire cfg_ready,cfg_applied,cfg_error,
    output wire [3:0] cfg_enabled_status,
    input wire spec_we,spec_commit,
    input wire [3:0] spec_addr,
    input wire [7:0] spec_wdata,
    input wire spec_replace,
    input wire [15:0] pad_mask,
    input wire [7:0] tilt,
    input wire signed [9:0] tilt_vbias,
    input wire [7:0] tilt_vgain,
    input wire [8:0] vel_vscale,
    input wire artic_enable,
    input wire [15:0] artic_mask,
    input wire [1:0] strike_d_m,
    input wire [4:0] strike_d_k_base,
    input wire [3:0] strike_d_k_curve,strike_s_lvl,
    input wire [57:0] pmod_cfg,
    input wire [159:0] timbre_gain_q8,
    input wire [31:0] timbre_voice_mask,finger_active,
    input wire [575:0] finger_offsets,
    input wire [15:0] d2_lvl,
    input wire [4:0] d2_k,
    output wire signed [23:0] pcm,
    output wire [31:0] active_groups,reserved_groups,
    output wire [5:0] active_count,
    output wire boot_ready,protocol_error,context_active
);
    wire render_ready,core_ready;
    wire eligible=!ev_on||render_ready;
    assign ev_ready=core_ready&&eligible;
    wire part_valid,part_ready,part_rsp_valid,part_rsp_ready;
    wire [TICKET_W-1:0] part_ticket,part_rsp_ticket;
    wire [31:0] part_token,part_rsp_token;
    wire [1:0] part_layer,part_rsp_layer;
    wire [3:0] part_index,part_rsp_index;
    wire [23:0] part_inc;
    wire [7:0] part_amp;
    wire [22:0] part_epar;
    wire [39:0] part_env;
    wire signed [17:0] part_gq;
    wire core_error,renderer_error;
    note_partial_renderer #(.TICKET_W(TICKET_W)) renderer(
        .clk(clk),.rst_n(rst_n),.note_valid(ev_valid&&ev_ready&&ev_on),.note_ready(render_ready),
        .note_token(ev_token),.note_number(ev_note),.note_velocity(ev_velocity),.note_glide(ev_glide),
        .note_finish(rsp_valid&&rsp_ready&&context_active),
        .cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),
        .cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),.cfg_enabled_status(cfg_enabled_status),
        .spec_we(spec_we),.spec_commit(spec_commit),.spec_addr(spec_addr),.spec_wdata(spec_wdata),.spec_replace(spec_replace),
        .pad_mask(pad_mask),.tilt(tilt),.tilt_vbias(tilt_vbias),.tilt_vgain(tilt_vgain),.vel_vscale(vel_vscale),
        .artic_enable(artic_enable),.artic_mask(artic_mask),.strike_d_m(strike_d_m),.strike_d_k_base(strike_d_k_base),
        .strike_d_k_curve(strike_d_k_curve),.strike_s_lvl(strike_s_lvl),
        .part_valid(part_valid),.part_ready(part_ready),.part_ticket(part_ticket),.part_token(part_token),
        .part_layer(part_layer),.part_index(part_index),.part_rsp_valid(part_rsp_valid),.part_rsp_ready(part_rsp_ready),
        .part_rsp_ticket(part_rsp_ticket),.part_rsp_token(part_rsp_token),.part_rsp_layer(part_rsp_layer),.part_rsp_index(part_rsp_index),
        .part_inc(part_inc),.part_amp(part_amp),.part_epar(part_epar),.part_env(part_env),.part_gq(part_gq),
        .protocol_error(renderer_error),.context_active(context_active));
    note_resource_audio_probe #(.TICKET_W(TICKET_W)) core(
        .clk(clk),.rst_n(rst_n),.sample_en(sample_en),.req_valid(ev_valid&&eligible),.req_ready(core_ready),
        .req_kind(ev_on?2'd0:2'd1),.req_token(ev_token),.req_layers(layer_selection),
        .cancel_valid(cancel_valid),.cancel_token(cancel_token),
        .rsp_valid(rsp_valid),.rsp_ready(rsp_ready),.rsp_code(rsp_code),.rsp_token(rsp_token),
        .rsp_groups(rsp_groups),.rsp_layers(rsp_layers),.rsp_map(rsp_map),
        .part_valid(part_valid),.part_ready(part_ready),.part_ticket(part_ticket),.part_token(part_token),
        .part_layer(part_layer),.part_index(part_index),.part_rsp_valid(part_rsp_valid),.part_rsp_ready(part_rsp_ready),
        .part_rsp_ticket(part_rsp_ticket),.part_rsp_token(part_rsp_token),.part_rsp_layer(part_rsp_layer),.part_rsp_index(part_rsp_index),
        .part_inc(part_inc),.part_amp(part_amp),.part_epar(part_epar),.part_env(part_env),.part_gq(part_gq),
        .pmod_cfg(pmod_cfg),.timbre_gain_q8(timbre_gain_q8),.timbre_voice_mask(timbre_voice_mask),
        .finger_active(finger_active),.finger_offsets(finger_offsets),.d2_lvl(d2_lvl),.d2_k(d2_k),
        .pcm(pcm),.active_groups(active_groups),.reserved_groups(reserved_groups),.active_count(active_count),
        .boot_ready(boot_ready),.protocol_error(core_error));
    assign protocol_error=core_error||renderer_error;
endmodule
