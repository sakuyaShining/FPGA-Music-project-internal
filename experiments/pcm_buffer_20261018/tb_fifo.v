`timescale 1ns/1ps
module tb_fifo;
 parameter AW=3;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,clear=0,iv=0,orr=0;reg [15:0] id=0;
 wire ir,ov;wire [15:0] od;wire [AW:0] level;
 pcm_sync_fifo #(.AW(AW)) dut(clk,rst_n,clear,iv,ir,id,ov,orr,od,level);
 integer f,o,n,c,rv,cv,ivv,orrv,dv;reg [1023:0] input_path,output_path;
 reg pre_ir,pre_ov;reg [15:0] pre_od;
 initial begin
  if(!$value$plusargs("input=%s",input_path)||!$value$plusargs("output=%s",output_path))$fatal(1,"paths");
  f=$fopen(input_path,"r");o=$fopen(output_path,"w");n=0;
  while(!$feof(f))begin
   c=$fscanf(f,"%d %d %d %d %d\n",rv,cv,ivv,orrv,dv);
   if(c!=5)$fatal(1,"stimulus");
   @(negedge clk);rst_n=rv;clear=cv;iv=ivv;orr=orrv;id=dv;
   #1;pre_ir=ir;pre_ov=ov;pre_od=od;
   @(posedge clk);#1;
   $fwrite(o,"%0d %0d %0d %h %0d\n",n,pre_ir,pre_ov,pre_od,level);n=n+1;
  end
  $fclose(f);$fclose(o);$display("PASS fifo trace AW=%0d cycles=%0d",AW,n);$finish;
 end
endmodule
