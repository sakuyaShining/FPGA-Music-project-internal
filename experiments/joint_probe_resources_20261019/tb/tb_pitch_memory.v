`timescale 1ns/1ps
module tb_pitch_memory;
 parameter NG=32,QW=18,SEED=17;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,sample_en=0,gw_en=0,vib_en=0,glide_en=0;
 reg [23:0] lfo_inc=0;reg [15:0] vib_depth=0,glide_step=0;
 reg [$clog2(NG)-1:0] gw_note=0,rd_note=0;
 reg signed [QW-1:0] gw_val=0;
 wire ov1,ov2;wire signed[QW-1:0] p1,p2;
 pitch_mod #(.NG(NG),.QW(QW)) dut(.clk(clk),.rst_n(rst_n),.sample_en(sample_en),.lfo_inc(lfo_inc),.vib_depth(vib_depth),.glide_step(glide_step),.vib_en(vib_en),.glide_en(glide_en),.gw_en(gw_en),.gw_note(gw_note),.gw_val(gw_val),.rd_note(rd_note),.update_overrun(ov1),.poff(p1));
 pitch_mod_reference #(.NG(NG),.QW(QW)) reference(.clk(clk),.rst_n(rst_n),.sample_en(sample_en),.lfo_inc(lfo_inc),.vib_depth(vib_depth),.glide_step(glide_step),.vib_en(vib_en),.glide_en(glide_en),.gw_en(gw_en),.gw_note(gw_note),.gw_val(gw_val),.rd_note(rd_note),.update_overrun(ov2),.poff(p2));
 integer cycle=0,n,writes=0,samples=0,same=0,different=0,resets=0,overlap=0;
 reg [31:0] random_state=SEED;
 task check;
  begin
   if(p1!==p2||ov1!==ov2)$fatal(1,"pitch output mismatch cycle=%0d note=%0d got=%0d old=%0d",cycle,rd_note,p1,p2);
   if(dut.pending!==reference.pending||dut.sweep!==reference.sweep||dut.busy!==reference.busy||dut.step_held!==reference.step_held||dut.lfo_ph!==reference.lfo_ph)$fatal(1,"epoch metadata mismatch");
   for(n=0;n<NG;n=n+1)if(dut.gq[n]!==reference.gq[n])$fatal(1,"logical storage mismatch cycle=%0d group=%0d",cycle,n);
  end
 endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  repeat(240000)begin
   @(negedge clk);random_state=random_state*1664525+1013904223;cycle=cycle+1;
   rd_note=random_state>>7;gw_note=random_state>>19;
   gw_en=random_state[4] || cycle%512<NG;
   sample_en=(cycle%512==0)||(cycle%6000<NG*2&&cycle%7==0);
   lfo_inc=random_state[23:0];vib_depth=random_state[31:16];glide_step=random_state[15:0];
   vib_en=random_state[5];glide_en=random_state[6];gw_val=random_state;
   if(cycle%79==0)gw_val=0;if(cycle%79==1)gw_val={1'b1,{(QW-1){1'b0}}};
   if(cycle%79==2)gw_val={1'b0,{(QW-1){1'b1}}};
   if(cycle%101==0)glide_step=0;if(cycle%101==1)glide_step=65535;
   if(cycle%19001==0)begin #1;rst_n=0;resets=resets+1;#1;check();end else rst_n=1;
   #1;check();
   @(posedge clk);
   if(gw_en)begin
    writes=writes+1;
    if(dut.busy&&!sample_en&&dut.pending[dut.sweep])begin
     if(gw_note==dut.sweep)same=same+1;else different=different+1;
    end
   end
   if(sample_en)samples=samples+1;
   if(sample_en&&gw_en)overlap=overlap+1;
   #1;check();
   // Between-edge address/control changes must still have old combinational semantics.
   #1;rd_note=rd_note+1'b1;vib_en=~vib_en;#1;check();
  end
  if(same==0||different==0||overlap==0||resets==0)$fatal(1,"missing race coverage");
  $display("PASS pitch_memory NG=%0d QW=%0d cycles=%0d writes=%0d epochs=%0d same_write=%0d dual_address_write=%0d sample_write=%0d resets=%0d",NG,QW,cycle,writes,samples,same,different,overlap,resets);$finish;
 end
endmodule
