`timescale 1ns/1ps
module tb_scan_store;
parameter WIDTH=587,HARD_WORDS=6,GAP_SIZE=0;
reg clk=0;always #5 clk=~clk;
reg din=0;wire[WIDTH-1:0]q;reg[WIDTH-1:0]reference;
reg gsr_n=0;GSR GSR(.GSRI(gsr_n));
probe_scan_store #(.WIDTH(WIDTH),.HARD_WORDS(HARD_WORDS),.GAP_START(26),.GAP_SIZE(GAP_SIZE))dut(.clk(clk),.din(din),.q(q));
reg[31:0]random_state=32'h861919;
integer cycle=0,n,checks=0,ones=0,zeros=0;
always @(posedge clk)begin
 reference<={reference[WIDTH-2:0],din};
 #1;
 if(cycle>WIDTH+4)begin
  if(q!==reference)$fatal(1,"scan history mismatch cycle=%0d",cycle);
  checks=checks+1;
 end
end
initial begin
 repeat(3)@(negedge clk);gsr_n=1;
 for(n=0;n<20000;n=n+1)begin
  @(negedge clk);cycle=cycle+1;random_state=random_state*1664525+1013904223;
  if(cycle<WIDTH*2)din=0;
  else if(cycle<WIDTH*4)din=1;
  else din=random_state[31];
  if(din)ones=ones+1;else zeros=zeros+1;
 end
 @(negedge clk);
 if(checks<15000||ones<1000||zeros<1000)$fatal(1,"scan coverage");
 $display("PASS scan WIDTH=%0d DSP_WORDS=%0d GAP=%0d cycles=20000 checked=%0d one_clock all_bits old_shift_equivalent",WIDTH,HARD_WORDS,GAP_SIZE,checks);$finish;
end
endmodule
