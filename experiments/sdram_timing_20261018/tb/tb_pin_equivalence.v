`timescale 1ns/1ps
module tb_pin_equivalence;
 reg clk=0;always #18.519 clk=~clk;
 reg rst=1,qv=0,qw=0,rr=0;reg[21:0] qa=0;reg[15:0] qd=0;reg[31:0] incoming=0;
 wire rdy0,rdy1,rv0,rv1,init0,init1;wire[15:0] rd0,rd1;
 wire sc0,sc1,cke0,cke1,cs0,cs1,ras0,ras1,cas0,cas1,we0,we1;
 wire[10:0] a0,a1;wire[1:0] b0,b1;wire[3:0] m0,m1;tri[31:0] dq0,dq1;
 sdram_original old(clk,rst,qv,rdy0,qw,qa,qd,rv0,rr,rd0,init0,sc0,cke0,cs0,ras0,cas0,we0,a0,b0,m0,dq0);
 sdram_word_controller dut(clk,rst,qv,rdy1,qw,qa,qd,rv1,rr,rd1,init1,sc1,cke1,cs1,ras1,cas1,we1,a1,b1,m1,dq1);
 assign dq0=!(rst&&old.state==8)?incoming:32'bz;
 assign dq1=!(rst&&dut.drive_write)?incoming:32'bz;
 integer n=0,seed=810018,requests=0,writes=0,reads=0,responses=0,reset_count=0;reg[31:0] r;
 task compare;
 begin
  if({rdy0,rv0,rd0,init0,sc0,cke0,cs0,ras0,cas0,we0,a0,b0,m0,dq0}!==
     {rdy1,rv1,rd1,init1,sc1,cke1,cs1,ras1,cas1,we1,a1,b1,m1,dq1})
    $fatal(1,"pin/handshake mismatch cycle=%0d oldstate=%0d newstate=%0d oldDQ=%h newDQ=%h",n,old.state,dut.state,dq0,dq1);
 end endtask
 initial begin
  #1;rst=0;#1;compare;@(negedge clk);rst=1;
  for(n=0;n<180000;n=n+1)begin
   @(negedge clk);r=$random(seed);qv=r[0];qw=r[1];rr=r[2];qa=r[27:6];qd=r[31:16];incoming=$random(seed);
   if(n%30001==15000)begin #4;rst=0;#1;compare;reset_count=reset_count+1;end
   if(n%30001==15004)rst=1;
   @(posedge clk);
   if(qv&&rdy0)begin requests=requests+1;if(qw)writes=writes+1;else reads=reads+1;end
   if(rv0&&rr)responses=responses+1;
   #1;compare;
   // Changing upstream inputs between active edges must not leak onto pins.
   #3;qa=~qa;qd=~qd;qv=~qv;#1;compare;
  end
  if(requests<1000||writes<500||reads<500||reset_count!=6)$fatal(1,"coverage");
  $display("PASS registered_pin_equivalence cycles=%0d accepted=%0d writes=%0d reads=%0d responses=%0d async_resets=%0d",n,requests,writes,reads,responses,reset_count);$finish;
 end
endmodule
