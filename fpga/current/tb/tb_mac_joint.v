`timescale 1ns/1ps
module tb_joint;
reg gsr_n=0;GSR GSR(.GSRI(gsr_n));
parameter ACCESS_DELAY=10;
reg clk=0;always #18.5185 clk=~clk;
reg reset_button=1,scan_in=0;wire probe_out;wire [5:0]led;
wire di,ws,bck,pa,sc,cke,cs,ras,cas,we;wire[10:0]addr;wire[1:0]ba;wire[3:0]dqm;tri[31:0]dq;
joint_timing_top dut(.clk(clk),.reset_button(reset_button),.scan_in(scan_in),.probe_out(probe_out),.led(led),
 .dac_din(di),.dac_ws(ws),.dac_bck(bck),.pa_en(pa),.O_sdram_clk(sc),.O_sdram_cke(cke),.O_sdram_cs_n(cs),
 .O_sdram_ras_n(ras),.O_sdram_cas_n(cas),.O_sdram_wen_n(we),.O_sdram_addr(addr),.O_sdram_ba(ba),.O_sdram_dqm(dqm),.IO_sdram_dq(dq));
wire [31:0]refreshes,reads,writes,max_gap;
sdram_timing_model #(.ACCESS_DELAY(ACCESS_DELAY)) memory(.clk(sc),.cke(cke),.cs_n(cs),.ras_n(ras),.cas_n(cas),.we_n(we),.addr(addr),.ba(ba),.dqm(dqm),.dq(dq),.operational(dut.probe_sdram_init_done),.refreshes(refreshes),.reads(reads),.writes(writes),.max_refresh_gap(max_gap));
reg [586:0]vector=0,expected_shift=0;
reg [29:0]expected_observation;
reg [31:0]random_state=32'h841985;
integer i,cycles=0,recorded=0,drained=0,fed=0,played=0,nonzero=0,pcm_seen=0,previous_pcm=-1;
reg active=0,observe_check=0;reg[15:0]queue[0:1023];
function[15:0]pattern;input integer n;begin pattern=(n*173)^16'h6a53;end endfunction
always @(posedge clk)begin
 cycles=cycles+1;
 if(dut.rst_n)begin
  if(dut.phase==0)expected_observation=dut.capture;else expected_observation={1'b0,dut.observation[29:1]};
  observe_check=1;
 end else begin expected_observation=0;observe_check=0;end
 if(active)begin
  if(dut.probe_pcm_valid)begin
   if(previous_pcm>=0&&cycles-previous_pcm!=512)$fatal(1,"sample period");previous_pcm=cycles;pcm_seen=pcm_seen+1;
  end
  if(dut.probe_pcm_valid&&dut.system.rec_enable)begin
   if((^dut.probe_pcm)===1'bx)$fatal(1,"unknown music PCM");
   queue[recorded]=dut.probe_pcm[23:8];recorded=recorded+1;if(dut.probe_pcm!=0)nonzero=nonzero+1;
  end
  if(dut.probe_rec_valid&&dut.system.rec_ready)begin
   if(drained>=recorded||dut.probe_rec_data!==queue[drained])$fatal(1,"live record mismatch at %0d",drained);drained=drained+1;
  end
  if(dut.system.feed_valid&&dut.probe_feed_ready)fed=fed+1;
  if(dut.probe_play_valid)begin
   if(played>=fed||dut.probe_play_data!==pattern(played))$fatal(1,"playback mismatch");played=played+1;
  end
  if(dut.probe_rec_overflow||dut.probe_play_underflow)$fatal(1,"unexpected transport fault");
 end
 #1;
 if(observe_check&&dut.observation!==expected_observation)$fatal(1,"registered observation mismatch");
 if({di,ws,bck,pa}!==4'd0)$fatal(1,"acoustic isolation");
 if(dut.system.rec_clear!==dut.controls[0+:1])$fatal(1,"scan port rec_clear");
if(dut.system.rec_enable!==dut.controls[1+:1])$fatal(1,"scan port rec_enable");
if(dut.system.rec_ready!==dut.controls[2+:1])$fatal(1,"scan port rec_ready");
if(dut.system.play_clear!==dut.controls[3+:1])$fatal(1,"scan port play_clear");
if(dut.system.play_enable!==dut.controls[4+:1])$fatal(1,"scan port play_enable");
if(dut.system.feed_valid!==dut.controls[5+:1])$fatal(1,"scan port feed_valid");
if(dut.system.feed_data!==dut.controls[6+:16])$fatal(1,"scan port feed_data");
if(dut.system.layer_selection!==dut.controls[22+:4])$fatal(1,"scan port layer_selection");
if(dut.system.cfg_valid!==dut.controls[26+:1])$fatal(1,"scan port cfg_valid");
if(dut.system.cfg_commit!==dut.controls[27+:1])$fatal(1,"scan port cfg_commit");
if(dut.system.cfg_slot!==dut.controls[28+:2])$fatal(1,"scan port cfg_slot");
if(dut.system.cfg_part!==dut.controls[30+:4])$fatal(1,"scan port cfg_part");
if(dut.system.cfg_word!==dut.controls[34+:88])$fatal(1,"scan port cfg_word");
if(dut.system.sense_n!==dut.controls[122+:6])$fatal(1,"scan port sense_n");
if(dut.system.calibrate!==dut.controls[128+:1])$fatal(1,"scan port calibrate");
if(dut.system.scan_bus_grant!==dut.controls[129+:1])$fatal(1,"scan port scan_bus_grant");
if(dut.system.left_note_map!==dut.controls[130+:182])$fatal(1,"scan port left_note_map");
if(dut.system.left_velocity!==dut.controls[312+:4])$fatal(1,"scan port left_velocity");
if(dut.system.threshold_on!==dut.controls[316+:14])$fatal(1,"scan port threshold_on");
if(dut.system.threshold_off!==dut.controls[330+:14])$fatal(1,"scan port threshold_off");
if(dut.system.uart_rx_pin!==dut.controls[344+:1])$fatal(1,"scan port uart_rx_pin");
if(dut.system.ev_valid!==dut.controls[345+:1])$fatal(1,"scan port ev_valid");
if(dut.system.ev_on!==dut.controls[346+:1])$fatal(1,"scan port ev_on");
if(dut.system.ev_note!==dut.controls[347+:7])$fatal(1,"scan port ev_note");
if(dut.system.ev_vel!==dut.controls[354+:4])$fatal(1,"scan port ev_vel");
if(dut.system.preset!==dut.controls[358+:2])$fatal(1,"scan port preset");
if(dut.system.touch_valid!==dut.controls[360+:1])$fatal(1,"scan port touch_valid");
if(dut.system.touch_active!==dut.controls[361+:5])$fatal(1,"scan port touch_active");
if(dut.system.touch_x!==dut.controls[366+:50])$fatal(1,"scan port touch_x");
if(dut.system.touch_y!==dut.controls[416+:50])$fatal(1,"scan port touch_y");
if(dut.system.touch_id!==dut.controls[466+:20])$fatal(1,"scan port touch_id");
if(dut.system.radius!==dut.controls[486+:10])$fatal(1,"scan port radius");
if(dut.system.slew_step!==dut.controls[496+:10])$fatal(1,"scan port slew_step");
if(dut.system.part_to_control!==dut.controls[506+:48])$fatal(1,"scan port part_to_control");
if(dut.system.restore_valid!==dut.controls[554+:1])$fatal(1,"scan port restore_valid");
if(dut.system.voice_mask!==dut.controls[555+:32])$fatal(1,"scan port voice_mask");
end
initial begin
 // Check actual shift transport before forcing the internal integration controls.
 repeat(3)@(negedge clk);gsr_n=1;
 for(i=0;i<700;i=i+1)begin
  @(negedge clk);random_state=random_state*1664525+1013904223;scan_in=random_state[31];
  @(posedge clk);expected_shift={expected_shift[585:0],dut.scan_sync};#1;
  if(i>=587&&dut.controls!==expected_shift)begin
   $fatal(1,"input scan shift i=%0d xor=%h",i,dut.controls^expected_shift);
  end
 end
 @(negedge clk);vector=0;vector[344+:1]=1'b1;
vector[22+:4]=4'd1;
vector[122+:6]=6'h3f;
vector[129+:1]=1'b1;
vector[312+:4]=4'd10;
vector[316+:14]=14'd8;
vector[330+:14]=14'd4;
vector[347+:7]=7'd60;
vector[354+:4]=4'd10;
vector[486+:10]=10'd50;
vector[496+:10]=10'd16;
vector[555+:32]=32'hffffffff;
vector[130+:182]=182'd0;
vector[130+:7]=48;
vector[137+:7]=49;
vector[144+:7]=50;
vector[151+:7]=51;
vector[158+:7]=52;
vector[165+:7]=53;
vector[172+:7]=54;
vector[179+:7]=55;
vector[186+:7]=56;
vector[193+:7]=57;
vector[200+:7]=58;
vector[207+:7]=59;
vector[214+:7]=60;
vector[221+:7]=61;
vector[228+:7]=62;
vector[235+:7]=63;
vector[242+:7]=64;
vector[249+:7]=65;
vector[256+:7]=66;
vector[263+:7]=67;
vector[270+:7]=68;
vector[277+:7]=69;
vector[284+:7]=70;
vector[291+:7]=71;
vector[298+:7]=72;
vector[305+:7]=73;
vector[506+:3]=0;
vector[509+:3]=0;
vector[512+:3]=1;
vector[515+:3]=1;
vector[518+:3]=2;
vector[521+:3]=2;
vector[524+:3]=3;
vector[527+:3]=3;
vector[530+:3]=4;
vector[533+:3]=4;
vector[536+:3]=5;
vector[539+:3]=5;
vector[542+:3]=6;
vector[545+:3]=6;
vector[548+:3]=7;
vector[551+:3]=7;
 force dut.controls=vector;
 @(negedge clk);reset_button=0;
 wait(dut.probe_sdram_init_done);repeat(5000)@(negedge clk);active=1;
 vector[2+:1]=1'b1;
 @(negedge clk);vector[346+:1]=1'b1; vector[345+:1]=1'b1;
 @(negedge clk);vector[345+:1]=1'b0;
 // Feed more than the eventual consumption count, allowing bounded prefill.
 for(i=0;i<256;i=i+1)begin
  @(negedge clk);vector[5+:1]=1'b1; vector[6+:16]=pattern(i);
  while(!dut.probe_feed_ready)@(negedge clk);
 end
 @(negedge clk);vector[5+:1]=1'b0;
 repeat(5000)@(negedge clk);vector[1+:1]=1'b1; vector[4+:1]=1'b1;
 wait(recorded>=200);@(negedge clk);vector[1+:1]=1'b0;
 wait(played>=200);@(negedge clk);vector[4+:1]=1'b0;
 wait(drained==recorded);repeat(200)@(negedge clk);
 if(recorded<200||drained!=recorded||played<200||nonzero<50||refreshes<100||reads<400||writes<400)$fatal(1,"coverage rec%0d drain%0d play%0d nz%0d reads%0d writes%0d",recorded,drained,played,nonzero,reads,writes);
 $display("PASS forced joint RTL cycles=%0d PCM=%0d recorded=%0d drained=%0d played=%0d nonzero=%0d refresh=%0d max_gap=%0d scan700 observer audio_muted; NOT hardware protocol",cycles,pcm_seen,recorded,drained,played,nonzero,refreshes,max_gap);$finish;
end
initial begin #12000000;$fatal(1,"joint watchdog");end
endmodule
