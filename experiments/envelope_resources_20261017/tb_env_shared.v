`timescale 1ns/1ps
module env_compare #(parameter W=16)(
 input wire [23:0] level,attack,decay,sustain,release_inc,cutoff,
 input wire [2:0] stage,input wire on_event,off_event,exponential,
 input wire [1:0] dm,rm,input wire [4:0] dk,rk
);
 wire [W-1:0] actual,expected;wire [2:0] actual_stage,expected_stage;
 osc_env #(.ENV_W(W)) candidate(.lvl_i(level[W-1:0]),.a_inc(attack[W-1:0]),.d_inc(decay[W-1:0]),.s_lvl(sustain[W-1:0]),.r_inc(release_inc[W-1:0]),.cutoff(cutoff[W-1:0]),
  .stg_i(stage),.trig_on(on_event),.trig_rel(off_event),.exp_mode(exponential),.d_m(dm),.r_m(rm),.d_k(dk),.r_k(rk),.lvl_o(actual),.stg_o(actual_stage));
 osc_env_reference #(.ENV_W(W)) reference(.lvl_i(level[W-1:0]),.a_inc(attack[W-1:0]),.d_inc(decay[W-1:0]),.s_lvl(sustain[W-1:0]),.r_inc(release_inc[W-1:0]),.cutoff(cutoff[W-1:0]),
  .stg_i(stage),.trig_on(on_event),.trig_rel(off_event),.exp_mode(exponential),.d_m(dm),.r_m(rm),.d_k(dk),.r_k(rk),.lvl_o(expected),.stg_o(expected_stage));
 always @(negedge tb_env_shared.check)if({actual,actual_stage}!=={expected,expected_stage})
  $fatal(1,"shared envelope mismatch width=%0d case=%0d stage=%0d exp=%b level=%h actual=%h/%d expected=%h/%d",W,tb_env_shared.cases,stage,exponential,level,actual,actual_stage,expected,expected_stage);
endmodule
module tb_env_shared;
 reg [23:0] level=0,attack=0,decay=0,sustain=0,release_inc=0,cutoff=0;
 reg [2:0] stage=0;reg on_event=0,off_event=0,exponential=0,check=0;
 reg [1:0] dm=0,rm=0;reg [4:0] dk=0,rk=0;
 env_compare #(8) w8(.*);env_compare #(16) w16(.*);env_compare #(24) w24(.*);
 reg [31:0] rng=32'h9f6b12a3;integer cases=0,i,j,k,m,s,e,t;
 reg [23:0] edges[0:13];
 function [31:0] next_random;
 input [31:0] v;reg [31:0] x;
 begin x=v^(v<<13);x=x^(x>>17);next_random=x^(x<<5);end
 endfunction
 task verify;
 begin check=1;#1;check=0;#1;cases=cases+1;end
 endtask
 task random_parameters;
 begin
  rng=next_random(rng);level=rng[23:0];stage=rng[26:24];{exponential,on_event,off_event}=rng[29:27];
  rng=next_random(rng);attack=rng[23:0];dm=rng[25:24];dk=rng[30:26];
  rng=next_random(rng);decay=rng[23:0];rm=rng[25:24];rk=rng[30:26];
  rng=next_random(rng);sustain=rng[23:0];rng=next_random(rng);release_inc=rng[23:0];rng=next_random(rng);cutoff=rng[23:0];
 end
 endtask
 initial begin
  edges[0]=0;edges[1]=1;edges[2]=99;edges[3]=100;edges[4]=101;edges[5]=127;edges[6]=128;
  edges[7]=32767;edges[8]=32768;edges[9]=32769;edges[10]=65534;edges[11]=65535;edges[12]=24'h7fffff;edges[13]=24'hffffff;
  for(i=0;i<500000;i=i+1)begin random_parameters;verify;end
  // Sweep the full product-width level range, not only levels used by ADSR.
  for(i=0;i<65536;i=i+1)begin random_parameters;level=i;verify;end
  for(i=0;i<14;i=i+1)for(m=0;m<4;m=m+1)for(k=0;k<32;k=k+1)
   for(s=0;s<8;s=s+1)for(e=0;e<2;e=e+1)for(t=0;t<4;t=t+1)begin
    level=edges[i];sustain=level-1;cutoff=level+1;attack=edges[(i+1)%14];
    decay=edges[(i+2)%14];release_inc=edges[(i+3)%14];
    dm=m;rm=3-m;dk=k;rk=31-k;stage=s;exponential=e;{on_event,off_event}=t;verify;
   end
  // Procedural-if unknown-mode behavior and invalid-state defaults are retained.
  for(i=0;i<14;i=i+1)for(s=0;s<8;s=s+1)begin
   random_parameters;level=edges[i];stage=s;exponential=1'bx;on_event=0;off_event=0;verify;
   on_event=1'bx;off_event=1'bx;verify;stage=3'bxxx;verify;
  end
  $display("PASS shared_envelope_reference cases=%0d widths=8,16,24 random full_level_range boundaries all_states coefficients shifts triggers linear_exp unknown_mode",cases);$finish;
 end
endmodule
