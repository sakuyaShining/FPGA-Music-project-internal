module note_audio_backend #(parameter TICKET_W=8)(
    input wire clk,rst_n,
    input wire work_valid,
    output wire work_ready,
    input wire [1:0] work_kind,
    input wire [TICKET_W-1:0] work_ticket,
    input wire [31:0] work_token,work_groups,
    input wire [3:0] work_layers,
    input wire [19:0] work_map,
    output reg done_valid,
    input wire done_ready,
    output reg [TICKET_W-1:0] done_ticket,
    output reg [31:0] done_token,
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
    output wire load_en,
    output wire [8:0] load_slot,
    output wire [23:0] load_inc,
    output wire [7:0] load_amp,load_start_tag,
    output wire load_gate,load_kill,
    output wire [22:0] load_epar,
    output wire [39:0] load_env,
    output wire signed [17:0] load_gq,
    output wire publish_valid,
    input wire publish_ready,publish_done,
    output wire [31:0] publish_groups,
    input wire [31:0] quiet_groups,
    output reg finish_valid,
    input wire finish_ready,
    output reg [31:0] finish_token,
    output wire [31:0] finish_groups,
    output reg boot_ready,protocol_error,
    output wire [31:0] owned_groups,staged_groups
);
    localparam BOOT_WRITE=0,BOOT_PUBLISH=1,BOOT_WAIT=2,IDLE=3,
        LAYER_SCAN=4,PART_SEND=5,PART_WAIT=6,CLEAR_WRITE=7,PUB_SEND=8,PUB_WAIT=9,RETURN=10;
    reg [3:0] state;
    reg [1:0] kind_hold;
    reg [TICKET_W-1:0] ticket_hold;
    reg [31:0] token_hold,groups_hold,owned_mask,prepared_mask;
    reg [3:0] layers_hold;
    reg [19:0] map_hold;
    reg [2:0] layer_number;
    reg [3:0] partial_number;
    reg [8:0] clear_slot;
    reg [4:0] finish_scan,finish_group;
    reg [31:0] owner_token[0:31];
    reg [7:0] start_tag[0:31];
    wire [4:0] mapped_group=map_hold[layer_number[1:0]*5+:5];
    wire response_match=part_rsp_ticket==ticket_hold&&part_rsp_token==token_hold&&
        part_rsp_layer==layer_number[1:0]&&part_rsp_index==partial_number;
    wire response_fire=state==PART_WAIT&&part_rsp_valid&&response_match;
    wire [31:0] finish_mask=32'b1<<finish_group;
    wire finish_clear=finish_valid&&finish_ready&&owned_mask[finish_group]&&owner_token[finish_group]==finish_token;
    wire [31:0] owned_after_finish=owned_mask&~(finish_clear?finish_mask:32'd0);
    reg [31:0] request_map;
    reg map_unique;
    integer check_layer;
    always @*begin
        request_map=0;map_unique=1;
        for(check_layer=0;check_layer<4;check_layer=check_layer+1)begin
            if(work_layers[check_layer])begin
                if(request_map[work_map[check_layer*5+:5]])map_unique=0;
                request_map[work_map[check_layer*5+:5]]=1;
            end
        end
    end
    wire format_ok=work_groups!=0&&map_unique&&request_map==work_groups&&
        (work_kind!=2||(work_groups&(owned_mask|prepared_mask))==0)&&
        (work_kind!=3||(work_groups&prepared_mask)==work_groups);
    assign work_ready=boot_ready&&state==IDLE&&!done_valid&&format_ok;
    assign part_valid=state==PART_SEND;
    assign part_ticket=ticket_hold;
    assign part_token=token_hold;
    assign part_layer=layer_number[1:0];
    assign part_index=partial_number;
    assign part_rsp_ready=state==PART_WAIT;
    assign load_en=state==BOOT_WRITE||(state==CLEAR_WRITE&&groups_hold[clear_slot[8:4]])||response_fire;
    assign load_slot=response_fire?{mapped_group,partial_number}:clear_slot;
    assign load_inc=response_fire?part_inc:24'd0;
    assign load_amp=response_fire?part_amp:8'd0;
    assign load_epar=response_fire?part_epar:23'd0;
    assign load_env=response_fire?part_env:40'd0;
    assign load_gq=response_fire?part_gq:18'sd0;
    assign load_gate=response_fire;
    assign load_kill=state==BOOT_WRITE||(state==CLEAR_WRITE&&kind_hold==1);
    assign load_start_tag=response_fire?start_tag[mapped_group]+1'b1:start_tag[clear_slot[8:4]];
    assign publish_valid=state==BOOT_PUBLISH||state==PUB_SEND;
    assign publish_groups=state==BOOT_PUBLISH?32'hffffffff:groups_hold;
    assign finish_groups=finish_mask;
    assign owned_groups=owned_mask;
    assign staged_groups=prepared_mask;
    integer reset_group;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=BOOT_WRITE;kind_hold<=0;ticket_hold<=0;token_hold<=0;groups_hold<=0;
            layers_hold<=0;map_hold<=0;layer_number<=0;partial_number<=0;clear_slot<=0;
            done_valid<=0;done_ticket<=0;done_token<=0;boot_ready<=0;protocol_error<=0;
            finish_valid<=0;finish_token<=0;finish_scan<=0;finish_group<=0;owned_mask<=0;prepared_mask<=0;
            for(reset_group=0;reset_group<32;reset_group=reset_group+1)begin
                owner_token[reset_group]<=0;start_tag[reset_group]<=0;
            end
        end else begin
            owned_mask<=owned_after_finish;
            if(done_valid&&done_ready)done_valid<=0;
            if(part_rsp_valid&&part_rsp_ready&&!response_match)protocol_error<=1;
            if(work_valid&&state==IDLE&&!done_valid&&!format_ok)protocol_error<=1;
            if(finish_valid&&finish_ready)finish_valid<=0;
            if(boot_ready&&!finish_valid&&state==IDLE&&!done_valid)begin
                if(owned_mask[finish_scan]&&quiet_groups[finish_scan])begin
                    finish_valid<=1;finish_group<=finish_scan;finish_token<=owner_token[finish_scan];
                end
                finish_scan<=finish_scan+1'b1;
            end
            case(state)
                BOOT_WRITE:if(clear_slot==511)state<=BOOT_PUBLISH;else clear_slot<=clear_slot+1'b1;
                BOOT_PUBLISH:if(publish_ready)state<=BOOT_WAIT;
                BOOT_WAIT:if(publish_done)begin boot_ready<=1;state<=IDLE;end
                IDLE:if(work_valid&&work_ready)begin
                    kind_hold<=work_kind;ticket_hold<=work_ticket;token_hold<=work_token;
                    groups_hold<=work_groups;layers_hold<=work_layers;map_hold<=work_map;
                    layer_number<=0;partial_number<=0;clear_slot<=0;
                    if(work_kind==2)state<=LAYER_SCAN;
                    else if(work_kind==3)state<=PUB_SEND;
                    else state<=CLEAR_WRITE;
                end
                LAYER_SCAN:begin
                    if(layer_number==4)begin prepared_mask<=prepared_mask|groups_hold;state<=RETURN;end
                    else if(layers_hold[layer_number])begin partial_number<=0;state<=PART_SEND;end
                    else layer_number<=layer_number+1'b1;
                end
                PART_SEND:if(part_ready)state<=PART_WAIT;
                PART_WAIT:if(response_fire)begin
                    if(partial_number==15)begin
                        start_tag[mapped_group]<=start_tag[mapped_group]+1'b1;
                        layer_number<=layer_number+1'b1;state<=LAYER_SCAN;
                    end else begin partial_number<=partial_number+1'b1;state<=PART_SEND;end
                end
                CLEAR_WRITE:if(clear_slot==511)state<=PUB_SEND;else clear_slot<=clear_slot+1'b1;
                PUB_SEND:if(publish_ready)state<=PUB_WAIT;
                PUB_WAIT:if(publish_done)begin
                    if(kind_hold==3)begin
                        owned_mask<=owned_after_finish|groups_hold;prepared_mask<=prepared_mask&~groups_hold;
                        for(reset_group=0;reset_group<32;reset_group=reset_group+1)
                            if(groups_hold[reset_group])owner_token[reset_group]<=token_hold;
                    end else if(kind_hold==1)begin
                        owned_mask<=owned_after_finish&~groups_hold;prepared_mask<=prepared_mask&~groups_hold;
                    end
                    state<=RETURN;
                end
                RETURN:begin done_ticket<=ticket_hold;done_token<=token_hold;done_valid<=1;state<=IDLE;end
                default:begin protocol_error<=1;state<=BOOT_WRITE;boot_ready<=0;clear_slot<=0;end
            endcase
        end
    end
endmodule
