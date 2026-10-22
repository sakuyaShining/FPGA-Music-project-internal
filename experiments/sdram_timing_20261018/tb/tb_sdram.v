`timescale 1ns/1ps
module tb_sdram;
 reg clk=0;always #18.519 clk=~clk;
 reg rst=0,qv=0,qw=0,rr=1;reg [21:0] qa=0;reg [15:0] qd=0;
 wire qr,rv,init,sc,ce,cs,ras,cas,we;wire [15:0] rd;
 wire [10:0] a;wire [1:0] ba;wire [3:0] mask;tri[31:0] dq;
 wire [31:0] refreshes,reads,writes,maxgap;
 sdram_word_controller dut(clk,rst,qv,qr,qw,qa,qd,rv,rr,rd,init,sc,ce,cs,ras,cas,we,a,ba,mask,dq);
 sdram_timing_model memory(sc,ce,cs,ras,cas,we,a,ba,mask,dq,init,refreshes,reads,writes,maxgap);
 integer seed=80018,n,t,completed=0,maxlatency=0,latency;reg [21:0] addresses[0:1023];reg [15:0] values[0:1023];reg [31:0] r;reg [15:0] held;
 task transaction;input write;input[21:0] adr;input[15:0] data;input[15:0] expected;input integer hold;
 begin
  @(negedge clk);qa=adr;qd=data;qw=write;qv=1;rr=0;t=0;
  while(!qr)begin @(negedge clk);t=t+1;if(t>100)$fatal(1,"request never ready");end
  @(posedge clk);#1;@(negedge clk);qv=0;latency=0;
  while(!rv)begin @(negedge clk);latency=latency+1;if(latency>100)$fatal(1,"response late");end
  if(!write&&rd!==expected)$fatal(1,"data address=%h got=%h expected=%h",adr,rd,expected);
  held=rd;
  repeat(hold)begin @(negedge clk);if(!rv||rd!==held||qr)$fatal(1,"response backpressure changed");end
  if(latency>maxlatency)maxlatency=latency;
  rr=1;@(negedge clk);completed=completed+1;
 end endtask
 initial begin
  repeat(4)@(negedge clk);rst=1;
  t=0;while(!init)begin @(negedge clk);t=t+1;if(!init&&(qr||rv))$fatal(1,"accepted before init");if(t>5500)$fatal(1,"init timeout");end
  // All banks, first/last row/column, both halves, and sparse random addresses.
  for(n=0;n<32;n=n+1)addresses[n]={n[4:3],(n[2]?11'h7ff:11'd0),(n[1]?8'hff:8'd0),n[0]};
  for(n=32;n<1024;n=n+1)begin r=$random(seed);addresses[n]={r[1:0],n[9:0],1'b0,n[7:0],n[0]};end
  for(n=0;n<1024;n=n+1)begin
   values[n]=(n*91)^16'hc75a;transaction(1,addresses[n],values[n],0,0);
  end
  for(n=1023;n>=0;n=n-1)transaction(0,addresses[n],0,values[n],n%7);
  for(n=0;n<32;n=n+1)begin
   values[n]=values[n]^16'h1873;transaction(1,addresses[n],values[n],0,0);
   transaction(0,addresses[n^1],0,values[n^1],0);
   transaction(0,addresses[n],0,values[n],0);
  end
  // A response held longer than several refresh periods must not stop refresh.
  transaction(0,addresses[0],0,values[0],2000);
  if(refreshes<10||maxgap>421)$fatal(1,"refresh coverage");
  // A new request's input pins may change while response is pending, but must
  // not change the completed response. Reset cancels in-flight operations.
  @(negedge clk);qv=1;qw=0;qa=1;rr=0;
  while(!qr)@(negedge clk);@(posedge clk);#1;@(negedge clk);qv=0;
  repeat(2)@(negedge clk);rst=0;repeat(4)@(negedge clk);
  if(rv||qr||init)$fatal(1,"reset did not abort");
  rst=1;while(!init)@(negedge clk);
  transaction(1,22'h200001,16'hbeef,0,0);transaction(0,22'h200001,0,16'hbeef,1200);
  $display("PASS SDRAM completed=%0d reads=%0d writes=%0d refreshes=%0d max_refresh_gap=%0d max_response_cycles=%0d CAS3 masks boundaries response_hold reset_reinit",completed,reads,writes,refreshes,maxgap,maxlatency);$finish;
 end
 initial begin #10000000;$fatal(1,"timeout");end
endmodule
