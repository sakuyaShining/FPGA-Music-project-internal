// Three positive deltas -> weighted centroid 0..256. Serial division is shared
// by all strips. Thresholds/debounce are replaceable sensor test parameters.
// Invalid nodes are reported and preserve the previous contact; upstream must
// decide the eventual sensor-failure release policy before physical deployment.
module rc_strip_positions #(
    parameter integer STRIPS=26,CW=12,CONFIRM_FRAMES=2,
    parameter [STRIPS*21-1:0] NODE_MAP=0
)(
    input wire clk,rst_n,frame_valid,
    output wire frame_ready,
    input wire [31:0] frame_sequence,
    input wire frame_calibration,
    output reg [6:0] read_address,
    input wire [CW-1:0] read_delta,
    input wire read_valid,
    input wire [CW+1:0] threshold_on,threshold_off,
    output reg report_valid,
    input wire report_ready,
    output reg [STRIPS-1:0] contact,invalid,
    output reg [STRIPS*9-1:0] position,
    output reg [31:0] report_sequence,
    output reg report_calibration
);
    localparam IDLE=0,REQ=1,WAIT=2,TAKE=3,CALC=4,DIVIDE=5,STORE=6,PUBLISH=7;
    reg [2:0] state;
    localparam SW=(STRIPS<2)?1:$clog2(STRIPS);
    reg [SW-1:0] strip;
    reg [1:0] electrode;
    reg [CW-1:0] d0,d1,d2;
    reg good,cal_q;
    reg [STRIPS-1:0] next_contact,next_invalid;
    reg [STRIPS*9-1:0] next_position;
    localparam DBW=(CONFIRM_FRAMES<2)?1:$clog2(CONFIRM_FRAMES+1);
    reg [DBW-1:0] confirm[0:STRIPS-1];
    reg [CW+1:0] on_q,off_q,denom;
    localparam NW=CW+9;
    reg [NW-1:0] dividend,quotient;
    reg [CW+2:0] remainder;
    reg [4:0] bits_left;
    wire [CW+1:0] sum={2'b0,d0}+{2'b0,d1}+{2'b0,d2};
    wire [CW+1:0] weighted={2'b0,d1}+{1'b0,d2,1'b0};
    wire [CW+3:0] trial={remainder,dividend[NW-1]};
    wire take_bit=trial>={2'b0,denom};
    wire [CW+3:0] reduced=take_bit?(trial-denom):trial;
    wire want_contact=sum>=(contact[strip]?off_q:on_q);
    assign frame_ready=state==PUBLISH&&report_valid&&report_ready;
    integer i;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;strip<=0;electrode<=0;read_address<=0;d0<=0;d1<=0;d2<=0;good<=0;cal_q<=0;
            next_contact<=0;next_invalid<=0;next_position<=0;contact<=0;invalid<=0;position<=0;report_valid<=0;
            on_q<=0;off_q<=0;denom<=0;dividend<=0;quotient<=0;remainder<=0;bits_left<=0;report_sequence<=0;report_calibration<=0;
            for(i=0;i<STRIPS;i=i+1)confirm[i]<=0;
        end else case(state)
            IDLE:if(frame_valid)begin
                strip<=0;electrode<=0;good<=1;cal_q<=frame_calibration;
                next_contact<=contact;next_position<=position;next_invalid<=0;
                on_q<=threshold_on;off_q<=(threshold_off>threshold_on)?threshold_on:threshold_off;
                report_sequence<=frame_sequence;report_calibration<=frame_calibration;state<=REQ;
            end
            REQ:begin read_address<=NODE_MAP[(strip*3+electrode)*7+:7];state<=WAIT;end
            WAIT:state<=TAKE;
            TAKE:begin
                good<=good&&read_valid;
                case(electrode)0:d0<=read_delta;1:d1<=read_delta;2:d2<=read_delta;endcase
                if(electrode==2)state<=CALC;
                else begin electrode<=electrode+1'b1;state<=REQ;end
            end
            CALC:begin
                next_invalid[strip]<=!good;
                if(cal_q)begin next_contact[strip]<=0;confirm[strip]<=0;end
                else if(!good)confirm[strip]<=0;
                else if(want_contact==contact[strip])confirm[strip]<=0;
                else if(confirm[strip]==CONFIRM_FRAMES-1)begin next_contact[strip]<=want_contact;confirm[strip]<=0;end
                else confirm[strip]<=confirm[strip]+1'b1;
                if(!good||sum==0||cal_q)state<=STORE;
                else begin
                    // NW=CW+9 accommodates (d1+2*d2)*128 without overflow.
                    dividend<={weighted,7'b0};denom<=sum;quotient<=0;remainder<=0;bits_left<=NW;state<=DIVIDE;
                end
            end
            DIVIDE:begin
                remainder<=reduced[CW+2:0]; // reduced < denom, high bit is zero.
                dividend<=dividend<<1;quotient<={quotient[NW-2:0],take_bit};
                if(bits_left==1)begin
                    next_position[strip*9+:9]<={quotient[7:0],take_bit};state<=STORE;
                end else bits_left<=bits_left-1'b1;
            end
            STORE:if(strip==STRIPS-1)begin state<=PUBLISH;end
                else begin strip<=strip+1'b1;electrode<=0;good<=1;state<=REQ;end
            PUBLISH:begin
                if(!report_valid)begin contact<=next_contact;invalid<=next_invalid;position<=next_position;report_valid<=1;end
                else if(report_ready)begin report_valid<=0;state<=IDLE;end
            end
        endcase
    end
endmodule
