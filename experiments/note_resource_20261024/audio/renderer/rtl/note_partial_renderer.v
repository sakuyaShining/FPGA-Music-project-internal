module note_partial_renderer #(parameter TICKET_W=8)(
    input wire clk,rst_n,
    input wire note_valid,
    output wire note_ready,
    input wire [31:0] note_token,
    input wire [6:0] note_number,
    input wire [7:0] note_velocity,
    input wire signed [17:0] note_glide,
    input wire note_finish,
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
    input wire part_valid,
    output wire part_ready,
    input wire [TICKET_W-1:0] part_ticket,
    input wire [31:0] part_token,
    input wire [1:0] part_layer,
    input wire [3:0] part_index,
    output wire part_rsp_valid,
    input wire part_rsp_ready,
    output reg [TICKET_W-1:0] part_rsp_ticket,
    output reg [31:0] part_rsp_token,
    output reg [1:0] part_rsp_layer,
    output reg [3:0] part_rsp_index,
    output reg [23:0] part_inc,
    output reg [7:0] part_amp,
    output reg [22:0] part_epar,
    output reg [39:0] part_env,
    output reg signed [17:0] part_gq,
    output reg protocol_error,
    output wire context_active
);
    localparam IDLE=0,READ_WAIT=1,EMIT=2,RESPOND=3;
    reg [1:0] state;
    reg context_valid;
    reg [31:0] token_hold;
    reg [6:0] note_hold;
    reg [7:0] velocity_hold,tilt_hold,tilt_gain_hold;
    reg signed [9:0] tilt_bias_hold;
    reg signed [17:0] glide_hold;
    reg [8:0] scale_hold;
    reg [3:0] enabled_hold,banks_hold;
    reg replace_hold,artic_hold;
    reg [15:0] pad_hold,artic_mask_hold;
    reg [1:0] strike_m_hold;
    reg [4:0] strike_k_hold;
    reg [3:0] strike_curve_hold,strike_sustain_hold;
    reg [127:0] spectrum_hold;
    reg [7:0] spectrum[0:15],spectrum_pending[0:15];
    reg [1:0] layer_hold;
    reg [3:0] index_hold;
    reg [23:0] note_rom[0:127];
    reg [47:0] preset_rom[0:63];
    reg [11:0] tilt_rom[0:255];
    initial begin
        $readmemh("note_inc.hex",note_rom);
        $readmemh("preset_part.hex",preset_rom);
        $readmemh("tilt_wtab.hex",tilt_rom);
    end
    wire [3:0] cfg_enabled,cfg_banks;
    wire [87:0] custom_word;
    assign cfg_ready=!context_valid&&state==IDLE;
    assign cfg_enabled_status=cfg_enabled;
    instrument_table table_store(.clk(clk),.rst_n(rst_n),.valid(cfg_valid&&cfg_ready),
        .commit(cfg_commit),.slot(cfg_slot),.part(cfg_part),.word(cfg_word),
        .applied(cfg_applied),.error(cfg_error),.enabled(cfg_enabled),.banks(cfg_banks),
        .read_addr({layer_hold,banks_hold[layer_hold],index_hold}),.read_word(custom_word));
    assign note_ready=!context_valid&&state==IDLE&&!cfg_valid&&!spec_commit;
    assign context_active=context_valid;
    assign part_ready=context_valid&&state==IDLE&&part_token==token_hold&&!note_finish;
    assign part_rsp_valid=state==RESPOND;
    wire custom=enabled_hold[layer_hold];
    wire [47:0] entry_word=custom?custom_word[47:0]:preset_rom[{layer_hold,index_hold}];
    wire [39:0] env_base=custom?custom_word[87:48]:40'd0;
    wire [7:0] base_amp=entry_word[31:24];
    wire [39:0] increment_product=note_rom[note_hold]*entry_word[47:32];
    wire nyquist_kill=|increment_product[39:31];
    wire [7:0] spectrum_value=pad_hold[index_hold]?8'd255:spectrum_hold[index_hold*8+:8];
    wire [8:0] sum_amp={1'b0,base_amp}+{1'b0,spectrum_value};
    wire [7:0] added_amp=sum_amp>255?8'd255:sum_amp[7:0];
    wire [7:0] source_amp=custom?base_amp:(replace_hold?spectrum_value:added_amp);
    wire [8:0] tilt_weight=tilt_rom[{tilt_hold[7:4],index_hold}][8:0];
    wire [8:0] bounded_tilt=tilt_weight<64?9'd64:tilt_weight;
    wire [16:0] tilted_product=source_amp*bounded_tilt;
    wire [9:0] tilted_shift=tilted_product[16:8];
    wire [7:0] tilted_amp=tilted_shift>255?8'd255:tilted_shift[7:0];
    wire [7:0] shaped_amp;
    vel_shape_scaled shape(.vel(velocity_hold[7:4]),.slot(layer_hold),.part(index_hold),.base(tilted_amp),
        .tilt_bias(tilt_bias_hold),.tilt_gain(tilt_gain_hold),.vscale(scale_hold),.amp(shaped_amp));
    wire [15:0] velocity_product=shaped_amp*velocity_hold;
    wire strike=artic_hold&&artic_mask_hold[index_hold];
    wire [7:0] curve_product=index_hold*strike_curve_hold;
    wire [3:0] curve_offset=curve_product[7:4];
    wire [4:0] decay_k=strike_k_hold>curve_offset?strike_k_hold-curve_offset:5'd0;
    wire [15:0] sustain_level=index_hold<4?{1'b0,strike_sustain_hold,11'd0}:16'd0;
    integer reset_index;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;context_valid<=0;token_hold<=0;note_hold<=0;velocity_hold<=0;glide_hold<=0;
            tilt_hold<=0;tilt_gain_hold<=0;tilt_bias_hold<=0;scale_hold<=0;enabled_hold<=0;banks_hold<=0;
            replace_hold<=0;artic_hold<=0;pad_hold<=0;artic_mask_hold<=0;strike_m_hold<=0;strike_k_hold<=0;
            strike_curve_hold<=0;strike_sustain_hold<=0;spectrum_hold<=0;layer_hold<=0;index_hold<=0;
            part_rsp_ticket<=0;part_rsp_token<=0;part_rsp_layer<=0;part_rsp_index<=0;
            part_inc<=0;part_amp<=0;part_epar<=0;part_env<=0;part_gq<=0;protocol_error<=0;
            for(reset_index=0;reset_index<16;reset_index=reset_index+1)begin
                spectrum[reset_index]<=0;spectrum_pending[reset_index]<=0;
            end
        end else begin
            if(spec_we)spectrum_pending[spec_addr]<=spec_wdata;
            if(spec_commit)
                for(reset_index=0;reset_index<16;reset_index=reset_index+1)
                    spectrum[reset_index]<=(spec_we&&spec_addr==reset_index)?spec_wdata:spectrum_pending[reset_index];
            if(note_valid&&note_ready)begin
                context_valid<=1;token_hold<=note_token;note_hold<=note_number;velocity_hold<=note_velocity;glide_hold<=note_glide;
                enabled_hold<=cfg_enabled;banks_hold<=cfg_banks;tilt_hold<=tilt;tilt_gain_hold<=tilt_vgain;
                tilt_bias_hold<=tilt_vbias;scale_hold<=vel_vscale;replace_hold<=spec_replace;pad_hold<=pad_mask;
                artic_hold<=artic_enable;artic_mask_hold<=artic_mask;strike_m_hold<=strike_d_m;
                strike_k_hold<=strike_d_k_base;strike_curve_hold<=strike_d_k_curve;strike_sustain_hold<=strike_s_lvl;
                for(reset_index=0;reset_index<16;reset_index=reset_index+1)spectrum_hold[reset_index*8+:8]<=spectrum[reset_index];
            end
            if(note_finish)begin
                if(state!=IDLE)protocol_error<=1;
                else context_valid<=0;
            end
            if(part_valid&&context_valid&&state==IDLE&&part_token!=token_hold)protocol_error<=1;
            case(state)
                IDLE:if(part_valid&&part_ready)begin
                    part_rsp_ticket<=part_ticket;part_rsp_token<=part_token;
                    part_rsp_layer<=part_layer;part_rsp_index<=part_index;
                    layer_hold<=part_layer;index_hold<=part_index;state<=READ_WAIT;
                end
                READ_WAIT:state<=EMIT;
                EMIT:begin
                    part_inc<=increment_product[31:8];part_amp<=nyquist_kill?8'd0:velocity_product[15:8];
                    part_epar<=strike?{sustain_level,strike_m_hold,decay_k}:entry_word[22:0];
                    part_env<=strike?{env_base[39:15],4'd0,env_base[10:0]}:env_base;
                    part_gq<=glide_hold;state<=RESPOND;
                end
                RESPOND:if(part_rsp_ready)state<=IDLE;
            endcase
        end
    end
endmodule
