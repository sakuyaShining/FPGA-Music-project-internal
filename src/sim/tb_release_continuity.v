`timescale 1ns/1ps
module tb_release_continuity;
reg clk=0,rst=0,en=0,gate=0;
reg [8:0] pc=0,slot=0;
reg [23:0] inc=0;
reg [7:0] amp=0;
reg [22:0] ep=0;
always #5 clk=~clk;
always @(posedge clk) if(!rst) pc<=0; else pc<=pc+1'b1;
tdm_engine #(.NSLOT(512),.PART(16)) dut(
.clk(clk),.rst_n(rst),.sample_en(pc==0),.clr(1'b0),.pclr(1'b0),.gate_in(1'b0),
.load_en(en),.load_slot(slot),.load_inc(inc),.load_amp(amp),.load_gate(gate),.load_epar(ep),
.env_en(1'b1),.a_inc(16'd65535),.d_inc(16'd0),.d_m(2'd0),.d_k(5'd0),
.s_lvl(16'd50000),.r_inc(16'd100),.r_m(2'd0),.r_k(5'd0),.env_cutoff(16'd0),.exp_mode(1'b0),
.load_gq(18'sd0),.pmod_cfg(58'd0),.finger_active(32'd0),.finger_offsets(576'd0));
task put;
input [8:0] s; input g; input [7:0] a;input [23:0] f; input [22:0] e;
begin
@(negedge clk);slot=s;gate=g;amp=a;inc=f;ep=e;en=1;
@(negedge clk);en=0;
repeat(1536) @(negedge clk);
end endtask
integer i;reg[7:0] expected;
reg [15:0] level;
initial begin
repeat(4) @(negedge clk);rst=1;
for(i=0;i<512;i=i+1) begin
expected=(i%4==0)?0:(50+i%150);
put(i,1,expected,10000+i,{16'd50000,7'd0});
// Refresh changes the sounding spectrum before release.
expected=expected/2;
put(i,1,expected,20000+i,{16'd45000,7'd0});
if(dut.amp_mem[i]!==expected || dut.inc_mem[i]!==20000+i) $fatal(1,"refresh slot%0d",i);
level=dut.env_mem[i];
// Poison every release parameter; only gate may take effect.
put(i,0,255,24'd999999,{16'd65535,7'd127});
if(dut.amp_mem[i]!==expected || dut.inc_mem[i]!==20000+i || dut.epar_mem[i]!=={16'd45000,7'd0})
$fatal(1,"release changed spectrum slot%0d amp%0d",i,dut.amp_mem[i]);
if(dut.gcur_mem[i]!==0 || dut.env_mem[i]>level) $fatal(1,"release envelope slot%0d",i);
// Reused slot must accept a fresh voice normally.
put(i,1,8'd123,24'd33333,{16'd42000,7'd0});
if(dut.amp_mem[i]!==123 || dut.inc_mem[i]!==33333 || dut.gcur_mem[i]!==1) $fatal(1,"reuse slot%0d",i);
end
$display("RESULT release_continuity=PASS slots=512 refreshed_spectrum preserved silent_partials reuse envelope");$finish;
end
initial begin #100000000; $fatal(1,"timeout"); end
endmodule
