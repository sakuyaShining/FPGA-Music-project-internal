`timescale 1ns/1ps
// Desired safety property, tested against the unmodified integration-07 source.
// A failure is a reproduced boundary defect, not an accepted product behavior.
module tb_note_map_guard;
reg clk=0, rst_n=0, valid=0;
always #5 clk=~clk;
wire le, gate, busy, ack;
wire [8:0] slot;
wire [23:0] inc;
wire [7:0] amp;
wire [22:0] ep;
wire signed [17:0] gq;
wire [31:0] active;
note_map #(.NG(32),.P(16)) dut(
 .clk(clk),.rst_n(rst_n),.ev_valid(valid),.ev_on(1'b1),
 .ev_note(7'd108),.ev_vel(8'd255),.preset(2'd0),
 .tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),
 .spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),
 .spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(1'b0),.rf_lo(7'd0),.rf_hi(8'd32),
 .load_en(le),.load_slot(slot),.load_inc(inc),.load_amp(amp),.load_gate(gate),
 .load_epar(ep),.load_gq(gq),.busy(busy),.ev_ack(ack),.active(active));
integer untruncated;
initial begin
 repeat(4) @(negedge clk);
 rst_n=1;
 repeat(2) @(negedge clk);
 valid=1;
 @(negedge clk);valid=0;
end
always @(negedge clk) if(le && slot==15) begin
 untruncated=dut.note_rom[108]*16;
 $display("OBSERVED note=108 preset=0 partial=16 full_increment=%0d loaded_increment=%0d loaded_amp=%0d",
          untruncated,inc,amp);
 if(untruncated < 8388608) $fatal(1,"Invalid test stimulus");
 if(amp!=0) $fatal(1,"TARGET FAIL: over-Nyquist partial remained audible after truncation");
 $display("TARGET PASS: over-Nyquist partial muted");$finish;
end
initial begin #100000; $fatal(1,"No observed slot; invalid test run"); end
endmodule
