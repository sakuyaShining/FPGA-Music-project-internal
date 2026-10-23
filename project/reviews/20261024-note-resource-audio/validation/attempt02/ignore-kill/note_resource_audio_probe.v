module note_resource_audio_probe #(parameter TICKET_W=8)(
    input wire clk,rst_n,sample_en,
    input wire req_valid,
    output wire req_ready,
    input wire [1:0] req_kind,
    input wire [31:0] req_token,
    input wire [3:0] req_layers,
    input wire cancel_valid,
    input wire [31:0] cancel_token,
    output wire rsp_valid,
    input wire rsp_ready,
    output wire [2:0] rsp_code,
    output wire [31:0] rsp_token,rsp_groups,
    output wire [3:0] rsp_layers,
    output wire [19:0] rsp_map,
    output wire part_valid,
    input wire part_ready,
    output wire [TICKET_W-1:0] part_ticket,
    output wire [31:0] part_token,
    output wire [1:0] part_layer,
    output wire [3:0] part_index,
    input wire part_rsp_valid,
    output wire part_rsp_ready,
    input wire [TICKET_W-1:0] part_rsp_ticket,
    input wire [31:0] part_rsp_token,
    input wire [1:0] part_rsp_layer,
    input wire [3:0] part_rsp_index,
    input wire [23:0] part_inc,
    input wire [7:0] part_amp,
    input wire [22:0] part_epar,
    input wire [39:0] part_env,
    input wire signed [17:0] part_gq,
    input wire [57:0] pmod_cfg,
    input wire [159:0] timbre_gain_q8,
    input wire [31:0] timbre_voice_mask,finger_active,
    input wire [575:0] finger_offsets,
    input wire [15:0] d2_lvl,
    input wire [4:0] d2_k,
    output wire signed [23:0] pcm,
    output wire [31:0] active_groups,reserved_groups,
    output wire [5:0] active_count,
    output wire boot_ready,protocol_error
);
    wire manager_ready,manager_rsp_valid,manager_rsp_ready;
    wire finish_valid,finish_ready;
    wire [31:0] finish_token,finish_groups;
    reg internal_request;
    assign req_ready=boot_ready&&manager_ready&&!finish_valid;
    assign finish_ready=boot_ready&&manager_ready;
    assign rsp_valid=manager_rsp_valid&&!internal_request;
    assign manager_rsp_ready=internal_request||rsp_ready;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)internal_request<=0;
        else if(boot_ready&&manager_ready&&(finish_valid||req_valid))internal_request<=finish_valid;
    end
    wire work_valid,work_ready,done_valid,done_ready;
    wire [1:0] work_kind;
    wire [TICKET_W-1:0] work_ticket,done_ticket;
    wire [31:0] work_token,work_groups,done_token;
    wire [3:0] work_layers;
    wire [19:0] work_map;
    wire manager_error,backend_error;
    note_resource_mgr #(.TICKET_W(TICKET_W)) manager(
        .clk(clk),.rst_n(rst_n),.req_valid(boot_ready&&(finish_valid||req_valid)),.req_ready(manager_ready),
        .req_kind(finish_valid?2'd2:req_kind),.req_token(finish_valid?finish_token:req_token),
        .req_layers(finish_valid?4'd0:req_layers),.req_groups(finish_valid?finish_groups:32'd0),
        .cancel_valid(cancel_valid),.cancel_token(cancel_token),
        .work_valid(work_valid),.work_ready(work_ready),.work_kind(work_kind),.work_ticket(work_ticket),
        .work_token(work_token),.work_groups(work_groups),.work_layers(work_layers),.work_map(work_map),
        .done_valid(done_valid),.done_ready(done_ready),.done_ticket(done_ticket),.done_token(done_token),
        .rsp_valid(manager_rsp_valid),.rsp_ready(manager_rsp_ready),.rsp_code(rsp_code),.rsp_token(rsp_token),
        .rsp_groups(rsp_groups),.rsp_layers(rsp_layers),.rsp_map(rsp_map),
        .active_groups(active_groups),.reserved_groups(reserved_groups),.active_count(active_count),.protocol_error(manager_error));
    wire load_en,load_gate,load_kill,publish_valid,publish_ready,publish_done;
    wire [8:0] load_slot;
    wire [23:0] load_inc;
    wire [7:0] load_amp,load_start_tag;
    wire [22:0] load_epar;
    wire [39:0] load_env;
    wire signed [17:0] load_gq;
    wire [31:0] publish_groups,quiet_groups;
    note_audio_backend #(.TICKET_W(TICKET_W)) backend(
        .clk(clk),.rst_n(rst_n),.work_valid(work_valid),.work_ready(work_ready),.work_kind(work_kind),
        .work_ticket(work_ticket),.work_token(work_token),.work_groups(work_groups),.work_layers(work_layers),.work_map(work_map),
        .done_valid(done_valid),.done_ready(done_ready),.done_ticket(done_ticket),.done_token(done_token),
        .part_valid(part_valid),.part_ready(part_ready),.part_ticket(part_ticket),.part_token(part_token),
        .part_layer(part_layer),.part_index(part_index),.part_rsp_valid(part_rsp_valid),.part_rsp_ready(part_rsp_ready),
        .part_rsp_ticket(part_rsp_ticket),.part_rsp_token(part_rsp_token),.part_rsp_layer(part_rsp_layer),.part_rsp_index(part_rsp_index),
        .part_inc(part_inc),.part_amp(part_amp),.part_epar(part_epar),.part_env(part_env),.part_gq(part_gq),
        .load_en(load_en),.load_slot(load_slot),.load_inc(load_inc),.load_amp(load_amp),.load_gate(load_gate),
        .load_kill(load_kill),.load_start_tag(load_start_tag),.load_epar(load_epar),.load_env(load_env),.load_gq(load_gq),
        .publish_valid(publish_valid),.publish_ready(publish_ready),.publish_done(publish_done),.publish_groups(publish_groups),
        .quiet_groups(quiet_groups),.finish_valid(finish_valid),.finish_ready(finish_ready),.finish_token(finish_token),
        .finish_groups(finish_groups),.boot_ready(boot_ready),.protocol_error(backend_error),.owned_groups(),.staged_groups());
    wire signed [23:0] engine_pcm;
    tdm_engine_transactional #(.NSLOT(512),.PART(16),.TRANSACTIONAL(1),.EXPLICIT_START(1),
        .INSTRUMENT_ENV(1),.FINGER_EXPR(1),.RIGHT_TIMBRE(1),.GAIN_UP(4)) engine(
        .clk(clk),.rst_n(rst_n),.sample_en(sample_en),.clr(1'b0),.pclr(1'b0),.gate_in(1'b1),
        .load_en(load_en),.load_slot(load_slot),.load_inc(load_inc),.load_amp(load_amp),.load_gate(load_gate),
        .load_start_tag(load_start_tag),.load_kill(load_kill),.load_epar(load_epar),.load_env(load_env),.load_gq(load_gq),
        .publish_valid(publish_valid),.publish_ready(publish_ready),.publish_groups(publish_groups),
        .publish_done(publish_done),.quiet_groups(quiet_groups),.pmod_cfg(pmod_cfg),.finger_active(finger_active),
        .finger_offsets(finger_offsets),.timbre_gain_q8(timbre_gain_q8),.timbre_voice_mask(timbre_voice_mask),
        .env_en(1'b1),.a_inc(16'd117),.d_inc(16'd1),.d_m(2'd3),.d_k(5'd12),.s_lvl(16'd22938),
        .r_inc(16'd1),.r_m(2'd3),.r_k(5'd13),.d2_lvl(d2_lvl),.d2_k(d2_k),.env_cutoff(16'd100),.exp_mode(1'b1),
        .sample_out(engine_pcm),.sum_raw(),.slot_dbg());
    assign pcm=boot_ready?engine_pcm:24'sd0;
    assign protocol_error=manager_error||backend_error;
endmodule
