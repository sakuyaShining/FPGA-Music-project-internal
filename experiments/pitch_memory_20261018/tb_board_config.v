`timescale 1ns/1ps
`include "transport_fixture.vh"
module tb_board_config;
parameter DIV=16,SMOKE=0,DUAL=0;
reg clk=0;always #5 clk=~clk;reg rst_n=0,rx=1;wire tx;tri [15:0] pad;
wire pcm_valid;wire signed [23:0] pcm;
board_config_top #(.UART_BAUD(27000000/DIV),.WARM_CYCLES(6000),.DIAG_CAPTURE_SAMPLES(64)) dut(
 .clk(clk),.reset_button(!rst_n),.uart_rx_pin(rx),.uart_tx_pin(tx));
assign pcm_valid=dut.pcm_valid;assign pcm=dut.pcm;
defparam dut.core.serial_configuration.receiver.QUIET_CYCLES=DIV*160;
defparam dut.core.serial_configuration.receiver.TIMEOUT_CYCLES=DIV*4000;
reg [7:0] payload[0:175];reg [87:0] words[0:15];reg [7:0] received[0:4095];integer nr=0,bitno,i,j,start,ncycles=0,samples=0,nonzero=0,lastsample=-1;reg [7:0] rb,v;
always @(posedge clk)if(!dut.rst_n)lastsample=-1;else begin
 ncycles=ncycles+1;
 if(!dut.warm&&(dut.pa_en!==0||dut.dac_din!==0))$fatal(1,"warmup audio leaked");
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
 get(8'hc0,v);if(v!=8'h72)$fatal(1,"diagnostic identity");get(8'hc2,v);if(v!=8'h76)$fatal(1,"wrapper identity");
 get(8'hd0,v);if(v!=8'h75)$fatal(1,"configuration capability got=%h endpoint=%h rb=%h",v,dut.core.cfg_read,dut.core.rb_addr);get(8'hd1,v);if(v!=1)$fatal(1,"ABI");
 $display("preupload active=%h busy=%b queue=%h own=%b idle=%b",dut.core.nm_active,dut.core.nm_busy,dut.core.uartq_level,dut.core.own_valid,dut.core.serial_configuration.receiver.idle_allowed);
 header;for(i=0;i<176;i=i+1)put(8'he4,payload[i]);finish;
 get(8'hd7,v);if(v!=1)$fatal(1,"UART upload rejected %0d",v);get(8'hde,v);if(v!=1)$fatal(1,"publication revision");
 if(dut.core.u_nm.cfg_enabled!=1)$fatal(1,"UART did not publish slot");release_lock;
 put(8'h37,0);put(8'h00,12);put(8'h60,8'hc5);put(8'h61,12);repeat(512*180)@(negedge clk);
 if(dut.core.nm_active!=1||dut.core.u_tdm.env_mem[0]!=32768||dut.core.u_tdm.epar_mem[0][70:31]!=words[0][87:48]||nonzero==0)$fatal(1,"uploaded configuration not used by PC note");
 if(!SMOKE)begin
  header;repeat(DIV*180)@(negedge clk);get(8'hd7,v);if(v!=6)$fatal(1,"busy accepted upload");release_lock;
 end
 put(8'h60,69);put(8'h61,0);repeat(512*256)@(negedge clk);
 if(dut.core.nm_active||pcm!=0)$fatal(1,"PC note release");
 // Active-note S2 reset must mute immediately, scrub old voices and clear slots.
 put(8'h60,8'hc5);put(8'h61,12);repeat(512*60)@(negedge clk);
 if(dut.core.nm_active!=1)$fatal(1,"reset test has no held note");
 @(negedge clk);rst_n=0;repeat(5)@(negedge clk);
 if(dut.rst_n||dut.pa_en||dut.dac_din)$fatal(1,"S2 reset assertion/mute");
 rst_n=1;repeat(7000)@(negedge clk);
 if(!dut.warm||dut.core.nm_active||pcm!=0||dut.core.u_nm.cfg_enabled||dut.core.serial_configuration.receiver.revision)$fatal(1,"reset did not clear note/configuration");
 $display("reset scrub slot0 env=%h gate=%b amp=%h pending=%b",dut.core.u_tdm.env_mem[0],dut.core.u_tdm.gcur_mem[0],dut.core.u_tdm.amp_mem[0],dut.core.u_tdm.pv_mem[0]);
 for(j=0;j<512;j=j+1)if(dut.core.u_tdm.gcur_mem[j]||dut.core.u_tdm.amp_mem[j]||dut.core.u_tdm.pv_mem[j])$fatal(1,"reset slot leaked %0d",j);
 header;for(i=0;i<176;i=i+1)put(8'he4,payload[i]);finish;
 get(8'hd7,v);if(v!=1)$fatal(1,"upload after reset");release_lock;
 put(8'h37,0);put(8'h00,12);put(8'h60,8'hc5);put(8'h61,12);repeat(512*60)@(negedge clk);
 if(dut.core.nm_active!=1||pcm==0)$fatal(1,"play after reset failed");
 put(8'h60,69);put(8'h61,0);repeat(512*256)@(negedge clk);
 if(dut.core.nm_active||pcm!=0||dut.dac_din!==0)$fatal(1,"final stop not silent");
 if(SMOKE)begin $display("PASS nominal_board_config S2_scrub_reupload warm_gate DIV=%0d samples=%0d PCM_and_upload_and_release",DIV,samples);$finish;end
 header;for(i=0;i<176;i=i+1)put(8'he4,i==8?payload[i]^8'h80:payload[i]);finish;
 get(8'hd7,v);if(v!=2)$fatal(1,"bad wire CRC accepted");get(8'hde,v);if(v!=1)$fatal(1,"bad CRC changed revision");release_lock;
 header;
 // A missing data byte shifts the pair decoder. A forged ordinary CTRL write
 // must remain isolated, even after the receiver rejects the transaction.
 byteout(8'h00);byteout(8'he4);byteout(8'hab);repeat(DIV*4200)@(negedge clk);
 get(8'h00,v);if(v!=12)$fatal(1,"misaligned upload changed ordinary control");
 get(8'hd0,v);if(v!=8'h75)$fatal(1,"pair decoder did not resync");
 if(!dut.core.cfg_sandbox)$fatal(1,"failed upload lost sandbox");release_lock;
 header;put(8'he4,payload[0]);repeat(DIV*4200)@(negedge clk);get(8'hd7,v);if(v!=5)$fatal(1,"wire upload timeout");release_lock;
 if(dut.core.u_nm.table_store.banks[0]!=1||dut.core.nm_active||dut.core.u_reg.regs_flat[8'h00*8+:8]!=12)$fatal(1,"failure rollback");
 $display("PASS board_config S2_scrub_reupload warm_gate DIV=%0d cycles=%0d samples=%0d nonzero=%0d UART_upload_PCM CRC busy truncated_sandbox resync timeout release",DIV,ncycles,samples,nonzero);$finish;
end
initial begin #90000000;$fatal(1,"global timeout");end
endmodule
