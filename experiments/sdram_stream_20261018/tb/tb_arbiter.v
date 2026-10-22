`timescale 1ns/1ps
module tb_arbiter;
 parameter AW=3,SEED=1,CYCLES=160000;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,rc=0,pc=0,rr=0,pr=0,pause=0;
 reg [7:0] latency=0;reg ri=1,pi=1;
 reg [15:0] rd=16'h1000,pd=16'h8000;
 wire rcr,pcr,rcd,pcd,rcb,pcb,rir,pir,rov,pov,mv,mr,mw,sv,sr,busy;
 wire [15:0] rod,pod,md,sd;wire [21:0] ma;wire [AW:0] rl,pl;
 pcm_sdram_arbiter #(.AW(AW)) dut(.clk(clk),.rst_n(rst_n),
 .rec_clear_valid(rc),.play_clear_valid(pc),.rec_clear_ready(rcr),.play_clear_ready(pcr),
 .rec_clear_done(rcd),.play_clear_done(pcd),.rec_clearing(rcb),.play_clearing(pcb),
 .rec_in_valid(ri),.rec_in_ready(rir),.rec_in_data(rd),.rec_out_valid(rov),.rec_out_ready(rr),.rec_out_data(rod),
 .play_in_valid(pi),.play_in_ready(pir),.play_in_data(pd),.play_out_valid(pov),.play_out_ready(pr),.play_out_data(pod),
 .rec_level(rl),.play_level(pl),.mem_req_valid(mv),.mem_req_ready(mr),.mem_req_write(mw),
 .mem_req_addr(ma),.mem_req_data(md),.mem_rsp_valid(sv),.mem_rsp_ready(sr),.mem_rsp_data(sd),.busy(busy));
 memory_backend_model #(.AW(AW)) memory(.clk(clk),.rst_n(rst_n),.pause(pause),.latency(latency),
 .req_valid(mv),.req_ready(mr),.req_write(mw),.req_addr(ma),.req_data(md),.rsp_valid(sv),.rsp_ready(sr),.rsp_data(sd));
 integer cycle=0,fd;reg [31:0] random_state=SEED;reg draining=0;
 reg held=0;reg [38:0] old_cmd;reg rh=0,ph=0;reg [15:0] old_r,old_p;
 initial begin
  fd=$fopen("trace-arbiter.txt","w");
  repeat(3)@(negedge clk);rst_n=1;
  repeat(CYCLES)begin
   @(negedge clk);random_state=random_state*1664525+1013904223;
   latency=random_state[13:8]%19;pause=random_state[3:0]<5 || cycle%4096<93;
   rr=random_state[4] && !(cycle%4000<150);pr=random_state[5] && !(cycle%5000<210);
   rc=rcr && (cycle%701==0 || (mv&&!mr&&cycle%113==0) || (sv&&cycle%313==0));
   pc=pcr && (cycle%997==0 || (busy&&cycle%137==0));
   if(cycle%20003==19900)rst_n=0;else rst_n=1;
  end
  @(negedge clk);draining=1;ri=0;pi=0;rc=0;pc=0;pause=0;rr=1;pr=1;latency=0;rst_n=1;
  repeat(10000)@(negedge clk);
  if(rl!=0||pl!=0||rov||pov||busy)$fatal(1,"drain incomplete");
  $display("PASS arbiter AW=%0d seed=%0d cycles=%0d drained",AW,SEED,cycle);$fclose(fd);$finish;
 end
 always @(posedge clk)begin
  cycle=cycle+1;
  if(!rst_n || !busy || rc&&rcr || pc&&pcr || rcd || pcd || ri&&rir || rov&&rr || pi&&pir || pov&&pr || mv&&mr || sv&&sr || draining && cycle%1000==0)
  $fdisplay(fd,"%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
   cycle,rst_n,rc&&rcr,pc&&pcr,rcd,pcd,rcb,pcb,ri&&rir,rd,rov&&rr,rod,pi&&pir,pd,pov&&pr,pod,
   mv,mr,mw,ma,md,sv,sr,rl,pl,rov,rr,pov,pr,busy,ri,pi);
  if(!rst_n)begin rd<=16'h1000;pd<=16'h8000;held=0;rh=0;ph=0;end
  else begin
   if(ri&&rir)rd<=rd+1'b1;if(pi&&pir)pd<=pd+7;
   if(rl>(1<<AW)||pl>(1<<AW))$fatal(1,"ring capacity");
   if(held && (!mv || {mw,ma,md}!==old_cmd))$fatal(1,"memory command changed under stall");
   if(rh && !rcb && (!rov||rod!==old_r))$fatal(1,"record head unstable");
   if(ph && !pcb && (!pov||pod!==old_p))$fatal(1,"play head unstable");
   if(rcb&&(rir||rov))$fatal(1,"record accepted while clearing");
   if(pcb&&(pir||pov))$fatal(1,"play accepted while clearing");
   held=mv&&!mr;old_cmd={mw,ma,md};rh=rov&&!rr;old_r=rod;ph=pov&&!pr;old_p=pod;
  end
 end
 initial begin #5000000;$fatal(1,"watchdog");end
endmodule
