module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0,valid=0,on=0,refresh=0;
reg[6:0] note=60; reg[7:0] vel=64; wire busy,le; wire[8:0] slot; wire[23:0] inc; wire[7:0] amp; wire gate; wire[22:0] ep; wire signed[17:0] gq; wire[31:0] active;
note_map d(.clk(clk),.rst_n(rst_n),.ev_valid(valid),.ev_on(on),.ev_note(note),.ev_vel(vel),.preset(2'd0),.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(refresh),.rf_lo(7'd0),.rf_hi(8'd32),.load_en(le),.load_slot(slot),.load_inc(inc),.load_amp(amp),.load_gate(gate),.load_epar(ep),.load_gq(gq),.busy(busy),.active(active));
task event_note; input[6:0] nn; input oo; input[7:0] vv; begin
@(negedge clk); valid=1; note=nn; on=oo; vel=vv; @(negedge clk); valid=0; end endtask
task idle; begin repeat(5) @(negedge clk); wait(!busy); repeat(3) @(negedge clk); end endtask
always @(negedge clk) if(le && slot[3:0]==0) $display("load slot=%0d amp=%0d gate=%0d vel_cur=%0d",slot,amp,gate,d.vel_cur);
initial begin #22 rst_n=1;
event_note(60,1,64); event_note(64,1,240); idle;
$display("busy_collision active=%h expected_two_notes=00000003",active);
event_note(64,1,240); idle;
@(negedge clk) refresh=1; @(negedge clk) refresh=0; idle;
$display("refresh_complete (compare slot0 amplitude with original)");
event_note(60,0,0); idle;
$display("note_off_complete (compare slot0 amplitude with original)");
event_note(108,1,240); idle;
$display("nyquist_overflow note108 part15 ratio=%0d full_inc=%0d truncated=%0d kill=%0d",d.ratio_q8,d.inc_mul>>8,d.inc_cal,d.nyq_kill);
$finish; end
endmodule