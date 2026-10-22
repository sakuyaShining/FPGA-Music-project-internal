// One contact per strip. Frames are immutable while being consumed. A dedicated
// event port supplies acceptance AND instance-tagged allocation completion.
// Movement never creates an on event. Sensor-fault limits are prototype knobs.
module left_contact_bridge_reference #(
    parameter integer NF=26,BAD_FRAMES=8,FRAME_TIMEOUT=2700000,LINK_TIMEOUT=8192
)(
    input wire clk,rst_n,frame_valid,
    output wire frame_ready,
    input wire [NF-1:0] contact,invalid,
    input wire [NF*9-1:0] position,
    input wire [31:0] frame_sequence,
    input wire frame_calibration,
    input wire [NF*7-1:0] note_map,
    input wire [3:0] velocity,
    output wire own_valid,
    input wire own_ready,
    output reg own_on,
    output reg [6:0] own_note,
    output reg [3:0] own_vel,
    output reg [12:0] own_instance,
    input wire result_valid,result_owned,result_on,result_success,
    input wire [12:0] result_instance,
    input wire [4:0] result_group,
    input wire voice_valid,voice_on,
    input wire [4:0] voice_group,
    output wire finger_valid,
    output wire [1:0] finger_cmd,
    output wire [4:0] finger_id,finger_group,
    output wire signed [11:0] finger_position,
    output reg frame_error,link_error,sensor_error,watchdog_error,
    output wire [NF-1:0] bound_contacts,blocked_contacts
);
    localparam IDLE=0,SCAN=1,SEND=2,REPLY=3,BIND_WAIT=4,BIND=5,MOVE=6,RELEASE=7,NEXT=8;
    reg [3:0] state;
    reg [4:0] index;
    reg [NF-1:0] seen,bound,blocked,touch_q,invalid_q;
    reg [NF*9-1:0] pos_q;
    reg [NF*7-1:0] notes_q;
    reg [3:0] vel_q;
    reg force_q,cal_q,sequence_known,stale_pending;
    reg [31:0] last_sequence;
    reg [7:0] generation[0:NF-1];
    reg [6:0] sounding_note[0:NF-1];
    reg [4:0] group[0:NF-1];
    reg [8:0] last_position[0:NF-1];
    localparam BW=(BAD_FRAMES<2)?1:$clog2(BAD_FRAMES+1);
    reg [BW-1:0] bad_count[0:NF-1];
    localparam FW=(FRAME_TIMEOUT<2)?1:$clog2(FRAME_TIMEOUT+1);
    localparam LW=(LINK_TIMEOUT<2)?1:$clog2(LINK_TIMEOUT+1);
    reg [FW-1:0] frame_timer;
    reg [LW-1:0] link_timer;
    wire [8:0] current_position=pos_q[index*9+:9];
    wire bad_expired=invalid_q[index]&&bad_count[index]>=BAD_FRAMES-1;
    wire force_release=force_q||cal_q||bad_expired;
    assign frame_ready=state==IDLE&&!stale_pending;
    assign own_valid=state==SEND;
    assign finger_valid=state==BIND||state==MOVE||state==RELEASE;
    assign finger_cmd=(state==BIND)?2'd0:(state==MOVE)?2'd1:2'd2;
    assign finger_id=index;
    assign finger_group=group[index];
    assign finger_position=$signed({3'b000,current_position});
    assign bound_contacts=bound;
    assign blocked_contacts=blocked;
    integer i;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;index<=0;seen<=0;bound<=0;blocked<=0;touch_q<=0;invalid_q<=0;pos_q<=0;notes_q<=0;vel_q<=0;force_q<=0;cal_q<=0;
            sequence_known<=0;stale_pending<=0;last_sequence<=0;frame_timer<=0;link_timer<=0;
            own_on<=0;own_note<=0;own_vel<=0;own_instance<=0;frame_error<=0;link_error<=0;sensor_error<=0;watchdog_error<=0;
            for(i=0;i<NF;i=i+1)begin generation[i]<=0;sounding_note[i]<=0;group[i]<=0;last_position[i]<=0;bad_count[i]<=0;end
        end else begin
            // Allocator reuse wins over old movement. finger_pitch independently
            // enforces the same rule, so in-flight old commands cannot take over.
            if(voice_valid&&voice_on)
                for(i=0;i<NF;i=i+1)if(bound[i]&&group[i]==voice_group)bound[i]<=0;
            if(frame_timer<FRAME_TIMEOUT)frame_timer<=frame_timer+1'b1;
            if(frame_timer==FRAME_TIMEOUT-1&&(|seen))begin stale_pending<=1;watchdog_error<=1;end
            if(state==SEND||state==REPLY)begin
                if(link_timer<LINK_TIMEOUT)link_timer<=link_timer+1'b1;
                if(link_timer==LINK_TIMEOUT-1)link_error<=1;
                // Keep an accepted request outstanding: never guess its group
                // or recycle the instance while its completion is unresolved.
            end else link_timer<=0;
            case(state)
                IDLE:begin
                    if(stale_pending)begin
                        touch_q<=0;invalid_q<=0;force_q<=1;cal_q<=0;index<=0;
                        blocked<=blocked|seen;stale_pending<=0;state<=SCAN;
                    end else if(frame_valid)begin
                        last_sequence<=frame_sequence;sequence_known<=1;frame_timer<=0;
                        pos_q<=position;notes_q<=note_map;vel_q<=velocity;index<=0;
                        if(sequence_known&&frame_sequence!=last_sequence+1'b1)begin
                            frame_error<=1;force_q<=1;cal_q<=0;touch_q<=0;invalid_q<=0;blocked<=blocked|seen;
                        end else begin force_q<=0;cal_q<=frame_calibration;touch_q<=contact;invalid_q<=invalid;end
                        state<=SCAN;
                    end
                end
                SCAN:begin
                    if(invalid_q[index])begin
                        if(bad_count[index]<BAD_FRAMES)bad_count[index]<=bad_count[index]+1'b1;
                        if(bad_expired)begin sensor_error<=1;blocked[index]<=1;end
                    end else bad_count[index]<=0;
                    if(force_release||(!invalid_q[index]&&!touch_q[index]))begin
                        if(force_release&&seen[index])blocked[index]<=1;
                        else if(!invalid_q[index]&&!touch_q[index])blocked[index]<=0;
                        if(seen[index]&&bound[index])begin
                            own_on<=0;own_note<=sounding_note[index];own_vel<=0;
                            own_instance<={generation[index],index};state<=SEND;
                        end else begin seen[index]<=0;state<=bound[index]?RELEASE:NEXT;end
                    end else if(invalid_q[index]||blocked[index])state<=NEXT;
                    else if(!seen[index])begin
                        generation[index]<=generation[index]+1'b1;
                        own_instance<={generation[index]+8'd1,index};own_on<=1;
                        own_note<=notes_q[index*7+:7];sounding_note[index]<=notes_q[index*7+:7];own_vel<=vel_q;
                        seen[index]<=1;state<=SEND;
                    end else if(bound[index]&&current_position!=last_position[index])state<=MOVE;
                    else state<=NEXT;
                end
                SEND:if(own_ready)state<=REPLY;
                REPLY:if(result_valid&&result_owned)begin
                    if(result_instance!=own_instance||result_on!=own_on)link_error<=1;
                    else if(own_on&&result_success)begin group[index]<=result_group;state<=BIND_WAIT;end
                    else begin
                        seen[index]<=0;bound[index]<=0;
                        if(own_on&&!result_success)blocked[index]<=1;
                        state<=RELEASE;
                    end
                end
                // Allow gact_q and allocator reuse notification to settle before
                // sending bind; binding on the notification clock is rejected.
                BIND_WAIT:state<=BIND;
                BIND:begin bound[index]<=1;last_position[index]<=current_position;state<=NEXT;end
                MOVE:begin last_position[index]<=current_position;state<=NEXT;end
                RELEASE:begin bound[index]<=0;state<=NEXT;end
                NEXT:if(index==NF-1)state<=IDLE;else begin index<=index+1'b1;state<=SCAN;end
                default:state<=IDLE;
            endcase
        end
    end
endmodule
