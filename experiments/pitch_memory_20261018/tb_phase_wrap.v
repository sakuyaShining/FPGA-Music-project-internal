`timescale 1ns/1ps
module tb_phase_wrap;
reg clk=0;always #5 clk=~clk;reg rst_n=0;reg [2:0] div=0;
always @(posedge clk)if(!rst_n)div<=0;else div<=div+1'b1;
reg load_en=0,gate=0;
wire [39:0] profile={4'd0,1'b1,4'd15,16'd32768,4'd0,4'd15,2'd1,5'd0};
tdm_engine_rh #(.NSLOT(8),.PART(2),.INSTRUMENT_ENV(1),.EXPLICIT_START(1)) dut(
 .clk(clk),.rst_n(rst_n),.sample_en(div==7),.clr(1'b0),.pclr(1'b0),.gate_in(1'b1),
 .load_en(load_en),.load_slot(3'd0),.load_inc(24'd45000),.load_amp(8'd20),.load_gate(gate),.load_start_tag(8'd1),.load_epar({16'd32768,2'd1,5'd0}),.load_env(profile),.load_gq(18'sd0),
 .env_en(1'b1),.a_inc(16'd117),.d_inc(16'd1),.d_m(2'd3),.d_k(5'd12),.s_lvl(16'd22938),.r_inc(16'd1),.r_m(2'd3),.r_k(5'd13),.env_cutoff(16'd100),.exp_mode(1'b1),
 .pmod_cfg(58'd0),.finger_active(4'd0),.finger_offsets(72'd0),.timbre_gain_q8(20'd0),.timbre_voice_mask(4'd0));
task waitclocks;input integer n;begin repeat(n)@(negedge clk);end endtask
initial begin
 waitclocks(4);rst_n=1;waitclocks(80);load_en=1;gate=1;waitclocks(1);load_en=0;
 waitclocks(260000);
 if(dut.env_mem[0]!=0||dut.stg_mem[0]!=1)$fatal(1,"slow attack did not hold before wrap");
 waitclocks(3000);
 if(dut.env_mem[0]!=32768||dut.stg_mem[0]!=3)$fatal(1,"attack tick lost at phase wrap");
 load_en=1;gate=0;waitclocks(1);load_en=0;waitclocks(40);
 if(dut.stg_mem[0]!=4||dut.env_mem[0]!=32768)$fatal(1,"release event blocked by divider");
 waitclocks(250000);
 if(dut.env_mem[0]!=32768)$fatal(1,"release divider ran too early");
 waitclocks(15000);
 if(dut.env_mem[0]!=0||dut.stg_mem[0]!=0)$fatal(1,"release tick lost at phase wrap");
 $display("PASS phase_wrap max_divider15 attack release gate_event two_rollovers");$finish;
end
endmodule
