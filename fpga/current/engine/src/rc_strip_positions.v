// Three positive deltas -> weighted centroid 0..256. Serial division is shared
// by all strips. Thresholds/debounce are replaceable sensor test parameters.
// Invalid nodes are reported and preserve the previous contact; upstream must
// decide the eventual sensor-failure release policy before physical deployment.
//
// `area` = d0+d1+d2, the raw contact-area proxy. It is the source for both
// velocity (D1: area at note-on) and aftertouch vibrato (D2: area drift after
// note-on), so it must leave this module -- the centroid alone cannot express
// either. Width is CW+2 because the sum of three CW-bit terms needs two extra
// bits. It is forced to zero on a bad read or during calibration: a failed
// node must not look like a light touch.
//
// 【八度档 5 格：单电极直读】
//   音域条（octave strip）的 5 个格子每格只有【一个】电极 —— 它不需要位置，
//   只需要"这一格被按住了"，所以不走三电极重心，只在本模块每帧末尾多读
//   NSINGLE 个节点，逐个与阈值比。
//   为什么要并进本模块、而不是另起一个读者：rc_delta_store 的读口只有一路
//   （read_address / read_delta / read_valid），多一个读者就要加仲裁，而
//   仲裁的失败模式（读到别的帧、读到半更新的行）恰恰最难在仿真里看出来。
//   并进来之后仍然只有一个读者、一帧一次、顺序确定。
//   去抖不在这里做：下游 strip_ctrl 要求按住 >= HOLD_MS(100 ms) 才生效，
//   已经比这里强得多；再加一层反而会让"按住 100 ms"变成 100 ms + N 帧。
//   节点号 = SINGLE_BASE + 格号（升序），见 D-023 的电极分配表。
module rc_strip_positions #(
    parameter integer STRIPS=25,CW=12,CONFIRM_FRAMES=2,
    parameter [STRIPS*21-1:0] NODE_MAP=0,
    parameter integer NSINGLE=5,
    parameter [6:0] SINGLE_BASE=7'd75
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
    output reg [STRIPS*(CW+2)-1:0] area,
    output reg [NSINGLE-1:0] single_touch,
    output reg [31:0] report_sequence,
    output reg report_calibration
);
    localparam IDLE=0,REQ=1,WAIT=2,TAKE=3,CALC=4,DIVIDE=5,STORE=6,PUBLISH=7;
    localparam SREQ=8,SWAIT=9,STAKE=10;
    reg [3:0] state;
    localparam SW=(STRIPS<2)?1:$clog2(STRIPS);
    reg [SW-1:0] strip;
    reg [1:0] electrode;
    localparam SGW=(NSINGLE<2)?1:$clog2(NSINGLE);
    reg [SGW-1:0] single;
    reg [NSINGLE-1:0] next_single;
    reg [CW-1:0] d0,d1,d2;
    reg good,cal_q;
    reg [STRIPS-1:0] next_contact,next_invalid;
    reg [STRIPS*9-1:0] next_position;
    reg [STRIPS*(CW+2)-1:0] next_area;
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
            next_contact<=0;next_invalid<=0;next_position<=0;next_area<=0;contact<=0;invalid<=0;position<=0;area<=0;report_valid<=0;
            on_q<=0;off_q<=0;denom<=0;dividend<=0;quotient<=0;remainder<=0;bits_left<=0;report_sequence<=0;report_calibration<=0;
            single<=0;next_single<=0;single_touch<=0;
            for(i=0;i<STRIPS;i=i+1)confirm[i]<=0;
        end else case(state)
            IDLE:if(frame_valid)begin
                strip<=0;electrode<=0;good<=1;cal_q<=frame_calibration;
                next_contact<=contact;next_position<=position;next_area<=area;next_invalid<=0;
                next_single<=single_touch;single<=0;
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
                // Area is updated every frame, unlike position which holds on a
                // skipped divide. A bad node or a calibration frame reports 0 so
                // upstream cannot read a stale or bogus touch size.
                next_area[strip*(CW+2) +: (CW+2)]<=(!good||cal_q)?{(CW+2){1'b0}}:sum;
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
            STORE:if(strip==STRIPS-1)begin single<=0;state<=SREQ;end
                else begin strip<=strip+1'b1;electrode<=0;good<=1;state<=REQ;end
            // 八度档：逐格读一个节点，与阈值比（带滞回），不做重心、不做帧确认
            SREQ:begin read_address<=SINGLE_BASE+{{(7-SGW){1'b0}},single};state<=SWAIT;end
            SWAIT:state<=STAKE;
            STAKE:begin
                // 读坏或标定帧一律报"没按"，避免坏节点被当成一直按住
                next_single[single]<=(!read_valid||cal_q)?1'b0:
                                     ({1'b0,read_delta}>=(single_touch[single]?off_q:on_q));
                if(single==NSINGLE-1)state<=PUBLISH;
                else begin single<=single+1'b1;state<=SREQ;end
            end
            PUBLISH:begin
                if(!report_valid)begin contact<=next_contact;invalid<=next_invalid;position<=next_position;area<=next_area;
                    single_touch<=next_single;report_valid<=1;end
                else if(report_ready)begin report_valid<=0;state<=IDLE;end
            end
        endcase
    end
endmodule
