`timescale 1ns/1ps
module tb_delta;
 parameter LANES=6,CW=12;
 reg clk=0;always #5 clk=~clk;
 reg rst_n=0,calibrate=0,row_valid=0,frame_ready=0;
 reg [3:0]row_address=0;reg[LANES*CW-1:0]row_count=0;reg[LANES-1:0]row_fault=0;
 reg[31:0]row_sequence=0;reg[6:0]read_address=0;
 wire rr1,rr2,fv1,fv2,fc1,fc2,rv1,rv2,e1,e2;wire[31:0]fs1,fs2;wire[CW-1:0]d1,d2;
 rc_delta_store #(.LANES(LANES),.CW(CW)) dut(.clk(clk),.rst_n(rst_n),.calibrate(calibrate),.row_valid(row_valid),.row_ready(rr1),.row_address(row_address),.row_count(row_count),.row_fault(row_fault),.row_sequence(row_sequence),.frame_valid(fv1),.frame_ready(frame_ready),.frame_sequence(fs1),.frame_calibration(fc1),.read_address(read_address),.read_delta(d1),.read_valid(rv1),.protocol_error(e1));
 rc_delta_reference #(.LANES(LANES),.CW(CW)) reference(.clk(clk),.rst_n(rst_n),.calibrate(calibrate),.row_valid(row_valid),.row_ready(rr2),.row_address(row_address),.row_count(row_count),.row_fault(row_fault),.row_sequence(row_sequence),.frame_valid(fv2),.frame_ready(frame_ready),.frame_sequence(fs2),.frame_calibration(fc2),.read_address(read_address),.read_delta(d2),.read_valid(rv2),.protocol_error(e2));
 integer cycle=0,i,collisions=0,known_collisions=0,updates=0,frames=0,resets=0;
 reg[31:0]random_state=32'h851919;
 task check;
 begin
  if({rr1,fv1,fc1,rv1,e1,fs1,d1}!=={rr2,fv2,fc2,rv2,e2,fs2,d2})$fatal(1,"delta old-data mismatch cycle=%0d address=%0d new=%h old=%h",cycle,read_address,d1,d2);
 end
 endtask
 initial begin
  repeat(3)@(negedge clk);rst_n=1;
  repeat(120000)begin
   @(negedge clk);cycle=cycle+1;random_state=random_state*1664525+1013904223;
   calibrate=(cycle%4096==1);frame_ready=random_state[3];row_valid=random_state[4];
   row_address=reference.expected;row_sequence=reference.expected==0?cycle:reference.sequence_q;
   if(cycle%991==0)row_address=row_address+3;
   if(cycle%541==0&&reference.expected!=0)row_sequence=row_sequence+1;
   for(i=0;i<LANES;i=i+1)row_count[i*CW+:CW]=(random_state>>(i%4))^(cycle*31+i*97);
   row_fault=random_state>>24;read_address=random_state>>9;
   if(cycle%3!=0)read_address=reference.index;
   if(cycle%19001==0)begin #1;rst_n=0;resets=resets+1;end else rst_n=1;
   @(posedge clk);
   if(reference.state==2)begin
    updates=updates+1;
    if(read_address==reference.index)begin collisions=collisions+1;if((^reference.old_word)!==1'bx)known_collisions=known_collisions+1;end
   end
   if(fv2&&frame_ready)frames=frames+1;
   #1;check();
  end
  if(collisions<1000||known_collisions<1000||frames<50||resets!=6)$fatal(1,"missing delta coverage");
  $display("PASS delta LANES=%0d CW=%0d cycles=%0d writes=%0d collisions=%0d known_collisions=%0d frames=%0d resets=%0d",LANES,CW,cycle,updates,collisions,known_collisions,frames,resets);$finish;
 end
endmodule
