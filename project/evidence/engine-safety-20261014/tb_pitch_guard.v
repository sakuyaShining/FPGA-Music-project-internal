`timescale 1ns/1ps
module tb_pitch_guard;
reg clk=0,rst=0,en=0;
reg [8:0] pc=0;
reg [31:0] active=0;
reg [575:0] offsets=0;
wire signed [23:0] audio;
always #5 clk=~clk;
always @(posedge clk) if(!rst) pc<=0;else pc<=pc+1'b1;
tdm_engine #(.NSLOT(512),.PART(16),.FINGER_EXPR(1)) dut(
 .clk(clk),.rst_n(rst),.sample_en(pc==0),.clr(1'b0),.pclr(1'b0),.gate_in(1'b0),
 .load_en(en),.load_slot(9'd0),.load_inc(24'h700000),.load_amp(8'd120),.load_gate(1'b1),
 .load_epar({16'd30000,2'd3,5'd4}),.env_en(1'b1),.a_inc(16'd65535),.d_inc(16'd100),
 .d_m(2'd3),.d_k(5'd4),.s_lvl(16'd30000),.r_inc(16'd256),.r_m(2'd3),.r_k(5'd13),
 .env_cutoff(16'd0),.exp_mode(1'b0),.load_gq(18'sd0),.pmod_cfg(58'd0),
 .finger_active(active),.finger_offsets(offsets),.sample_out(audio));
initial begin
 repeat(4) @(negedge clk);rst=1;
 @(negedge clk);en=1;@(negedge clk);en=0;
 repeat(4096) @(negedge clk);active=1;offsets[17:0]=18'sd65536;
 repeat(2048) @(negedge clk);
 repeat(8) begin
  wait(pc==8);@(negedge clk);
  if(audio!==0) $fatal(1,"TARGET FAIL post-expression Nyquist leak %0d",audio);
  repeat(512) @(negedge clk);
 end
 $display("TARGET PASS post-expression Nyquist muted");$finish;
end
initial begin #1000000;$fatal(1,"timeout");end
endmodule
