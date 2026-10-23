// Prototype: at most two selected slots out of four. No transpose or rhythm.
// A parent instance owns child IDs {parent,slot}; OFF uses the captured mask.
// This adapter is the sole producer of its child domain. Ordered completion.
module layer_dispatch #(parameter NF=26)(
    input wire clk,rst_n,
    input wire [3:0] selection,
    input wire parent_valid,parent_on,
    input wire [6:0] parent_note,
    input wire [3:0] parent_vel,
    input wire [12:0] parent_instance,
    output wire parent_ready,
    output reg parent_result,parent_success,parent_result_on,
    output reg [12:0] parent_result_instance,
    output wire [4:0] parent_group,
    output wire child_valid,child_on,
    output wire [6:0] child_note,
    output wire [3:0] child_vel,
    output wire [14:0] child_instance,
    output wire [1:0] child_preset,
    input wire child_ready,result_valid,result_owned,result_on,result_success,
    input wire [14:0] result_instance,
    input wire [4:0] result_group,
    input wire voice_valid,
    input wire [4:0] voice_group,
    input wire in_finger_valid,
    input wire [1:0] in_finger_cmd,
    input wire [4:0] in_finger_id,
    input wire signed [11:0] in_finger_position,
    output wire finger_valid,
    output wire [1:0] finger_cmd,
    output wire [4:0] finger_id,finger_group,
    output wire signed [11:0] finger_position,
    output reg protocol_error,selection_error
);
    localparam IDLE=0,PICK=1,SEND=2,WAIT_RESULT=3,FINISH=4,BIND=5;
    reg [2:0] state;
    reg [3:0] todo,mask_hold;
    reg [12:0] instance_hold;
    reg on_hold;
    reg [6:0] note_hold;
    reg [3:0] vel_hold;
    reg [1:0] slot_hold;
    reg any_success;
    reg [3:0] masks[0:NF-1];
    reg [7:0] generations[0:NF-1];
    reg [4:0] groups0[0:NF-1],groups1[0:NF-1];
    reg [1:0] slots0[0:NF-1],slots1[0:NF-1];
    reg [1:0] count[0:NF-1];
    reg [31:0] group_valid;
    reg [14:0] group_token[0:31];
    reg [4:0] bind_id;
    reg bind_second;
    reg signed [11:0] bind_position;
    wire [4:0] bind_group=bind_second?groups1[bind_id]:groups0[bind_id];
    wire [1:0] bind_slot=bind_second?slots1[bind_id]:slots0[bind_id];
    wire [4:0] lookup_group=(state==IDLE&&in_finger_valid&&in_finger_cmd==0)?groups0[in_finger_id]:
        ((state==BIND&&!bind_second&&count[bind_id]>1)?groups1[bind_id]:bind_group);
    reg [14:0] checked_token;
    always @(posedge clk)checked_token<=group_token[lookup_group];
    wire bind_ok=group_valid[bind_group]&&checked_token=={{generations[bind_id],bind_id},bind_slot};
    wire pass_cmd=state==IDLE&&in_finger_valid&&in_finger_cmd!=0;
    assign finger_valid=(state==BIND&&bind_ok)||pass_cmd;
    assign finger_cmd=state==BIND?2'd0:in_finger_cmd;
    assign finger_id=state==BIND?bind_id:in_finger_id;
    assign finger_group=bind_group;
    assign finger_position=state==BIND?bind_position:in_finger_position;
    assign parent_ready=state==IDLE&&!in_finger_valid;
    assign parent_group=parent_result_instance[4:0]; // virtual bridge handle
    assign child_valid=state==SEND;
    assign child_on=on_hold;
    assign child_note=note_hold;
    assign child_vel=vel_hold;
    assign child_instance={instance_hold,slot_hold};
    assign child_preset=slot_hold;
    wire [2:0] selected_count={2'b0,selection[0]}+{2'b0,selection[1]}+{2'b0,selection[2]}+{2'b0,selection[3]};
    reg [1:0] next_slot;
    always @* begin
        if(todo[0])next_slot=0;else if(todo[1])next_slot=1;else if(todo[2])next_slot=2;else next_slot=3;
    end
    integer i;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;todo<=0;mask_hold<=0;instance_hold<=0;on_hold<=0;note_hold<=0;vel_hold<=0;slot_hold<=0;any_success<=0;
            parent_result<=0;parent_success<=0;parent_result_on<=0;parent_result_instance<=0;group_valid<=0;
            bind_id<=0;bind_second<=0;bind_position<=0;protocol_error<=0;selection_error<=0;
            for(i=0;i<NF;i=i+1)begin masks[i]<=0;generations[i]<=0;groups0[i]<=0;groups1[i]<=0;slots0[i]<=0;slots1[i]<=0;count[i]<=0;end
            // group_valid guards synchronous token RAM; its payload has no reset.
        end else begin
            parent_result<=0;
            if(voice_valid)group_valid[voice_group]<=0;
            if(in_finger_valid&&state!=IDLE)protocol_error<=1;
            case(state)
                IDLE:begin
                    if(in_finger_valid&&in_finger_cmd==0&&in_finger_id<NF&&count[in_finger_id]!=0)begin
                        bind_id<=in_finger_id;bind_position<=in_finger_position;bind_second<=0;state<=BIND;
                    end else if(parent_valid&&parent_ready)begin
                        instance_hold<=parent_instance;on_hold<=parent_on;note_hold<=parent_note;vel_hold<=parent_vel;any_success<=0;
                        if(parent_instance[4:0]>=NF)begin todo<=0;state<=FINISH;protocol_error<=1;end
                        else if(parent_on)begin
                            if(selected_count==0||selected_count>2)begin todo<=0;state<=FINISH;selection_error<=1;end
                            else begin
                                masks[parent_instance[4:0]]<=selection;generations[parent_instance[4:0]]<=parent_instance[12:5];
                                count[parent_instance[4:0]]<=0;todo<=selection;mask_hold<=selection;state<=PICK;
                            end
                        end else begin
                            todo<=generations[parent_instance[4:0]]==parent_instance[12:5]?masks[parent_instance[4:0]]:4'b0;
                            state<=PICK;
                        end
                    end
                end
                PICK:if(todo==0)state<=FINISH;else begin slot_hold<=next_slot;todo[next_slot]<=0;state<=SEND;end
                SEND:if(child_ready)state<=WAIT_RESULT;
                WAIT_RESULT:if(result_valid&&result_owned)begin
                    if(result_instance!=child_instance||result_on!=on_hold)protocol_error<=1;
                    else begin
                        if(result_success)begin
                            any_success<=1;
                            if(on_hold)begin
                                group_valid[result_group]<=1;group_token[result_group]<=child_instance;
                                if(count[instance_hold[4:0]]==0)begin groups0[instance_hold[4:0]]<=result_group;slots0[instance_hold[4:0]]<=slot_hold;end
                                else begin groups1[instance_hold[4:0]]<=result_group;slots1[instance_hold[4:0]]<=slot_hold;end
                                count[instance_hold[4:0]]<=count[instance_hold[4:0]]+1'b1;
                            end
                        end
                        state<=PICK;
                    end
                end
                FINISH:begin
                    parent_result<=1;parent_success<=any_success;parent_result_on<=on_hold;parent_result_instance<=instance_hold;state<=IDLE;
                end
                BIND:if(!bind_second&&count[bind_id]>1)bind_second<=1;else state<=IDLE;
                default:state<=IDLE;
            endcase
        end
    end
endmodule
