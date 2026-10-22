// Transport only, all ports synchronous to clk. No musical start/stop policy.
// Two disjoint power-of-two rings: rec=[0,2**AW), play=[2**AW,2**(AW+1)).
// One memory request in flight. Upstream samples pop on request acceptance;
// committed ring levels/pointers change on response, never on mere selection.
// Clear cancels that direction's unconsumed head; held memory requests remain
// stable and drain before clear_done. No new session data is accepted meanwhile.
module pcm_sdram_arbiter #(parameter AW=17)(
 input wire clk,rst_n,
 input wire rec_clear_valid,play_clear_valid,
 output wire rec_clear_ready,play_clear_ready,rec_clearing,play_clearing,
 output reg rec_clear_done,play_clear_done,
 input wire rec_in_valid,output wire rec_in_ready,input wire [15:0] rec_in_data,
 output wire rec_out_valid,input wire rec_out_ready,output reg [15:0] rec_out_data,
 input wire play_in_valid,output wire play_in_ready,input wire [15:0] play_in_data,
 output wire play_out_valid,input wire play_out_ready,output reg [15:0] play_out_data,
 output reg [AW:0] rec_level,play_level,
 output wire mem_req_valid,input wire mem_req_ready,output wire mem_req_write,
 output reg [21:0] mem_req_addr,output reg [15:0] mem_req_data,
 input wire mem_rsp_valid,output wire mem_rsp_ready,input wire [15:0] mem_rsp_data,
 output wire busy
);
 localparam [AW:0] CAP={1'b1,{AW{1'b0}}};
 localparam IDLE=0,ISSUE=1,WAIT_RSP=2;
 reg [1:0] state,kind,next_kind;
 reg [AW-1:0] rec_wp,rec_rp,play_wp,play_rp;
 reg rec_pending,play_pending;
 reg rec_head_valid,play_head_valid;
 assign rec_out_valid=rst_n && rec_head_valid && !rec_clearing;
 assign play_out_valid=rst_n && play_head_valid && !play_clearing;
 assign rec_clear_ready=rst_n && !rec_pending && !rec_clear_done;
 assign play_clear_ready=rst_n && !play_pending && !play_clear_done;
 wire rc=rec_clear_valid && rec_clear_ready;
 wire pc=play_clear_valid && play_clear_ready;
 assign rec_clearing=rec_pending || rc || rec_clear_done;
 assign play_clearing=play_pending || pc || play_clear_done;
 assign busy=state!=IDLE;
 wire is_rec=!kind[1];
 wire cancel=is_rec?rec_clearing:play_clearing;
 assign mem_req_valid=rst_n && state==ISSUE;
 assign mem_req_write=!kind[0];
 assign mem_rsp_ready=rst_n && state==WAIT_RSP;
 assign rec_in_ready=mem_req_valid && mem_req_ready && kind==0 && !rec_clearing;
 assign play_in_ready=mem_req_valid && mem_req_ready && kind==2 && !play_clearing;
 wire [3:0] eligible={
  !play_clearing && play_level!=0 && !play_head_valid,
  !play_clearing && play_level<CAP && play_in_valid,
  !rec_clearing && rec_level!=0 && !rec_head_valid,
  !rec_clearing && rec_level<CAP && rec_in_valid};
 reg selected;reg [1:0] choice;integer i;reg [1:0] candidate;
 always @*begin
  selected=0;choice=next_kind;candidate=0;
  for(i=0;i<4;i=i+1)begin
   candidate=next_kind+i;
   if(!selected && eligible[candidate])begin selected=1;choice=candidate;end
  end
 end
 // Valid heads may be discarded by an accepted clear. Normal backpressure
 // must hold them unchanged. Clear is an explicit cancellation boundary.
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin
   state<=IDLE;kind<=0;next_kind<=0;rec_wp<=0;rec_rp<=0;play_wp<=0;play_rp<=0;
   rec_level<=0;play_level<=0;rec_pending<=0;play_pending<=0;
   rec_clear_done<=0;play_clear_done<=0;rec_head_valid<=0;play_head_valid<=0;
   rec_out_data<=0;play_out_data<=0;mem_req_addr<=0;mem_req_data<=0;
  end else begin
   rec_clear_done<=0;play_clear_done<=0;
   if(rec_head_valid && rec_out_ready)rec_head_valid<=0;
   if(play_head_valid && play_out_ready)play_head_valid<=0;
   if(rc)begin rec_pending<=1;rec_head_valid<=0;end
   if(pc)begin play_pending<=1;play_head_valid<=0;end
   // Quiesce only the affected direction, even while the other has a request
   // in flight. Requests already presented for this direction cannot retract.
   if(rec_pending && (1'b1))begin
    rec_pending<=0;rec_wp<=0;rec_rp<=0;rec_level<=0;rec_head_valid<=0;rec_clear_done<=1;
   end
   if(play_pending && (state==IDLE || is_rec))begin
    play_pending<=0;play_wp<=0;play_rp<=0;play_level<=0;play_head_valid<=0;play_clear_done<=1;
   end
   case(state)
    IDLE:if(selected)begin
     kind<=choice;next_kind<=choice+1'b1;state<=ISSUE;
     case(choice)
      0:begin mem_req_addr<={{(22-AW){1'b0}},rec_wp};mem_req_data<=rec_in_data;end
      1:begin mem_req_addr<={{(22-AW){1'b0}},rec_rp};mem_req_data<=0;end
      2:begin mem_req_addr<=22'd1<<AW | play_wp;mem_req_data<=play_in_data;end
      3:begin mem_req_addr<=22'd1<<AW | play_rp;mem_req_data<=0;end
     endcase
    end
    ISSUE:if(mem_req_ready)state<=WAIT_RSP;
    WAIT_RSP:if(mem_rsp_valid)begin
     state<=IDLE;
     if(!cancel)case(kind)
      0:begin rec_wp<=rec_wp+1'b1;rec_level<=rec_level+1'b1;end
      1:begin rec_rp<=rec_rp+1'b1;rec_level<=rec_level-1'b1;rec_out_data<=mem_rsp_data;rec_head_valid<=1;end
      2:begin play_wp<=play_wp+1'b1;play_level<=play_level+1'b1;end
      3:begin play_rp<=play_rp+1'b1;play_level<=play_level-1'b1;play_out_data<=mem_rsp_data;play_head_valid<=1;end
     endcase
    end
    default:state<=IDLE;
   endcase
  end
 end
endmodule
