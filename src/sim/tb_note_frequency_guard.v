`timescale 1ns/1ps
module tb_note_frequency_guard;
reg clk=0,rst_n=0,valid=0;
reg [6:0] note=0;
reg [1:0] preset=0;
wire le,gate,busy,ack;
wire [7:0] start_tag;
wire [8:0] slot;
wire [23:0] inc;
wire [7:0] amp;
wire [22:0] ep;
wire signed [17:0] gq;
integer n,p,k,checked=0;
reg [39:0] full_product;
always #5 clk=~clk;
note_map #(.NG(32),.P(16)) dut(
 .clk(clk),.rst_n(rst_n),.ev_valid(valid),.ev_on(1'b1),.ev_note(note),.ev_vel(8'd255),.preset(preset),
 .tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),
 .spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),
 .spec_replace(1'b1),.pad_mask(16'hffff),.refresh_valid(1'b0),.rf_lo(7'd0),.rf_hi(8'd32),
 .load_en(le),.load_slot(slot),.load_inc(inc),.load_amp(amp),.load_gate(gate),.load_start_tag(start_tag),
 .load_epar(ep),.load_gq(gq),.busy(busy),.ev_ack(ack));
always @(negedge clk) if(le) begin
 k=slot%16;
 full_product=dut.note_rom[note]*dut.part_rom[preset*16+k][47:32];
 if((full_product>>8)>=8388608 && amp!==0)
  $fatal(1,"out-of-band note%0d preset%0d partial%0d product%0d amp%0d",note,preset,k,full_product,amp);
 if((full_product>>8)<8388608 && amp==0)
  $fatal(1,"in-band partial incorrectly muted");
 if(start_tag!==dut.group_start_tag[slot/16]) $fatal(1,"note-on lacks its start tag");
 checked=checked+1;
end
initial begin
 repeat(4) @(negedge clk);rst_n=1;
 for(p=0;p<4;p=p+1) for(n=0;n<128;n=n+1) begin
  @(negedge clk);note=n;preset=p;valid=1;
  @(negedge clk);valid=0;
  repeat(25) @(negedge clk);
 end
 if(checked!=8192) $fatal(1,"missing checks %0d",checked);
 $display("RESULT note_frequency_guard=PASS checked=8192 full_product before_truncation explicit_start");$finish;
end
endmodule
