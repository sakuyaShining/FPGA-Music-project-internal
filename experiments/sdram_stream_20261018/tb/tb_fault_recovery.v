`timescale 1ns/1ps
module tb_fault_recovery;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,rc=0,pc=0,tick=0,re=0,pe=0,feed=0,rr=0;
 reg [15:0] pcm=16'h1000,data=16'h9000;
 wire rcr,pcr,rcd,pcd,rcb,pcb,rv,fr,pv,over,under,miss,busy;
 wire [15:0] rd,pd,md,sd;wire [2:0] rl,pl;wire [3:0] rrl,prl;
 wire mv,mr,mw,sv,sr;wire [21:0] ma;
 integer cycle=0,fd,accepted=0;
 pcm_sdram_stream #(.FIFO_AW(2),.RING_AW(3)) dut(.clk(clk),.rst_n(rst_n),
 .rec_clear(rc),.play_clear(pc),.rec_clear_ready(rcr),.play_clear_ready(pcr),
 .rec_clear_done(rcd),.play_clear_done(pcd),.rec_clearing(rcb),.play_clearing(pcb),
 .rec_enable(re),.pcm_valid(tick),.pcm_data(pcm),.rec_valid(rv),.rec_ready(rr),.rec_data(rd),
 .rec_level(rl),.play_level(pl),.rec_ring_level(rrl),.play_ring_level(prl),.rec_overflow(over),
 .play_enable(pe),.sample_tick(tick),.feed_valid(feed),.feed_ready(fr),.feed_data(data),
 .play_valid(pv),.play_data(pd),.play_underflow(under),.play_miss(miss),
 .mem_req_valid(mv),.mem_req_ready(mr),.mem_req_write(mw),.mem_req_addr(ma),.mem_req_data(md),
 .mem_rsp_valid(sv),.mem_rsp_ready(sr),.mem_rsp_data(sd),.mem_busy(busy));
 memory_backend_model #(.AW(3)) memory(.clk(clk),.rst_n(rst_n),.pause(1'b0),.latency(8'd3),
 .req_valid(mv),.req_ready(mr),.req_write(mw),.req_addr(ma),.req_data(md),.rsp_valid(sv),.rsp_ready(sr),.rsp_data(sd));
 initial begin
  fd=$fopen("trace-fault.txt","w");repeat(3)@(negedge clk);rst_n=1;
  repeat(12000)begin
   @(negedge clk);tick=cycle%64==0;rc=cycle==6000;pc=cycle==6000||cycle==11500;
   re=cycle>=64&&cycle<11000;rr=cycle>=3000;
   pe=cycle>=1000&&cycle<11500 && !(cycle>=6000&&cycle<6500);
   feed=cycle<11500 && accepted<16 && !pc && !pcb;
  end
  if(rl||rrl||rv||pl||prl||busy)$fatal(1,"fault recovery did not drain");
  if(over||under)$fatal(1,"clears did not recover sticky flags");
  $display("PASS deliberate overrun prefix, underrun misses, independent clears and recovered stream");$fclose(fd);$finish;
 end
 always @(posedge clk)begin
  cycle=cycle+1;
  $fdisplay(fd,"%0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",
   cycle,rst_n,rc&&rcr,pc&&pcr,rcd,pcd,rcb,pcb,re,tick,pcm,rv&&rr,rd,feed&&fr,data,pv,pd,miss,over,under);
  if(rst_n)begin
   if(tick)pcm<=pcm+1'b1;
   if(feed&&fr)begin data<=data+1'b1;accepted<=accepted+1;end
   if(pc&&pcr && cycle<10000)begin accepted<=0;data<=16'hb000;end
   if(pv&&miss)$fatal(1,"valid stale replay on miss");
   if(pcb&&(pv||miss||fr)||rcb&&rv)$fatal(1,"fault clear isolation");
  end
 end
endmodule
