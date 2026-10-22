`timescale 1ns/1ps
module tb_release_spike;
reg clk=0,rst=0,valid=0,on=0;reg[7:0] vel=0;
wire busy,load,gate;wire[7:0] amp;wire[8:0] slot;
always #5 clk=~clk;
note_map dut(.clk(clk),.rst_n(rst),.ev_valid(valid),.ev_on(on),.ev_note(7'd69),.ev_vel(vel),.preset(2'd0),
.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),
.spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),
.refresh_valid(1'b0),.rf_lo(7'd0),.rf_hi(8'd32),.busy(busy),.load_en(load),.load_gate(gate),.load_amp(amp),.load_slot(slot));
integer count;reg[7:0] a_on,a_off;
task event_capture;
input is_on;input[7:0] v;output[7:0] first;
begin
while(busy) @(negedge clk);
@(negedge clk);on=is_on;vel=v;valid=1;
@(negedge clk);valid=0;
count=0;
while(count<16) begin
@(negedge clk);
if(load) begin if(count==0) first=amp; count=count+1;end
end
while(busy) @(negedge clk);
end endtask
integer i;
initial begin
repeat(4) @(negedge clk);rst=1;
for(i=4;i<=15;i=i+4) begin
 event_capture(1,i*16,a_on);event_capture(0,0,a_off);
 $display("VELOCITY %0d ON %0d OFF %0d",i,a_on,a_off);
end
$display("RESULT release_spike_probe=DONE");$finish;
end
endmodule
