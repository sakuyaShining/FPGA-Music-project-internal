module note_duet_probe #(parameter TICKET_W=8)(
    input wire clk,rst_n,sample_en,
    input wire cancel_valid,
    input wire [31:0] cancel_token,
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
    output wire boot_ready,protocol_error,context_active,
    input wire live_valid,live_on,
    output wire live_ready,
    input wire [30:0] live_serial,
    input wire [6:0] live_note,
    input wire [7:0] live_velocity,
    input wire signed [17:0] live_glide,
    input wire [3:0] live_layers,
    input wire score_valid,score_on,
    output wire score_ready,
    input wire [30:0] score_serial,
    input wire [6:0] score_note,
    input wire [7:0] score_velocity,
    input wire signed [17:0] score_glide,
    input wire [3:0] score_layers,
    output wire live_response_valid,score_response_valid,
    input wire live_response_ready,score_response_ready,
    output wire [31:0] routed_token,routed_groups,
    output wire [2:0] routed_code,
    output wire [3:0] routed_layers,
    output wire [19:0] routed_map
);
    wire event_valid;
    wire event_ready;
    wire event_on;
    wire [31:0] event_token;
    wire [6:0] event_note;
    wire [7:0] event_velocity;
    wire signed [17:0] event_glide;
    wire [3:0] event_layers;
    wire response_valid;
    wire response_ready;
    wire [31:0] response_token,response_groups;
    wire [2:0] response_code;
    wire [3:0] response_layers;
    wire [19:0] response_map;
    wire core_error,router_error;
    wire accept_live=live_valid&&live_ready;
    wire accept_score=score_valid&&score_ready;
    wire accept_event=accept_live||accept_score;
    wire accepted_on=accept_score?score_on:live_on;
    wire [31:0] accepted_token=accept_score?{1'b1,score_serial}:{1'b0,live_serial};
    wire response_accepted=response_valid&&response_ready;
    reg route_busy,route_on,cancel_pending;
    reg [31:0] route_token;
    wire core_cancel_valid=cancel_valid||cancel_pending;
    wire [31:0] core_cancel_token=cancel_pending?route_token:cancel_token;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin route_busy<=0;route_on<=0;route_token<=0;cancel_pending<=0;end
        else begin
            if(accept_event)begin
                route_busy<=1;route_on<=accepted_on;route_token<=accepted_token;cancel_pending<=0;
            end
            if(cancel_valid&&((route_busy&&route_on&&cancel_token==route_token)||
                (accept_event&&accepted_on&&cancel_token==accepted_token)))cancel_pending<=1;
            if(response_accepted)begin route_busy<=0;cancel_pending<=0;end
        end
    end
    note_event_router router(
        .clk(clk),
        .rst_n(rst_n),
        .live_valid(live_valid),
        .live_on(live_on),
        .live_ready(live_ready),
        .live_serial(live_serial),
        .live_note(live_note),
        .live_velocity(live_velocity),
        .live_glide(live_glide),
        .live_layers(live_layers),
        .score_valid(score_valid),
        .score_on(score_on),
        .score_ready(score_ready),
        .score_serial(score_serial),
        .score_note(score_note),
        .score_velocity(score_velocity),
        .score_glide(score_glide),
        .score_layers(score_layers),
        .event_valid(event_valid),
        .event_ready(event_ready),
        .event_on(event_on),
        .event_token(event_token),
        .event_note(event_note),
        .event_velocity(event_velocity),
        .event_glide(event_glide),
        .event_layers(event_layers),
        .response_valid(response_valid),
        .response_ready(response_ready),
        .response_token(response_token),
        .response_groups(response_groups),
        .response_code(response_code),
        .response_layers(response_layers),
        .response_map(response_map),
        .live_response_valid(live_response_valid),
        .score_response_valid(score_response_valid),
        .live_response_ready(live_response_ready),
        .score_response_ready(score_response_ready),
        .routed_token(routed_token),
        .routed_groups(routed_groups),
        .routed_code(routed_code),
        .routed_layers(routed_layers),
        .routed_map(routed_map),
        .protocol_error(router_error)
    );
    note_resource_instrument_probe #(.TICKET_W(TICKET_W)) core(
        .clk(clk),
        .rst_n(rst_n),
        .sample_en(sample_en),
        .ev_valid(event_valid),
        .ev_on(event_on),
        .ev_ready(event_ready),
        .ev_token(event_token),
        .ev_note(event_note),
        .ev_velocity(event_velocity),
        .ev_glide(event_glide),
        .layer_selection(event_layers),
        .cancel_valid(core_cancel_valid),
        .cancel_token(core_cancel_token),
        .rsp_valid(response_valid),
        .rsp_ready(response_ready),
        .rsp_code(response_code),
        .rsp_token(response_token),
        .rsp_groups(response_groups),
        .rsp_layers(response_layers),
        .rsp_map(response_map),
        .cfg_valid(cfg_valid),
        .cfg_commit(cfg_commit),
        .cfg_slot(cfg_slot),
        .cfg_part(cfg_part),
        .cfg_word(cfg_word),
        .cfg_ready(cfg_ready),
        .cfg_applied(cfg_applied),
        .cfg_error(cfg_error),
        .cfg_enabled_status(cfg_enabled_status),
        .spec_we(spec_we),
        .spec_commit(spec_commit),
        .spec_addr(spec_addr),
        .spec_wdata(spec_wdata),
        .spec_replace(spec_replace),
        .pad_mask(pad_mask),
        .tilt(tilt),
        .tilt_vbias(tilt_vbias),
        .tilt_vgain(tilt_vgain),
        .vel_vscale(vel_vscale),
        .artic_enable(artic_enable),
        .artic_mask(artic_mask),
        .strike_d_m(strike_d_m),
        .strike_d_k_base(strike_d_k_base),
        .strike_d_k_curve(strike_d_k_curve),
        .strike_s_lvl(strike_s_lvl),
        .pmod_cfg(pmod_cfg),
        .timbre_gain_q8(timbre_gain_q8),
        .timbre_voice_mask(timbre_voice_mask),
        .finger_active(finger_active),
        .finger_offsets(finger_offsets),
        .d2_lvl(d2_lvl),
        .d2_k(d2_k),
        .pcm(pcm),
        .active_groups(active_groups),
        .reserved_groups(reserved_groups),
        .active_count(active_count),
        .boot_ready(boot_ready),
        .protocol_error(core_error),
        .context_active(context_active)
    );
    assign protocol_error=core_error||router_error;
endmodule
