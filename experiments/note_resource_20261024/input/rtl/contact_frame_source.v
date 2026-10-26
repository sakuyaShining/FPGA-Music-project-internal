module contact_frame_source #(
    parameter integer NF=26,BAD_FRAMES=8,FRAME_TIMEOUT=2700000,LINK_TIMEOUT=8192
)(
    input wire clk,rst_n,frame_valid,
    output wire frame_ready,
    input wire [NF-1:0] contact,invalid,
    input wire [NF*9-1:0] position,
    input wire [NF*7-1:0] note_map,
    input wire [31:0] frame_sequence,
    input wire frame_calibration,
    input wire [7:0] velocity,
    input wire signed [17:0] glide,
    input wire [3:0] layer_selection,
    input wire link_pending,
    output wire on_valid,
    input wire on_ready,
    output wire [4:0] on_contact,
    output wire [7:0] on_generation,on_velocity,
    output wire [6:0] on_note,
    output wire signed [17:0] on_glide,
    output wire [3:0] on_layers,
    output wire signed [11:0] on_position,
    output wire release_valid,
    input wire release_ready,
    output reg [31:0] release_token,
    output wire move_valid,
    output reg [31:0] move_token,
    output wire signed [11:0] move_position,
    output wire [4:0] query_contact,
    input wire query_held,
    input wire [31:0] query_token,query_groups,
    output reg frame_error,link_error,sensor_error,watchdog_error,admission_error,
    output wire [NF-1:0] seen_contacts,blocked_contacts
);
    localparam IDLE=0,SCAN=1,ON=2,RELEASE=3,MOVE=4,NEXT=5;
    localparam BW=BAD_FRAMES<2?1:$clog2(BAD_FRAMES+1);
    localparam FW=FRAME_TIMEOUT<2?1:$clog2(FRAME_TIMEOUT+1);
    localparam LW=LINK_TIMEOUT<2?1:$clog2(LINK_TIMEOUT+1);
    reg [2:0] state;
    reg [4:0] index;
    reg [NF-1:0] seen,blocked,touch_q,invalid_q;
    reg [NF*9-1:0] position_q;
    reg [NF*7-1:0] notes_q;
    reg [7:0] velocity_q;
    reg signed [17:0] glide_q;
    reg [3:0] layers_q;
    reg [7:0] generation[0:NF-1];
    reg [8:0] last_position[0:NF-1];
    reg [BW-1:0] bad_count[0:NF-1];
    reg sequence_known,force_q,calibration_q,stale_pending;
    reg [31:0] last_sequence;
    reg [FW-1:0] frame_timer;
    reg [LW-1:0] link_timer;
    wire [8:0] current_position=position_q[index*9+:9];
    wire bad_expired=invalid_q[index]&&bad_count[index]>=BAD_FRAMES-1;
    wire force_release=force_q||calibration_q||bad_expired;
    assign frame_ready=rst_n&&state==IDLE&&!stale_pending;
    assign on_valid=rst_n&&state==ON;
    assign on_contact=index;
    assign on_generation=generation[index];
    assign on_note=notes_q[index*7+:7];
    assign on_velocity=velocity_q;
    assign on_glide=glide_q;
    assign on_layers=layers_q;
    assign on_position=$signed({3'b000,current_position});
    assign release_valid=rst_n&&state==RELEASE;
    assign move_valid=rst_n&&state==MOVE;
    assign move_position=$signed({3'b000,current_position});
    assign query_contact=index;
    assign seen_contacts=seen;
    assign blocked_contacts=blocked;
    integer row;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;index<=0;seen<=0;blocked<=0;touch_q<=0;invalid_q<=0;
            position_q<=0;notes_q<=0;velocity_q<=0;glide_q<=0;layers_q<=0;
            sequence_known<=0;last_sequence<=0;force_q<=0;calibration_q<=0;stale_pending<=0;
            frame_timer<=0;link_timer<=0;release_token<=0;move_token<=0;
            frame_error<=0;link_error<=0;sensor_error<=0;watchdog_error<=0;admission_error<=0;
            for(row=0;row<NF;row=row+1)begin generation[row]<=0;last_position[row]<=0;bad_count[row]<=0;end
        end else begin
            if(frame_timer<FRAME_TIMEOUT)frame_timer<=frame_timer+1'b1;
            if(frame_timer==FRAME_TIMEOUT-1&&(|seen))begin stale_pending<=1;watchdog_error<=1;end
            if(state==ON||state==RELEASE||link_pending)begin
                if(link_timer<LINK_TIMEOUT)link_timer<=link_timer+1'b1;
                if(link_timer==LINK_TIMEOUT-1)link_error<=1;
            end else link_timer<=0;
            case(state)
                IDLE:begin
                    if(stale_pending)begin
                        index<=0;touch_q<=0;invalid_q<=0;force_q<=1;calibration_q<=0;
                        blocked<=blocked|seen;stale_pending<=0;state<=SCAN;
                    end else if(frame_valid&&frame_ready)begin
                        position_q<=position;notes_q<=note_map;velocity_q<=velocity;glide_q<=glide;layers_q<=layer_selection;
                        last_sequence<=frame_sequence;sequence_known<=1;frame_timer<=0;index<=0;
                        if(sequence_known&&frame_sequence!=last_sequence+1'b1)begin
                            frame_error<=1;force_q<=1;calibration_q<=0;touch_q<=0;invalid_q<=0;blocked<=blocked|seen;
                        end else begin force_q<=0;calibration_q<=frame_calibration;touch_q<=contact;invalid_q<=invalid;end
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
                        if(seen[index]&&query_held)begin
                            release_token<=query_token;state<=RELEASE;
                        end else begin seen[index]<=0;state<=NEXT;end
                    end else if(invalid_q[index]||blocked[index])state<=NEXT;
                    else if(!seen[index])begin
                        if(layers_q==0)begin seen[index]<=1;admission_error<=1;state<=NEXT;end
                        else begin generation[index]<=generation[index]+8'd1;state<=ON;end
                    end else if(query_held&&query_groups!=0&&current_position!=last_position[index])begin
                        move_token<=query_token;state<=MOVE;
                    end else state<=NEXT;
                end
                ON:if(on_ready)begin seen[index]<=1;last_position[index]<=current_position;state<=NEXT;end
                RELEASE:if(release_ready)begin seen[index]<=0;state<=NEXT;end
                MOVE:begin last_position[index]<=current_position;state<=NEXT;end
                NEXT:if(index==NF-1)state<=IDLE;else begin index<=index+5'd1;state<=SCAN;end
                default:state<=IDLE;
            endcase
        end
    end
endmodule
