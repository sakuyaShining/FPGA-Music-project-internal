// Stage80 logical SDRAM candidate, 27MHz, 4 banks x 2048 rows x 256 x32.
// One 16-bit transaction at a time; explicit precharge, BL1 and CAS3.
// Timing values below are conservative candidates, NOT board qualification.
// Response backpressure never blocks auto refresh. Reset aborts the session;
// data retention across reinitialization is not promised. No CDC support.
module sdram_word_controller #(parameter INIT_CYCLES=5400,REF_PERIOD=384)(
 input wire clk,rst_n,
 input wire req_valid,output wire req_ready,input wire req_write,
 input wire [21:0] req_addr,input wire [15:0] req_data,
 output reg rsp_valid,input wire rsp_ready,output reg [15:0] rsp_data,
 output reg init_done,
 output wire sd_clk,sd_cke,sd_cs_n,
 output reg sd_ras_n,sd_cas_n,sd_we_n,
 output reg [10:0] sd_addr,output reg [1:0] sd_bank,
 output reg [3:0] sd_dqm,inout wire [31:0] sd_dq
);
 localparam POWER=0,IPRE=1,IREF1=2,IREF2=3,MODE=4,IDLE=5,
            ACT=6,READ=7,WRITE=8,CAPTURE=9,PRE=10,DONE=11,REFRESH=12,WAITING=13;
 localparam TRP=3,TRCD=2,TWR=3,TRFC=9,TMRD=3,CL=3;
 localparam CW=$clog2(INIT_CYCLES+1),RW=$clog2(REF_PERIOD+1);
 reg [3:0] state,next_state;
 reg [CW-1:0] delay_count;
 reg [RW-1:0] ref_count;
 reg [21:0] address;
 reg [15:0] write_data;
 reg is_write;
 wire refresh_due=ref_count>=REF_PERIOD;
 assign req_ready=rst_n && init_done && state==IDLE && !rsp_valid && !refresh_due;
 assign sd_clk=~clk;
 assign sd_cke=1'b1;
 assign sd_cs_n=1'b0;
 assign sd_dq=(rst_n && state==WRITE)?{write_data,write_data}:32'bz;
 always @*begin
  {sd_ras_n,sd_cas_n,sd_we_n}=3'b111;
  sd_addr=0;sd_bank=address[21:20];sd_dqm=0;
  if(rst_n)case(state)
   IPRE,PRE:begin {sd_ras_n,sd_cas_n,sd_we_n}=3'b010;sd_addr=11'h400;end
   IREF1,IREF2,REFRESH:{sd_ras_n,sd_cas_n,sd_we_n}=3'b001;
   MODE:begin {sd_ras_n,sd_cas_n,sd_we_n}=3'b000;sd_addr=11'h030;sd_bank=0;end
   ACT:begin {sd_ras_n,sd_cas_n,sd_we_n}=3'b011;sd_addr=address[19:9];end
   READ:begin {sd_ras_n,sd_cas_n,sd_we_n}=3'b101;sd_addr={3'b000,address[8:1]};end
   WRITE:begin
    {sd_ras_n,sd_cas_n,sd_we_n}=3'b100;sd_addr={3'b000,address[8:1]};
    sd_dqm=address[0]?4'b0011:4'b1100;
   end
   default:;
  endcase
 end
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=POWER;next_state<=IDLE;delay_count<=INIT_CYCLES-1;
   ref_count<=0;init_done<=0;rsp_valid<=0;rsp_data<=0;
   address<=0;write_data<=0;is_write<=0;
  end else begin
   if(!init_done)ref_count<=0;
   else if(state==REFRESH)ref_count<=0;
   else if(!refresh_due)ref_count<=ref_count+1'b1;
   if(rsp_valid && rsp_ready)rsp_valid<=0;
   case(state)
    POWER:if(delay_count==0)state<=IPRE;else delay_count<=delay_count-1'b1;
    IPRE:begin state<=WAITING;delay_count<=TRP-2;next_state<=IREF1;end
    IREF1:begin state<=WAITING;delay_count<=TRFC-2;next_state<=IREF2;end
    IREF2:begin state<=WAITING;delay_count<=TRFC-2;next_state<=MODE;end
    MODE:begin state<=WAITING;delay_count<=TMRD-2;next_state<=IDLE;end
    WAITING:if(delay_count==0)begin
     state<=next_state;
     if(next_state==IDLE && !init_done)init_done<=1;
    end else delay_count<=delay_count-1'b1;
    IDLE:if(refresh_due)state<=REFRESH;
     else if(req_valid && req_ready)begin address<=req_addr;write_data<=req_data;is_write<=req_write;state<=ACT;end
    ACT:begin state<=WAITING;delay_count<=TRCD-2;next_state<=is_write?WRITE:READ;end
    WRITE:begin state<=WAITING;delay_count<=TWR-2;next_state<=PRE;rsp_data<=0;end
    READ:begin state<=WAITING;delay_count<=CL-2;next_state<=CAPTURE;end
    CAPTURE:begin rsp_data<=address[0]?sd_dq[31:16]:sd_dq[15:0];state<=PRE;end
    PRE:begin state<=WAITING;delay_count<=TRP-2;next_state<=DONE;end
    DONE:begin rsp_valid<=1;state<=IDLE;end
    REFRESH:begin state<=WAITING;delay_count<=TRFC-2;next_state<=IDLE;end
    default:begin state<=POWER;init_done<=0;rsp_valid<=0;delay_count<=INIT_CYCLES-1;end
   endcase
  end
 end
endmodule
