`timescale 1ns/1ps
module tb_native;
parameter NG=32,QW=18;
reg clk=0;always #5 clk=~clk;
reg we=0;reg[$clog2(NG)-1:0]wa=0,ra=0,rb=0;reg[QW-1:0]data=0;
wire[QW-1:0]qa,qb;
pitch_native_store #(.NG(NG),.QW(QW))dut(.clk(clk),.we(we),.wa(wa),.ra(ra),.rb(rb),.data(data),.qa(qa),.qb(qb));
reg[QW-1:0]memory[0:NG-1];reg[31:0]random_state=32'h198584;
integer i,n,writes=0,same=0,sweeps=0;
task check;
begin if(qa!==memory[ra]||qb!==memory[rb])$fatal(1,"native store mismatch");end
endtask
initial begin
 for(i=0;i<NG;i=i+1)memory[i]=0;
 for(n=0;n<20000;n=n+1)begin
  @(negedge clk);random_state=random_state*1664525+1013904223;
  wa=random_state>>15;ra=random_state>>7;rb=random_state>>24;we=random_state[4];data=random_state;
  if(n%3==0)ra=wa;if(n%5==0)rb=wa;
  #1;check();@(posedge clk);
  if(we)begin memory[wa]=data;writes=writes+1;if(ra==wa||rb==wa)same=same+1;end
  #1;check();
  if(n%257==0)begin
   @(negedge clk);we=0;
   for(i=0;i<NG;i=i+1)begin ra=i;rb=NG-1-i;#1;check();end
   sweeps=sweeps+1;
  end
 end
 if(writes<5000||same<1000||sweeps!=78)$fatal(1,"native coverage");
 $display("PASS native NG=%0d QW=%0d cycles=20000 writes=%0d read_write=%0d full_address_sweeps=%0d async_reads",NG,QW,writes,same,sweeps);$finish;
end
endmodule
