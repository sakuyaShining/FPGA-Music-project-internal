`timescale 1ns/1ps
module tb_engine_safety;
reg clk=0,rst=0,en=0,gate=0;
reg [7:0] start_tag=0;
reg [7:0] tags[0:31];
reg [8:0] pc=0,slot=0;
reg [23:0] inc=0;
reg [7:0] amp=0;
reg [22:0] ep={16'd12000,2'd3,5'd4};
reg [31:0] fingers=0;
reg [575:0] offsets=0;
wire signed [23:0] sample;
integer starts=0,frames=0,peak=0;
always #5 clk=~clk;
always @(posedge clk) if(!rst) pc<=0; else pc<=pc+1'b1;
tdm_engine #(.NSLOT(512),.PART(16),.FINGER_EXPR(1),.EXPLICIT_START(1)) dut(
 .clk(clk),.rst_n(rst),.sample_en(pc==0),.clr(1'b0),.pclr(1'b0),.gate_in(1'b0),
 .load_en(en),.load_slot(slot),.load_inc(inc),.load_amp(amp),.load_gate(gate),.load_start_tag(start_tag),.load_epar(ep),
 .env_en(1'b1),.a_inc(16'd4096),.d_inc(16'd512),.d_m(2'd3),.d_k(5'd4),
 .s_lvl(16'd12000),.r_inc(16'd256),.r_m(2'd3),.r_k(5'd13),.env_cutoff(16'd0),.exp_mode(1'b0),
 .load_gq(18'sd0),.pmod_cfg(58'd0),.finger_active(fingers),.finger_offsets(offsets),.sample_out(sample));
always @(posedge clk) if(rst && dut.sl1==0 && dut.trig_on) starts=starts+1;
task cycles; input integer n; begin repeat(n) @(negedge clk); end endtask
task samples; input integer n; begin cycles(n*512); end endtask
task put; input integer s;input g,t;input [23:0] f;input [7:0] a;
begin
 @(negedge clk);slot=s;gate=g;if(t) tags[s/16]=tags[s/16]+1'b1;
 start_tag=tags[s/16];inc=f;amp=a;en=1;
 @(negedge clk);en=0;
end endtask
task align; begin wait(pc==100); @(negedge clk); end endtask
task silent_window;
begin
 samples(4);
 repeat(16) begin
  wait(pc==8); @(negedge clk);
  if(sample!==0) $fatal(1,"invalid frequency leaked sample=%0d",sample);
  samples(1);
 end
end endtask
integer before_start,old_level;
initial begin
 for(frames=0;frames<32;frames=frames+1) tags[frames]=0;
 cycles(4);rst=1;
 put(0,1,1,24'd1000000,8'd120);samples(90);
 if(dut.env_mem[0]!==12000) $fatal(1,"sustain setup failed");
 before_start=starts;
 // An explicit ON and a refresh before the pending buffer is consumed.
 align;put(0,1,1,24'd1000000,8'd120);put(0,1,0,24'd1000000,8'd80);samples(3);
 if(starts!=before_start+1 || dut.env_mem[0]<=12000) $fatal(1,"pending ON lost/replayed by refresh");
 samples(90);before_start=starts;
 put(0,1,0,24'd1000000,8'd60);samples(4);
 if(starts!=before_start || dut.env_mem[0]!==12000) $fatal(1,"refresh restarted envelope");
 // OFF->ON within one frame has no gate edge after coalescing, but is a new excitation.
 align;put(0,0,0,24'd1000000,8'd60);put(0,1,1,24'd1000000,8'd60);samples(3);
 if(starts!=before_start+1 || dut.env_mem[0]<=12000) $fatal(1,"fast OFF ON did not restart");
 samples(90);put(0,0,0,24'd1000000,8'd60);samples(8);old_level=dut.env_mem[0];
 if(dut.stg_mem[0]!==4 || old_level>=12000) $fatal(1,"release setup failed");
 put(0,1,1,24'd1000000,8'd60);samples(3);
 if(dut.env_mem[0]<=old_level || dut.stg_mem[0]!==1) $fatal(1,"tail reattack failed");
 samples(90);before_start=starts;
 // A start cancelled by a final OFF must not escape the pending buffer.
 align;put(0,1,1,24'd1000000,8'd60);put(0,0,0,24'd1000000,8'd60);samples(4);
 if(starts!=before_start || dut.gcur_mem[0]!==0) $fatal(1,"cancelled ON replayed");
 put(0,1,1,24'h700000,8'd120);samples(90);
 before_start=starts;fingers=1;offsets[17:0]=18'sd65536;silent_window;
 offsets[17:0]=-18'sd65536;silent_window;
 offsets[17:0]=-18'sd131072;silent_window;
 offsets[17:0]=0;samples(4);peak=0;
 repeat(32) begin wait(pc==8);@(negedge clk);if(sample!=0) peak=1;samples(1);end
 if(!peak || starts!=before_start) $fatal(1,"pitch recovery failed or retriggered");
 // Group31 and its last partial exercise the upper group/address bits.
 put(511,1,1,24'h700000,8'd120);samples(90);
 fingers[31]=1;offsets[31*18+:18]=18'sd65536;samples(4);
 wait(dut.sl1==511);@(posedge clk);#1;
 if(dut.amp2!==0) $fatal(1,"group31 final-increment guard failed");
 put(511,0,0,24'h700000,8'd120);samples(4);
 old_level=dut.env_mem[511];put(511,1,1,24'd1000000,8'd120);samples(3);
 if(dut.env_mem[511]<=old_level) $fatal(1,"last-slot tail restart failed");
 $display("RESULT engine_safety=PASS refresh_no_retrigger rapid_OFF_ON release_reattack pending_cancel pitch_overflow_zero_negative_recovery group31");$finish;
end
initial begin #10000000;$fatal(1,"timeout");end
endmodule
