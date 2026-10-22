`timescale 1ns/1ps
module tb_final_check;
 reg clk=0,reset_button=1;always #18.5185 clk=~clk;
 wire [31:0] dq;
 sdram_board_top dut(.clk(clk),.reset_button(reset_button),.IO_sdram_dq(dq));
 integer cases=0,j;
 task check;input[7:0] code;input[5:0] mask;input[31:0] prefix,clears,after_stop;
  begin
   reset_button=1;repeat(3)@(negedge clk);reset_button=0;wait(dut.rst_n);@(negedge clk);
   // Directed unit test of the real default-width final acceptance predicate;
   // intentionally bypasses the traffic FSM, which has separate end-to-end tests.
   dut.state=20;dut.epoch=2;dut.tests=mask;dut.prefix_count=prefix;dut.clear_count=clears;dut.after_stop=after_stop;
   repeat(2)begin @(posedge clk);#1;end
   if(code==0)begin if(dut.state!=18||dut.tests!=63)$fatal(1,"valid final metrics rejected");end
   else if(dut.state!=19||dut.error_code!=code)$fatal(1,"invalid final metrics escaped code=%0d state=%0d gotcode=%0d",code,dut.state,dut.error_code);
   cases=cases+1;
  end
 endtask
 initial begin
  check(0,6'h1f,132097,6,8193);
  check(11,6'h1e,132097,6,8193);
  check(12,6'h1f,132096,6,8193);
  check(13,6'h1f,132097,5,8193);
  check(14,6'h1f,132097,6,0);
  check(11,6'h3f,132097,6,8193);
  for(j=0;j<32;j=j+1)check(12,6'h1f,32'd132097^(32'd1<<j),6,8193);
  $display("PASS 38 default-width final acceptance/rejection cases including every prefix bit");$finish;
 end
endmodule
