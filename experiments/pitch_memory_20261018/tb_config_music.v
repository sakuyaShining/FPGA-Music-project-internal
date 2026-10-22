`timescale 1ns/1ps
module tb_config_music;
reg clk=0;always #5 clk=~clk;reg rst_n=0;
reg cfg_valid=0,cfg_commit=0;reg [1:0] cfg_slot=0;reg [3:0] cfg_part=0;reg [87:0] cfg_word=0;
reg [3:0] selection=3,contact=0;reg left_valid=0;reg [31:0] seq=0;
wire cfg_ready,cfg_applied,cfg_error,left_ready;wire [3:0] bound,blocked;
wire frame_error,link_error,sensor_error,watchdog_error,lp_error,ls_error,control_error;
wire pcm_valid;wire signed [23:0] pcm;tri [15:0] pad;
left_layer_music_probe #(.NF(4),.INSTRUMENT_ENV(1),.BOARD_BOOT_SCRUB(1)) dut(
 .clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.pad(pad),.ev_valid(1'b0),.ev_on(1'b0),.ev_note(7'd0),.ev_vel(4'd0),.preset(2'd0),
 .layer_selection(selection),.cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),.layer_protocol_error(lp_error),.layer_selection_error(ls_error),
 .left_valid(left_valid),.left_ready(left_ready),.left_contact(contact),.left_invalid(4'd0),.left_position({4{9'd128}}),.left_sequence(seq),.left_calibration(1'b0),.left_note_map({7'd72,7'd67,7'd64,7'd69}),.left_velocity(4'd12),
 .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound),.blocked_contacts(blocked),
 .touch_valid(1'b0),.touch_active(5'd0),.touch_x(50'd0),.touch_y(50'd0),.touch_id(20'd0),.radius(10'd50),.slew_step(10'd1),.part_to_control(48'd0),.restore_valid(1'b0),.voice_mask(32'hffffffff),.control_error(control_error),.pcm_valid(pcm_valid),.pcm(pcm));
reg [87:0] fast[0:15],slow[0:15],hybrid[0:15],strike[0:15];
integer cycles=0,samples=0,nonzero=0,ons=0,offs=0,applies=0,errors=0,last_sample=-1;integer i,a,b,h,s,fd;reg [1023:0] filename;
reg [39:0] old_a,old_b;
always @(posedge clk)if(rst_n)begin
 cycles=cycles+1;
 if(cfg_applied)applies=applies+1;if(cfg_error)errors=errors+1;
 if(dut.child_valid&&dut.child_ready)begin if(dut.child_on)ons=ons+1;else offs=offs+1;end
 if(frame_error||link_error||sensor_error||watchdog_error||lp_error||ls_error||control_error)$fatal(1,"chain fault");
 if(pcm_valid)begin
  if(last_sample>=0&&cycles-last_sample!=512)$fatal(1,"PCM cadence");last_sample=cycles;samples=samples+1;
  if(cycles>4096&&(^pcm)===1'bx)$fatal(1,"unknown PCM");if(pcm!=0)nonzero=nonzero+1;
  $fdisplay(fd,"%0d %0d %h %0d %0d %0d %0d",cycles,pcm,dut.core.nm_active,dut.core.u_tdm.env_mem[0],dut.core.u_tdm.env_mem[16],ons,offs);
 end
end
task config_op;
 input commit;input [1:0] slot;input [3:0] part;input [87:0] word;
 begin @(negedge clk);while(!cfg_ready)@(negedge clk);cfg_valid=1;cfg_commit=commit;cfg_slot=slot;cfg_part=part;cfg_word=word;@(negedge clk);cfg_valid=0;@(negedge clk);end
endtask
task report;
 input [3:0] ct;
 begin @(negedge clk);while(!left_ready)@(negedge clk);left_valid=1;contact=ct;@(negedge clk);left_valid=0;seq=seq+1;while(!left_ready)@(negedge clk);repeat(4)@(negedge clk);end
endtask
initial begin
 if(!$value$plusargs("trace=%s",filename))$fatal(1,"trace required");fd=$fopen(filename,"w");
 $readmemh("../../config-fast.hex",fast);$readmemh("../../config-slow.hex",slow);$readmemh("../../config-hybrid.hex",hybrid);$readmemh("../../config-strike.hex",strike);
 repeat(4)@(negedge clk);rst_n=1;repeat(4096)@(negedge clk);
 config_op(1,0,0,0);config_op(0,0,0,fast[0]|(88'd1<<84));
 if(errors!=2||dut.core.u_nm.cfg_enabled!=0)$fatal(1,"incomplete/reserved configuration published");
 for(i=0;i<16;i=i+1)config_op(0,0,i[3:0],fast[i]);config_op(1,0,0,0);
 for(i=0;i<16;i=i+1)config_op(0,1,i[3:0],slow[i]);config_op(1,1,0,0);
 for(i=0;i<16;i=i+1)config_op(0,2,i[3:0],hybrid[i]);config_op(1,2,0,0);
 for(i=0;i<16;i=i+1)config_op(0,3,i[3:0],strike[i]);config_op(1,3,0,0);
 if(applies!=4||dut.core.u_nm.cfg_enabled!=15)$fatal(1,"four slot publication");
 report(1);a=dut.layers.groups0[0];b=dut.layers.groups1[0];repeat(512*128)@(negedge clk);
 if(ons!=2||bound!=1||a==b)$fatal(1,"dual allocation");
 if(dut.core.u_tdm.env_mem[a*16]!=32768||dut.core.u_tdm.env_mem[b*16]>=20000||dut.core.u_tdm.env_mem[b*16]==0)$fatal(1,"independent attack");
 old_a=dut.core.u_tdm.epar_mem[a*16][70:31];old_b=dut.core.u_tdm.epar_mem[b*16][70:31];
 for(i=0;i<16;i=i+1)config_op(0,0,i[3:0],slow[i]);config_op(1,0,0,0);repeat(512*20)@(negedge clk);
 if(dut.core.u_tdm.epar_mem[a*16][70:31]!=old_a||dut.core.u_tdm.epar_mem[b*16][70:31]!=old_b||ons!=2)$fatal(1,"commit changed held envelope");
 report(0);repeat(512*256)@(negedge clk);
 if(offs!=2||dut.core.nm_active||dut.core.u_tdm.env_mem[a*16]!=0||dut.core.u_tdm.env_mem[b*16]==0)$fatal(1,"independent release or hanging gate");
 if(dut.core.u_tdm.epar_mem[a*16][70:31]!=old_a||dut.core.u_tdm.epar_mem[b*16][70:31]!=old_b)$fatal(1,"OFF replaced old envelope with edited slot");
 selection=1;report(1);a=dut.layers.groups0[0];repeat(512*10)@(negedge clk);
 if(dut.core.u_tdm.epar_mem[a*16][70:31]!=slow[0][87:48])$fatal(1,"new note ignored edited envelope");
 selection=4;report(2);h=dut.layers.groups0[1];repeat(512*400)@(negedge clk);
 if(dut.core.u_tdm.env_mem[h*16]!=hybrid[0][22:7]||dut.core.u_tdm.env_mem[h*16+1]!=0||!dut.core.nm_active[h])$fatal(1,"hybrid partial envelopes");
 selection=8;report(4);s=dut.layers.groups0[2];repeat(512*300)@(negedge clk);
 if(dut.core.u_tdm.env_mem[s*16]!=0||!dut.core.nm_active[s])$fatal(1,"strike must decay while still held");
 report(0);repeat(512*3000)@(negedge clk);
 if(dut.core.nm_active||bound||pcm!=0||ons!=offs)$fatal(1,"final release silence");
 $fclose(fd);$display("PASS config_music cycles=%0d samples=%0d nonzero=%0d child_on=%0d child_off=%0d commits=%0d rejects=%0d independent_ADSR edit_snapshot hybrid strike final_silence",cycles,samples,nonzero,ons,offs,applies,errors);$finish;
end
initial begin #30000000;$fatal(1,"timeout");end
endmodule
