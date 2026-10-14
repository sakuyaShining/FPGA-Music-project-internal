`timescale 1ns/1ps
// Exercise the REAL allocator->pending buffer->envelope connection.
module tb_retrigger_top;
reg clk=0,rst=0,valid=0,on=0;
wire [15:0] pads;
integer starts=0,old_starts,level;
always #5 clk=~clk;
tdm_top dut(.clk(clk),.rst_n(rst),.ev_valid(valid),.ev_on(on),.ev_note(7'd60),
 .ev_vel(4'd12),.preset(2'd0),.test_mode(1'b0),.uart_rx_pin(1'b1),
 .pad(pads));
always @(posedge clk) if(rst && dut.u_tdm.sl1==0 && dut.u_tdm.trig_on) starts=starts+1;
task frames;input integer n;begin repeat(n*512) @(negedge clk);end endtask
task event_note;input value;begin
 @(negedge clk);on=value;valid=1;
 @(negedge clk);valid=0;
 repeat(100) @(negedge clk);
end endtask
initial begin
 repeat(4) @(negedge clk);rst=1;frames(4);
 event_note(1);frames(24);
 if(starts!=1 || dut.u_tdm.env_mem[0]==0) $fatal(1,"initial note failed");
 old_starts=starts;
 event_note(1);frames(4);
 if(starts!=old_starts+1) $fatal(1,"held same-note ON did not re-excite");
 event_note(0);frames(6);level=dut.u_tdm.env_mem[0];
 if(level==0 || dut.u_tdm.stg_mem[0]!==4) $fatal(1,"release-tail setup failed");
 old_starts=starts;event_note(1);frames(4);
 if(starts!=old_starts+1 || dut.u_tdm.env_mem[0]<=level) $fatal(1,"tail note-on failed");
 old_starts=starts;event_note(0);event_note(1);frames(4);
 if(starts!=old_starts+1) $fatal(1,"fast OFF ON lost at real allocator");
 $display("RESULT retrigger_top=PASS held_repeat tail_reattack fast_OFF_ON");$finish;
end
initial begin #3000000;$fatal(1,"timeout");end
endmodule
