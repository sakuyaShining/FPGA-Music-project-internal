`timescale 1ns/1ps
module tb_envelope;
reg clk=0;always #5 clk=~clk;
reg rst_n=0;reg [4:0] divider=0;
always @(posedge clk)if(!rst_n)divider<=0;else divider<=divider+1'b1;
reg load_en=0,load_gate=0;reg [4:0] load_slot=0;reg [7:0] tag=0;
reg [39:0] ext=0;reg [22:0] epar=0;
tdm_engine_rh #(.NSLOT(32),.PART(16),.INSTRUMENT_ENV(1),.EXPLICIT_START(1)) dut(
 .clk(clk),.rst_n(rst_n),.sample_en(divider==31),.clr(1'b0),.pclr(1'b0),.gate_in(1'b1),
 .load_en(load_en),.load_slot(load_slot),.load_inc(24'd45000),.load_amp(8'd20),.load_gate(load_gate),.load_start_tag(tag),.load_epar(epar),.load_env(ext),.load_gq(18'sd0),
 .env_en(1'b1),.a_inc(16'd117),.d_inc(16'd1),.d_m(2'd3),.d_k(5'd12),.s_lvl(16'd22938),.r_inc(16'd1),.r_m(2'd3),.r_k(5'd13),.env_cutoff(16'd100),.exp_mode(1'b1),
 .pmod_cfg(58'd0),.finger_active(2'd0),.finger_offsets(36'd0),.timbre_gain_q8(160'd0),.timbre_voice_mask(2'd0));
integer cycle=0,fd;reg [31:0] random_state=32'h59a47328;reg [3:0] a_shift,d_shift,r_shift;reg [15:0] a_inc,sustain;reg [1:0] rm,dm;reg [4:0] rk,dk;
reg [1023:0] filename;
always @(posedge clk)if(rst_n)begin
 $fdisplay(fd,"%0d %0d %0d %0d %0d %0d %0d %h %0d %0d %0d %h %0d %0d %0d %0d %0d %0d %0d %h %h %h",cycle,dut.sc,dut.sl1,dut.env1,dut.stg1,dut.gc1,dut.gq1,dut.epar1,dut.pv1,dut.pp1,dut.pg1,dut.pe1,dut.per_instrument_env.phase_read,dut.ppr1,dut.env_n,dut.stg_n,load_en,load_slot,load_gate,ext,tag,epar);
 cycle=cycle+1;
end
initial begin
 if(!$value$plusargs("trace=%s",filename))$fatal(1,"trace path required");fd=$fopen(filename,"w");
 repeat(4)@(negedge clk);rst_n=1;
 while(cycle<50000)begin
  @(negedge clk);load_en=0;
  if((cycle>=64&&cycle<96)||(cycle>=6000&&cycle<6032)||(cycle>=16000&&cycle<16032))begin
   load_en=1;load_slot=cycle[4:0];load_gate=cycle<6000||cycle>=16000;tag=cycle>=16000?2:1;
   a_shift={2'd0,load_slot[1:0]};d_shift=0;r_shift={2'd0,load_slot[1:0]};a_inc=16'd8192>>load_slot[1:0];sustain=load_slot[0]?16'd0:16'd32768;rm=1;rk=5'd4+{3'd0,load_slot[1:0]};dm=1;dk=4;
   // A release must retain its old stored envelope, even if supplied metadata differs.
   if(!load_gate)begin a_shift=0;r_shift=0;a_inc=32768;rm=3;rk=1;end
   ext={4'd0,1'b1,a_shift,a_inc,d_shift,r_shift,rm,rk};epar={sustain,dm,dk};
  end else if(cycle>=20000&&cycle<45000)begin
   random_state=random_state*32'd1664525+32'd1013904223;
   if(random_state[3:0]<3)begin
    load_en=1;load_slot=random_state[8:4];load_gate=random_state[9];tag=random_state[17:10];
    a_shift={2'd0,random_state[19:18]};d_shift={2'd0,random_state[21:20]};r_shift={2'd0,random_state[23:22]};a_inc=16'd8192>>random_state[25:24];
    sustain=random_state[26]?32768:0;dm=1;dk=5'd2+{3'd0,random_state[28:27]};rm=1;rk=5'd3+{3'd0,random_state[30:29]};
    ext={4'd0,random_state[31],a_shift,a_inc,d_shift,r_shift,rm,rk};epar={sustain,dm,dk};
   end
  end
 end
 $fclose(fd);$display("PASS trace generated cycles=%0d",cycle);$finish;
end
endmodule
