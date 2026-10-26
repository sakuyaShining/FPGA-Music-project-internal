module note_resource_mgr #(parameter TICKET_W=8)(
    input wire clk, rst_n,
    input wire req_valid,
    output wire req_ready,
    input wire [1:0] req_kind,
    input wire [31:0] req_token,
    input wire [3:0] req_layers,
    input wire [31:0] req_groups,
    input wire cancel_valid,
    input wire [31:0] cancel_token,
    output wire work_valid,
    input wire work_ready,
    output reg [1:0] work_kind,
    output reg [TICKET_W-1:0] work_ticket,
    output reg [31:0] work_token, work_groups,
    output reg [3:0] work_layers,
    output reg [19:0] work_map,
    input wire done_valid,
    output wire done_ready,
    input wire [TICKET_W-1:0] done_ticket,
    input wire [31:0] done_token,
    output wire rsp_valid,
    input wire rsp_ready,
    output reg [2:0] rsp_code,
    output wire [31:0] rsp_token,
    output reg [31:0] rsp_groups,
    output reg [3:0] rsp_layers,
    output reg [19:0] rsp_map,
    output wire [31:0] active_groups, reserved_groups,
    output wire [5:0] active_count,
    output reg protocol_error
);
    localparam IDLE=0,LOOKUP=1,CHECK=2,FIND_ENTRY=3,FIND_GROUPS=4,
        VICTIM_SCAN=5,REMOVE_FIND=6,REMOVE_SHIFT=7,SEND=8,WAIT_DONE=9,
        COMPLETE=10,RESP=11;
    localparam ON=0,OFF=1,FINISH=2;
    localparam RELEASE=0,RETIRE=1,PREPARE=2,PUBLISH=3;
    localparam ALLOCATED=0,RELEASED=1,FINISHED=2,STALE=3,INVALID=4,DUPLICATE=5,CANCELLED=6;
    localparam AFTER_RELEASE=0,AFTER_STEAL=1,AFTER_PREPARE=2,AFTER_PUBLISH=3,AFTER_CANCEL=4;

    reg [3:0] state, remove_return;
    reg [2:0] continuation;
    reg [1:0] kind_hold;
    reg [31:0] token_hold, groups_hold, used_mask, reserve_mask;
    reg [3:0] layers_hold;
    reg [19:0] reserve_map;
    reg [31:0] entries_valid, entries_released;
    reg [31:0] entry_tokens[0:31], entry_masks[0:31];
    reg [3:0] entry_layers[0:31];
    reg [19:0] entry_maps[0:31];
    reg [4:0] order[0:31];
    reg [5:0] order_count, scan_index, group_index, shift_index;
    reg [2:0] layer_index;
    reg [4:0] entry_index, victim_index, remove_target;
    reg [TICKET_W-1:0] next_ticket;
    reg cancel_pending, publication_recorded;
    reg [1:0] source_serial_valid;
    reg [30:0] source_serial[0:1];

    function [5:0] group_count;
        input [31:0] mask;
        integer count_index;
        begin
            group_count=0;
            for(count_index=0;count_index<32;count_index=count_index+1)
                group_count=group_count+mask[count_index];
        end
    endfunction
    function [2:0] layer_count;
        input [3:0] mask;
        begin layer_count={2'd0,mask[0]}+{2'd0,mask[1]}+{2'd0,mask[2]}+{2'd0,mask[3]}; end
    endfunction
    function [3:0] remaining_layers;
        input [3:0] layers;
        input [19:0] mapping;
        input [31:0] finished;
        integer layer_number;
        begin
            remaining_layers=layers;
            for(layer_number=0;layer_number<4;layer_number=layer_number+1)
                if(layers[layer_number]&&finished[mapping[layer_number*5+:5]])
                    remaining_layers[layer_number]=0;
        end
    endfunction
    task issue_work;
        input [1:0] operation;
        input [31:0] token, mask;
        input [3:0] layers;
        input [19:0] mapping;
        input [2:0] following;
        begin
            work_kind<=operation;work_token<=token;work_groups<=mask;
            work_layers<=layers;work_map<=mapping;work_ticket<=next_ticket;
            next_ticket<=next_ticket+1'b1;continuation<=following;state<=SEND;
        end
    endtask
    task remove_entry;
        input [4:0] target;
        input [3:0] following;
        begin remove_target<=target;remove_return<=following;scan_index<=0;state<=REMOVE_FIND; end
    endtask
    wire cancel_now=cancel_pending||(cancel_valid&&cancel_token==token_hold);
    wire done_match=done_ticket==work_ticket&&done_token==work_token;
    wire [4:0] lookup_entry=scan_index[4:0];
    wire [4:0] scanned_victim=order[scan_index[4:0]];
    wire [31:0] finish_remaining=entry_masks[lookup_entry]&~groups_hold;
    wire [30:0] serial_delta=token_hold[30:0]-source_serial[token_hold[31]];
    wire fresh_token=!source_serial_valid[token_hold[31]]||(serial_delta!=0&&!serial_delta[30]);
    assign req_ready=state==IDLE;
    assign work_valid=state==SEND;
    assign done_ready=state==WAIT_DONE||(state==SEND&&work_ready);
    assign rsp_valid=state==RESP&&!(kind_hold==ON&&rsp_code==ALLOCATED&&cancel_now);
    assign rsp_token=token_hold;
    assign active_groups=used_mask;
    assign reserved_groups=reserve_mask;
    assign active_count=order_count;

    always @(posedge clk)begin
        if(!rst_n)begin
            state<=IDLE;remove_return<=RESP;continuation<=0;kind_hold<=0;
            token_hold<=0;groups_hold<=0;layers_hold<=0;used_mask<=0;
            reserve_mask<=0;reserve_map<=0;entries_valid<=0;entries_released<=0;
            order_count<=0;scan_index<=0;group_index<=0;shift_index<=0;
            layer_index<=0;entry_index<=0;victim_index<=0;remove_target<=0;
            next_ticket<=0;cancel_pending<=0;publication_recorded<=0;
            source_serial_valid<=0;
            work_kind<=0;work_ticket<=0;work_token<=0;work_groups<=0;
            work_layers<=0;work_map<=0;rsp_code<=0;rsp_groups<=0;rsp_layers<=0;rsp_map<=0;
            protocol_error<=0;
        end else begin
            if(done_valid&&done_ready&&!done_match)protocol_error<=1;
            case(state)
                IDLE:begin
                    if(req_valid)begin
                        kind_hold<=req_kind;token_hold<=req_token;
                        layers_hold<=req_layers;groups_hold<=req_groups;
                        reserve_mask<=0;reserve_map<=0;publication_recorded<=0;cancel_pending<=0;
                        rsp_groups<=0;rsp_layers<=0;rsp_map<=0;scan_index<=0;
                        if(req_kind==3||(req_kind==ON&&req_layers==0))begin rsp_code<=INVALID;state<=RESP;end
                        else state<=LOOKUP;
                    end
                end
                LOOKUP:begin
                    if(entries_valid[lookup_entry]&&entry_tokens[lookup_entry]==token_hold)begin
                        entry_index<=lookup_entry;
                        if(kind_hold==ON)begin
                            rsp_code<=DUPLICATE;rsp_groups<=entry_masks[lookup_entry];
                            rsp_layers<=entry_layers[lookup_entry];rsp_map<=entry_maps[lookup_entry];state<=RESP;
                        end else if(kind_hold==OFF)begin
                            rsp_groups<=entry_masks[lookup_entry];rsp_layers<=entry_layers[lookup_entry];rsp_map<=entry_maps[lookup_entry];
                            entries_released[lookup_entry]<=1;
                            if(entries_released[lookup_entry])begin rsp_code<=RELEASED;state<=RESP;end
                            else issue_work(RELEASE,token_hold,entry_masks[lookup_entry],entry_layers[lookup_entry],entry_maps[lookup_entry],AFTER_RELEASE);
                        end else begin
                            if(groups_hold==0)begin rsp_code<=INVALID;state<=RESP;end
                            else if((groups_hold&entry_masks[lookup_entry])==0)begin rsp_code<=STALE;state<=RESP;end
                            else if((groups_hold&~entry_masks[lookup_entry])!=0)begin rsp_code<=INVALID;state<=RESP;end
                            else begin
                                used_mask<=used_mask&~groups_hold;entry_masks[lookup_entry]<=finish_remaining;
                                entry_layers[lookup_entry]<=remaining_layers(entry_layers[lookup_entry],entry_maps[lookup_entry],groups_hold);
                                rsp_code<=FINISHED;rsp_groups<=groups_hold;
                                rsp_layers<=remaining_layers(entry_layers[lookup_entry],entry_maps[lookup_entry],groups_hold);
                                rsp_map<=entry_maps[lookup_entry];
                                if(finish_remaining==0)begin
                                    entries_valid[lookup_entry]<=0;entries_released[lookup_entry]<=0;
                                    remove_entry(lookup_entry,RESP);
                                end else state<=RESP;
                            end
                        end
                    end else if(scan_index==31)begin
                        if(kind_hold==ON&&fresh_token)begin
                            source_serial_valid[token_hold[31]]<=1;source_serial[token_hold[31]]<=token_hold[30:0];state<=CHECK;
                        end else if(kind_hold==ON)begin rsp_code<=STALE;state<=RESP;end
                        else begin rsp_code<=STALE;state<=RESP;end
                    end else scan_index<=scan_index+1'b1;
                end
                CHECK:begin
                    if(cancel_now)begin rsp_code<=CANCELLED;reserve_mask<=0;state<=RESP;end
                    else if(32-group_count(used_mask)>=layer_count(layers_hold)&&order_count<32)begin
                        scan_index<=0;state<=FIND_ENTRY;
                    end else if(order_count==0)begin protocol_error<=1;rsp_code<=INVALID;state<=RESP;end
                    else begin scan_index<=0;state<=VICTIM_SCAN;end
                end
                FIND_ENTRY:begin
                    if(cancel_now)begin rsp_code<=CANCELLED;state<=RESP;end
                    else if(!entries_valid[lookup_entry])begin
                        entry_index<=lookup_entry;layer_index<=0;group_index<=0;state<=FIND_GROUPS;
                    end else if(scan_index==31)begin protocol_error<=1;rsp_code<=INVALID;state<=RESP;end
                    else scan_index<=scan_index+1'b1;
                end
                FIND_GROUPS:begin
                    if(cancel_now)begin rsp_code<=CANCELLED;reserve_mask<=0;state<=RESP;end
                    else if(layer_index==4)issue_work(PREPARE,token_hold,reserve_mask,layers_hold,reserve_map,AFTER_PREPARE);
                    else if(!layers_hold[layer_index])layer_index<=layer_index+1'b1;
                    else if(group_index==32)begin protocol_error<=1;rsp_code<=INVALID;reserve_mask<=0;state<=RESP;end
                    else if(used_mask[group_index[4:0]])group_index<=group_index+1'b1;
                    else begin
                        reserve_mask[group_index[4:0]]<=1;reserve_map[layer_index*5+:5]<=group_index[4:0];
                        layer_index<=layer_index+1'b1;group_index<=group_index+1'b1;
                    end
                end
                VICTIM_SCAN:begin
                    if(cancel_now)begin rsp_code<=CANCELLED;state<=RESP;end
                    else if(entries_released[scanned_victim])begin
                        victim_index<=scanned_victim;
                        issue_work(RETIRE,entry_tokens[scanned_victim],entry_masks[scanned_victim]&(~entry_masks[scanned_victim]+1'b1),entry_layers[scanned_victim],entry_maps[scanned_victim],AFTER_STEAL);
                    end else if(scan_index+1>=order_count)begin
                        victim_index<=order[0];
                        issue_work(RETIRE,entry_tokens[order[0]],entry_masks[order[0]],entry_layers[order[0]],entry_maps[order[0]],AFTER_STEAL);
                    end else scan_index<=scan_index+1'b1;
                end
                SEND:begin
                    if(work_ready)begin
                        if(done_valid&&done_match)state<=COMPLETE;
                        else state<=WAIT_DONE;
                    end
                end
                WAIT_DONE:if(done_valid&&done_match)state<=COMPLETE;
                COMPLETE:begin
                    case(continuation)
                        AFTER_RELEASE:begin rsp_code<=RELEASED;state<=RESP;end
                        AFTER_STEAL:begin
                            entries_valid[victim_index]<=0;entries_released[victim_index]<=0;
                            used_mask<=used_mask&~entry_masks[victim_index];remove_entry(victim_index,CHECK);
                        end
                        AFTER_PREPARE:begin
                            if(cancel_now)issue_work(RETIRE,token_hold,reserve_mask,layers_hold,reserve_map,AFTER_CANCEL);
                            else issue_work(PUBLISH,token_hold,reserve_mask,layers_hold,reserve_map,AFTER_PUBLISH);
                        end
                        AFTER_PUBLISH:begin
                            if(cancel_now)issue_work(RETIRE,token_hold,reserve_mask,layers_hold,reserve_map,AFTER_CANCEL);
                            else begin
                                entries_valid[entry_index]<=1;entries_released[entry_index]<=0;
                                entry_tokens[entry_index]<=token_hold;entry_masks[entry_index]<=reserve_mask;
                                entry_layers[entry_index]<=layers_hold;entry_maps[entry_index]<=reserve_map;
                                used_mask<=used_mask|reserve_mask;order[order_count[4:0]]<=entry_index;order_count<=order_count+1'b1;
                                rsp_groups<=reserve_mask;rsp_layers<=layers_hold;rsp_map<=reserve_map;
                                reserve_mask<=0;publication_recorded<=1;rsp_code<=ALLOCATED;state<=RESP;
                            end
                        end
                        AFTER_CANCEL:begin
                            reserve_mask<=0;rsp_code<=CANCELLED;rsp_groups<=0;rsp_layers<=0;rsp_map<=0;
                            if(publication_recorded)begin
                                entries_valid[entry_index]<=0;entries_released[entry_index]<=0;
                                used_mask<=used_mask&~entry_masks[entry_index];publication_recorded<=0;
                                remove_entry(entry_index,RESP);
                            end else state<=RESP;
                        end
                        default:begin protocol_error<=1;rsp_code<=INVALID;state<=RESP;end
                    endcase
                end
                REMOVE_FIND:begin
                    if(order[scan_index[4:0]]==remove_target)begin shift_index<=scan_index;state<=REMOVE_SHIFT;end
                    else if(scan_index+1>=order_count)begin protocol_error<=1;rsp_code<=INVALID;state<=RESP;end
                    else scan_index<=scan_index+1'b1;
                end
                REMOVE_SHIFT:begin
                    if(shift_index+1<order_count)begin
                        order[shift_index[4:0]]<=order[shift_index[4:0]+1'b1];shift_index<=shift_index+1'b1;
                    end else begin order_count<=order_count-1'b1;state<=remove_return;end
                end
                RESP:begin
                    if(kind_hold==ON&&rsp_code==ALLOCATED&&cancel_now&&publication_recorded)
                        issue_work(RETIRE,token_hold,entry_masks[entry_index],entry_layers[entry_index],entry_maps[entry_index],AFTER_CANCEL);
                    else if(rsp_ready)begin reserve_mask<=0;state<=IDLE;end
                end
                default:begin protocol_error<=1;state<=IDLE;end
            endcase
            if(cancel_valid&&((state!=IDLE&&kind_hold==ON&&cancel_token==token_hold)||
               (state==IDLE&&req_valid&&req_kind==ON&&cancel_token==req_token)))cancel_pending<=1;
        end
    end
endmodule
