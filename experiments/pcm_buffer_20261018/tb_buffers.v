`timescale 1ns/1ps
module tb_buffers;
 reg clk=0;always #5 clk=~clk;
 reg rst=0,rc=0,re=0,pv=0,rr=0,pc=0,pe=0,tick=0,fv=0;
 reg [15:0] pd=0,fd=0;
 wire rv,fr,over,pvalid,under,miss;wire [15:0] rd,pdata;wire [10:0] rl,pl;
 pcm_storage_buffers dut(clk,rst,rc,re,pv,pd,rv,rr,rd,rl,over,pc,pe,tick,fv,fr,fd,pvalid,pdata,pl,under,miss);
 integer rec_in=0,rec_out=0,play_in=0,play_out=0,misses=0,cycles=0,n;
 integer expected_rec[0:20000];integer expected_play[0:20000];
 reg [15:0] wanted;reg expected_valid,expected_miss;
 function [15:0] pattern;input integer n;begin pattern=(n*37)^16'ha55a;end endfunction
 always @(posedge clk)begin
  cycles=cycles+1;
  if(!rst||rc)begin rec_in=0;rec_out=0;end
  else begin
   if(rv&&rr)begin
    if(rec_out>=rec_in||rd!==expected_rec[rec_out][15:0])$fatal(1,"record order/duplication");rec_out=rec_out+1;
   end
   if(pv&&re&&!over&&dut.capture_ready)begin expected_rec[rec_in]=pd;rec_in=rec_in+1;end
  end
  expected_valid=rst&&!pc&&pe&&tick&&dut.queued_valid;
  expected_miss=rst&&!pc&&pe&&tick&&!dut.queued_valid;
  if(!rst||pc)begin play_in=0;play_out=0;misses=0;end
  else begin
   if(expected_valid)begin
    if(play_out>=play_in)$fatal(1,"play empty consumed");wanted=expected_play[play_out];play_out=play_out+1;
   end
   if(fv&&fr)begin expected_play[play_in]=fd;play_in=play_in+1;end
   if(expected_miss)misses=misses+1;
  end
  #1;
  if(pvalid!==expected_valid||miss!==expected_miss)$fatal(1,"sample deadline/valid");
  if(expected_valid&&pdata!==wanted)$fatal(1,"play sample ordering");
 end
 task step;input integer c;begin repeat(c)@(negedge clk);end endtask
 initial begin
  step(3);rst=1;step(2);
  // Fill both paths with unique data, no consumption; capacity exactly 1024.
  re=1;pv=1;fv=1;
  for(n=0;n<1024;n=n+1)begin pd=pattern(n);fd=pattern(n+5000);step(1);end
  pv=0;fv=0;step(2);
  if(rl!=1024||pl!=1024||over||under)$fatal(1,"capacity/preload");
  // Overflow poisons recording until explicit clear, while playback continues.
  pv=1;pd=16'hffff;step(1);pv=0;if(!over)$fatal(1,"overflow not reported");
  rr=1;pe=1;
  for(n=0;n<1024;n=n+1)begin tick=1;pv=1;pd=pattern(n+8000);step(1);tick=0;pv=0;step(511);end
  if(rec_in!=1024||rec_out!=1024||play_out!=1024||misses||!over)$fatal(1,"drain/prefix/interference");
  tick=1;step(1);tick=0;step(1);
  if(!under||misses!=1)$fatal(1,"underflow not explicit");
  rc=1;pc=1;step(1);rc=0;pc=0;re=1;pe=0;rr=0;step(2);
  if(over||under||rl||pl)$fatal(1,"clear recovery");
  // Native 512-clock cadence. Backend stalls 400000 clocks (~14.81ms),
  // then drains in bursts. 782 samples maximum, below the 1024 capacity.
  for(n=0;n<1200000;n=n+1)begin
   pv=(n%512==0);pd=pattern(n/512);
   rr=(n>=400000)&&(n%64<32);
   fv=(n%128==0);fd=pattern(n/128+9000);
   // Playback starts after enough prefetch; independent from record stalls.
   pe=(n>=20000);tick=(n%512==0);
   step(1);
  end
  pv=0;fv=0;pe=0;rr=1;step(2048);
  if(over||under||rec_in!=2344||rec_out!=2344)$fatal(1,"bounded backend stall lost data");
  $display("PASS buffers native512 rec=%0d/%0d play=%0d misses=%0d no_stall_errors cycles=%0d",rec_out,rec_in,play_out,misses,cycles);
  // Stop draining for longer than full FIFO budget; no silent loss allowed.
  rc=1;step(1);rc=0;rr=0;re=1;
  for(n=0;n<1100;n=n+1)begin pv=1;pd=pattern(n);step(1);pv=0;step(511);end
  if(!over||rec_in!=1024)$fatal(1,"long stall did not stop at contiguous prefix");
  // Clear queued words and request playback before any new preload.
  pc=1;step(1);pc=0;pe=1;tick=1;step(1);tick=0;step(2);
  if(!under||pvalid||play_out!=0)$fatal(1,"stale playback after clear");
  $display("PASS bounded overflow after1024 explicit underflow clear separate lanes; final cycles=%0d",cycles);$finish;
 end
 initial begin #30000000;$fatal(1,"timeout");end
endmodule
