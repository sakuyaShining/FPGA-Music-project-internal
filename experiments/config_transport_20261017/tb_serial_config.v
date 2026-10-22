`timescale 1ns/1ps
`include "transport_fixture.vh"
module tb_serial_config;
parameter DIV=16,SMOKE=0,DUAL=0;
reg clk=0;always #5 clk=~clk;reg rst_n=0,rx=1;wire tx;tri [15:0] pad;
wire pcm_valid;wire signed [23:0] pcm;
tdm_top_owned #(.CONFIG_DUAL_SOURCE(DUAL),.CONFIG_SERIAL(1),.INSTRUMENT_ENV(1),.BOARD_DIAG(1),.BOARD_BOOT_SCRUB(1),.UART_BAUD(27000000/DIV),.LEGACY_PAD(0),.LIVE_MONITOR(0)) dut(
 .clk(clk),.rst_n(rst_n),.uart_rx_pin(rx),.uart_tx_pin(tx),.test_mode(1'b0),.preset(2'd0),.pad(pad),
 .board_status(8'h19),.board_case(8'd0),.cfg_valid(1'b0),.cfg_commit(1'b0),.cfg_slot(2'd0),.cfg_part(4'd0),.cfg_word(88'd0),
 .own_valid(1'b0),.own_on(1'b0),.own_note(7'd0),.own_vel(4'd0),.own_instance(13'd0),.own_preset(2'd0),
 .ev_valid(1'b0),.ev_on(1'b0),.ev_note(7'd0),.ev_vel(4'd0),.finger_valid(1'b0),.finger_cmd(2'd0),.finger_id(5'd0),.finger_group(5'd0),.finger_position(12'sd0),
 .timbre_gain_q8(160'd0),.timbre_voice_mask(32'd0),.monitor_valid(pcm_valid),.monitor_pcm(pcm));
defparam dut.serial_configuration.receiver.QUIET_CYCLES=DIV*160;
defparam dut.serial_configuration.receiver.TIMEOUT_CYCLES=DIV*4000;
reg [7:0] payload[0:175];reg [87:0] words[0:15];reg [7:0] received[0:4095];integer nr=0,bitno,i,j,start,ncycles=0,samples=0,nonzero=0,lastsample=-1;reg [7:0] rb,v;
always @(posedge clk)if(rst_n)begin
 ncycles=ncycles+1;
 if(pcm_valid)begin
  if(lastsample>=0&&ncycles-lastsample!=512)$fatal(1,"sample cadence");lastsample=ncycles;samples=samples+1;
  if(ncycles>4096&&(^pcm)===1'bx)$fatal(1,"unknown PCM after startup");if(pcm!=0)nonzero=nonzero+1;
 end
end
initial forever begin
 @(negedge tx);repeat(DIV/2)@(negedge clk);
 if(tx!==0)$fatal(1,"UART start");
 for(bitno=0;bitno<8;bitno=bitno+1)begin repeat(DIV)@(negedge clk);rb[bitno]=tx;end
 repeat(DIV)@(negedge clk);if(tx!==1)$fatal(1,"UART stop");received[nr]=rb;nr=nr+1;
end
task byteout;input [7:0] b;integer k;
 begin @(negedge clk);rx=0;repeat(DIV)@(negedge clk);for(k=0;k<8;k=k+1)begin rx=b[k];repeat(DIV)@(negedge clk);end rx=1;repeat(DIV)@(negedge clk);end
endtask
task put;input [7:0] a,d;begin byteout(a);byteout(d);end endtask
task get;input [7:0] a;output [7:0] value;integer prior,t;
 begin prior=nr;put(8'h0f,a);t=0;while(nr<prior+2&&t<DIV*40)begin @(negedge clk);t=t+1;end
 if(nr!=prior+2||received[prior]!==a)$fatal(1,"UART echo/read %h",a);value=received[prior+1];end
endtask
task header;begin put(8'he0,8'ha5);put(8'he1,0);put(8'he2,8'h34);put(8'he3,8'h12);end endtask
task finish;begin put(8'he5,`GOOD_CRC&255);put(8'he6,`GOOD_CRC>>8);put(8'he7,8'h5a);repeat(DIV*180)@(negedge clk);end endtask
task release_lock;begin put(8'he0,8'hc3);get(8'he9,v);if(v[1])$fatal(1,"sandbox failed to release");end endtask
initial begin
 $readmemh("../transport-payload.hex",payload);$readmemh("../config-fast.hex",words);
 repeat(5)@(negedge clk);rst_n=1;repeat(5000)@(negedge clk);
 get(8'hd0,v);if(v!=8'h75)$fatal(1,"configuration capability got=%h endpoint=%h rb=%h",v,dut.cfg_read,dut.rb_addr);get(8'hd1,v);if(v!=1)$fatal(1,"ABI");
 $display("preupload active=%h busy=%b queue=%h own=%b idle=%b",dut.nm_active,dut.nm_busy,dut.uartq_level,dut.own_valid,dut.serial_configuration.receiver.idle_allowed);
 header;for(i=0;i<176;i=i+1)put(8'he4,payload[i]);finish;
 get(8'hd7,v);if(v!=1)$fatal(1,"UART upload rejected %0d",v);get(8'hde,v);if(v!=1)$fatal(1,"publication revision");
 if(dut.u_nm.cfg_enabled!=1)$fatal(1,"UART did not publish slot");release_lock;
 put(8'h37,0);put(8'h00,12);put(8'h60,8'hc5);put(8'h61,12);repeat(512*180)@(negedge clk);
 if(dut.nm_active!=1||dut.u_tdm.env_mem[0]!=32768||dut.u_tdm.epar_mem[0][70:31]!=words[0][87:48]||nonzero==0)$fatal(1,"uploaded configuration not used by PC note");
 if(!SMOKE)begin
  header;repeat(DIV*180)@(negedge clk);get(8'hd7,v);if(v!=6)$fatal(1,"busy accepted upload");release_lock;
 end
 put(8'h60,69);put(8'h61,0);repeat(512*256)@(negedge clk);
 if(dut.nm_active||pcm!=0)$fatal(1,"PC note release");
 if(SMOKE)begin $display("PASS nominal_serial_config DIV=%0d samples=%0d PCM_and_upload_and_release",DIV,samples);$finish;end
 header;for(i=0;i<176;i=i+1)put(8'he4,i==8?payload[i]^8'h80:payload[i]);finish;
 get(8'hd7,v);if(v!=2)$fatal(1,"bad wire CRC accepted");get(8'hde,v);if(v!=1)$fatal(1,"bad CRC changed revision");release_lock;
 header;
 // A missing data byte shifts the pair decoder. A forged ordinary CTRL write
 // must remain isolated, even after the receiver rejects the transaction.
 byteout(8'h00);byteout(8'he4);byteout(8'hab);repeat(DIV*4200)@(negedge clk);
 get(8'h00,v);if(v!=12)$fatal(1,"misaligned upload changed ordinary control");
 get(8'hd0,v);if(v!=8'h75)$fatal(1,"pair decoder did not resync");
 if(!dut.cfg_sandbox)$fatal(1,"failed upload lost sandbox");release_lock;
 header;put(8'he4,payload[0]);repeat(DIV*4200)@(negedge clk);get(8'hd7,v);if(v!=5)$fatal(1,"wire upload timeout");release_lock;
 if(dut.u_nm.table_store.banks[0]!=1||dut.nm_active||dut.u_reg.regs_flat[8'h00*8+:8]!=12)$fatal(1,"failure rollback");
 $display("PASS serial_config DIV=%0d cycles=%0d samples=%0d nonzero=%0d UART_upload_PCM CRC busy truncated_sandbox resync timeout release",DIV,ncycles,samples,nonzero);$finish;
end
initial begin #90000000;$fatal(1,"global timeout");end
endmodule
