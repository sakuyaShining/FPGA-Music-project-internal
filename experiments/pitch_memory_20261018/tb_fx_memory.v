`timescale 1ns/1ps
module fx_compare #(parameter AW=11,FLUSH=2048)(
 input wire clk,rst_n,sample_en,input wire signed [23:0] din,
 input wire dry_en,dly_en,cho_en,rev_en,input wire [2:0] wet_sh,
 input wire [15:0] dly_len,cho_rate,cho_depth,input wire [7:0] fb_q8,rev_fb_q8,
 input wire [2:0] rev_damp
);
 wire signed [23:0] actual,expected;wire signed [15:0] tap_actual,tap_expected;
 fx_delay #(.AW(AW),.FLUSH_LEN(FLUSH)) candidate(.*,.dout(actual),.tap_dbg(tap_actual));
 fx_delay_reference #(.AW(AW),.FLUSH_LEN(FLUSH)) reference(.*,.dout(expected),.tap_dbg(tap_expected));
 integer j,write_index,writes=0,known_outputs=0,unknown_outputs=0;
 reg write_now;reg signed [15:0] expected_write;
 always @(posedge clk)begin
  write_now=rst_n&&!sample_en&&reference.st==11;write_index=reference.wptr;
  expected_write=reference.flush_done?reference.wr_val:0;
  #1;
  if({actual,tap_actual,candidate.ch_tap,candidate.st,candidate.wptr,candidate.lfo_ph,candidate.flush_done,candidate.flush_cnt,candidate.rev_lp}
   !=={expected,tap_expected,reference.ch_tap,reference.st,reference.wptr,reference.lfo_ph,reference.flush_done,reference.flush_cnt,reference.rev_lp})
   $fatal(1,"fx memory mismatch AW=%0d cycle=%0d tag=%d st=%d actual=%h expected=%h",AW,tb_fx_memory.cycle,candidate.read_tag,candidate.st,actual,expected);
  for(j=0;j<8;j=j+1)if(candidate.rt[j]!==reference.rt[j])$fatal(1,"fx tap mismatch AW=%0d cycle=%0d tap=%0d",AW,tb_fx_memory.cycle,j);
  if(write_now)begin
   if(candidate.line[write_index]!==expected_write||reference.line[write_index]!==expected_write)$fatal(1,"fx write mismatch");
   writes=writes+1;
  end
  if((^actual)===1'bx)unknown_outputs=unknown_outputs+1;else known_outputs=known_outputs+1;
 end
endmodule
module tb_fx_memory;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,sample_en=0;reg signed [23:0] din=0;
 reg dry_en=1,dly_en=0,cho_en=0,rev_en=0;reg [2:0] wet_sh=1;
 reg [15:0] dly_len=1024,cho_rate=500,cho_depth=100;
 reg [7:0] fb_q8=96,rev_fb_q8=192;reg [2:0] rev_damp=3;
 fx_compare #(.AW(11),.FLUSH(2048)) product(.*);
 fx_compare #(.AW(4),.FLUSH(16)) wrap(.*);
 integer cycle=0;reg [31:0] rng=32'hf3b21987;
 function [31:0] random_next;input [31:0] x;reg [31:0] v;
 begin v=x^(x<<13);v=v^(v>>17);random_next=v^(v<<5);end endfunction
 initial begin
  for(cycle=0;cycle<600000;cycle=cycle+1)begin
   @(negedge clk);rng=random_next(rng);
   // Exercise real512-clock cadence, then parameter changes on every clock,
   // interrupted tap sweeps, repeated sample pulses and resets mid-read/write.
   rst_n=!(cycle<4||(cycle>=170003&&cycle<170008)||(cycle>=370011&&cycle<370016));
   sample_en=cycle%512==0;
   if(cycle>=200000&&cycle<300000)sample_en=rng[5:0]==0||cycle%32==0;
   if(cycle>=450000&&cycle<451024)sample_en=1;
   if(cycle<100000)begin
    din=(cycle%512==1)?24'sh400000:0;
    {dry_en,dly_en,cho_en,rev_en}=(cycle/6144)%16;
    dly_len=(cycle/16384)%2?1:2047;
   end else begin
    din=rng[23:0];{dry_en,dly_en,cho_en,rev_en}=rng[27:24];wet_sh=rng[30:28];
    rng=random_next(rng);{cho_rate,dly_len}=rng;
    rng=random_next(rng);cho_depth=rng[15:0];fb_q8=rng[23:16];rev_fb_q8=rng[31:24];
    rng=random_next(rng);rev_damp=rng[2:0];
    if(cycle%4096<16)begin dly_len=cycle%4;fb_q8=cycle[0]?255:0;rev_fb_q8=cycle[1]?255:0;end
   end
  end
  @(negedge clk);
  if(product.writes<30000||wrap.writes<30000)$fatal(1,"coverage lacks ring wraps");
  $display("PASS fx_memory cycles=%0d AW11_writes=%0d AW4_writes=%0d known=%0d unknown=%0d all_taps_dout_state_write_exact live_parameters reset interrupted_reads",cycle,product.writes,wrap.writes,product.known_outputs,product.unknown_outputs);$finish;
 end
endmodule
