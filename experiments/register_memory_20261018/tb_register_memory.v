`timescale 1ns/1ps
module tb_register_memory;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=1,we=0,re=0;reg [7:0] wa=0,wd=0,ra=0;
 wire [7:0] oldrd,newrd;wire [1023:0] oldflat,newflat;
 reg_bank #(.NW(128)) reference_bank(clk,rst_n,we,wa,wd,re,ra,oldrd,oldflat);
 reg_bank_compact candidate(clk,rst_n,we,wa,wd,re,ra,newrd,newflat);
 integer cycle=0,k,seed=7818,collisions=0,holds=0,highwrites=0,highreads=0,resets=0;
 reg [31:0] random_word;reg [255:0] written=0,readset=0;
 always @(posedge clk)begin
  #1;
  if(oldrd!==newrd)$fatal(1,"read mismatch cycle=%0d addr=%h we=%b wa=%h old=%h new=%h",cycle,ra,we,wa,oldrd,newrd);
  for(k=0;k<128;k=k+1)begin
   if(candidate.FLAT_MASK[k])begin
    if(oldflat[k*8+:8]!==newflat[k*8+:8])$fatal(1,"mirror mismatch cycle=%0d byte=%h",cycle,k);
   end else if(newflat[k*8+:8]!==0)$fatal(1,"unused flat byte not zero");
  end
 end
 initial begin
  #1;rst_n=0;#1;if(newrd!==0)$fatal(1,"async reset");
  @(negedge clk);rst_n=1;
  for(cycle=0;cycle<150000;cycle=cycle+1)begin
   @(negedge clk);random_word=$random(seed);
   we=random_word[0];re=random_word[1];wa=random_word[15:8];wd=random_word[23:16];ra=random_word[31:24];
   if(cycle<512)begin we=1;re=1;wa=cycle;ra=cycle;wd=cycle^8'ha5;end
   if(cycle>=512 && cycle<1024)begin we=0;re=1;ra=cycle;end
   if(cycle%11==0)begin re=1;we=1;ra=wa;end
   if(cycle%1999==0)begin
    #2;rst_n=0;#1;if(oldrd!==0||newrd!==0)$fatal(1,"midcycle reset output");resets=resets+1;
   end else if(cycle%1999==5)rst_n=1;
   if(we)begin written[wa]=1;if(wa[7])highwrites=highwrites+1;end
   if(re)begin readset[ra]=1;if(ra[7])highreads=highreads+1;end else holds=holds+1;
   if(we&&re&&wa==ra)collisions=collisions+1;
  end
  @(negedge clk);
  if(written!=={256{1'b1}}||readset!=={256{1'b1}}||collisions<10000||holds<50000||resets<70)$fatal(1,"coverage missing");
  $display("PASS register_memory cycles=%0d all256_addresses collisions=%0d read_holds=%0d highwrite=%0d highread=%0d resets=%0d",cycle,collisions,holds,highwrites,highreads,resets);$finish;
 end
endmodule
