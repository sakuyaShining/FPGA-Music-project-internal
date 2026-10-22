`timescale 1ns/1ps
module tb_stream;
 parameter REAL_MEMORY=1;
 reg clk=0;always #18.5185 clk=~clk;
 reg rst_n=0,rc=0,pc=0,rec_enable=0,play_enable=0,feed=0,host_ready=1,pause=0;
 reg tick=0;reg [15:0] pcm=16'h4000,data=16'h9000;
 wire rcr,pcr,rcd,pcd,rcb,pcb,rv,fr,pv,over,under,miss,busy;
 wire [15:0] rd,pd,md,sd;wire [3:0] rl,pl;wire [6:0] rrl,prl;
 wire mv,mr,mw,sv,sr;wire [21:0] ma;
 integer cycle=0,fd;reg [31:0] random_state=31;reg feed_accepted=0;
 pcm_sdram_stream #(.FIFO_AW(3),.RING_AW(6)) dut(.clk(clk),.rst_n(rst_n),
 .rec_clear(rc),.play_clear(pc),.rec_clear_ready(rcr),.play_clear_ready(pcr),
 .rec_clear_done(rcd),.play_clear_done(pcd),.rec_clearing(rcb),.play_clearing(pcb),
 .rec_enable(rec_enable),.pcm_valid(tick),.pcm_data(pcm),.rec_valid(rv),.rec_ready(host_ready),.rec_data(rd),
 .rec_level(rl),.play_level(pl),.rec_ring_level(rrl),.play_ring_level(prl),.rec_overflow(over),
 .play_enable(play_enable),.sample_tick(tick),.feed_valid(feed),.feed_ready(fr),.feed_data(data),
 .play_valid(pv),.play_data(pd),.play_underflow(under),.play_miss(miss),
 .mem_req_valid(mv),.mem_req_ready(mr),.mem_req_write(mw),.mem_req_addr(ma),.mem_req_data(md),
 .mem_rsp_valid(sv),.mem_rsp_ready(sr),.mem_rsp_data(sd),.mem_busy(busy));
 generate if(REAL_MEMORY)begin:real_ram
  wire cr,initialized,sclk,cke,cs,ras,cas,we;wire [10:0] addr;wire [1:0] bank;wire [3:0] mask;wire [31:0] dq;
  integer refs,reads,writes,gap;
  assign mr=cr&&!pause;
  sdram_word_controller controller(.clk(clk),.rst_n(rst_n),
   .req_valid(mv&&!pause),.req_ready(cr),.req_write(mw),.req_addr(ma),.req_data(md),
   .rsp_valid(sv),.rsp_ready(sr),.rsp_data(sd),.init_done(initialized),
   .sd_clk(sclk),.sd_cke(cke),.sd_cs_n(cs),.sd_ras_n(ras),.sd_cas_n(cas),.sd_we_n(we),.sd_addr(addr),.sd_bank(bank),.sd_dqm(mask),.sd_dq(dq));
  sdram_timing_model memory(.clk(sclk),.cke(cke),.cs_n(cs),.ras_n(ras),.cas_n(cas),.we_n(we),
   .addr(addr),.ba(bank),.dqm(mask),.dq(dq),.operational(initialized),.refreshes(refs),.reads(reads),.writes(writes),.max_refresh_gap(gap));
  initial begin
   wait(cycle==209999);#1;$display("SDRAM refs=%0d reads=%0d writes=%0d max_gap=%0d",refs,reads,writes,gap);
  end
 end else begin:mock_ram
  memory_backend_model #(.AW(6)) memory(.clk(clk),.rst_n(rst_n),.pause(pause),.latency(8'd13),
   .req_valid(mv),.req_ready(mr),.req_write(mw),.req_addr(ma),.req_data(md),.rsp_valid(sv),.rsp_ready(sr),.rsp_data(sd));
 end endgenerate
 initial begin
  fd=$fopen("trace-stream.txt","w");repeat(3)@(negedge clk);rst_n=1;
  repeat(210000)begin
   @(negedge clk);random_state=random_state*1664525+1013904223;
   tick=cycle%512==0;
   rec_enable=cycle>=10000 && cycle<160000;
   play_enable=cycle>=10000 && cycle<180000 && !(cycle>=80385&&cycle<83385) && !(cycle>=130049&&cycle<133049);
   // Producer holds valid/data throughout long backpressure; pause starts
   // only on an accepted word so it does not violate a valid/ready contract.
   if(!feed || feed_accepted)feed=cycle<180000 && !(cycle>=40000&&cycle<60000);
   host_ready=!(cycle>=20000&&cycle<40000) && !(cycle>=150000&&cycle<166000);
   pause=(cycle>=109500&&cycle<111500) || (cycle>=140000&&cycle<142000);
   rc=cycle==30000 || cycle==110000;
   pc=cycle==80385 || cycle==130049 || cycle==180000;
   // An accepted explicit session clear also cancels the producer's old head.
   if(pc)feed=0;
  end
  if(rl||rrl||rv||prl||pl||busy)$fatal(1,"stream final drain incomplete");
  $display("PASS stream REAL_MEMORY=%0d cycles=%0d stopped_record_drained play_cleared",REAL_MEMORY,cycle);
  $fclose(fd);$finish;
 end
 always @(posedge clk)begin
  cycle=cycle+1;
  feed_accepted=feed&&fr;
  if(tick || rv&&host_ready || feed&&fr || pv || miss || rc&&rcr || pc&&pcr || rcd || pcd || mv&&mr || sv&&sr || !rst_n || cycle%1000==0)
  $fdisplay(fd,"%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
   cycle,rst_n,rc&&rcr,pc&&pcr,rcd,pcd,rcb,pcb,rec_enable,tick,pcm,rv&&host_ready,rd,feed&&fr,data,pv,pd,miss,over,under,
   mv&&mr,mw,ma,rl,pl,rrl,prl,play_enable,tick);
  if(rst_n)begin
   if(tick)pcm<=pcm+3;if(feed&&fr)data<=data+9;
   if(over||under||miss)$fatal(1,"unexpected stream overflow/underrun");
   if(rcb&&rv || pcb&&fr)$fatal(1,"stream host accepted during clear");
   if(pcb&&(pv||miss))$fatal(1,"stream output during clear");
  end
 end
 initial begin #9000000;$fatal(1,"stream watchdog");end
endmodule
