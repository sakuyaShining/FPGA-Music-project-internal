from pathlib import Path
P=Path(__file__).resolve().parents[2];R=P/'experiments/envelope_resources_20261017'
s=(R/'tb_serial_config.v').read_text(encoding='utf-8').replace('module tb_serial_config;','module tb_board_config;')
a=s.index('tdm_top_owned #(');b=s.index('defparam',a)
s=s[:a]+'''board_config_top #(.UART_BAUD(27000000/DIV),.WARM_CYCLES(6000),.DIAG_CAPTURE_SAMPLES(64)) dut(
 .clk(clk),.reset_button(!rst_n),.uart_rx_pin(rx),.uart_tx_pin(tx));
assign pcm_valid=dut.pcm_valid;assign pcm=dut.pcm;
'''+s[b:]
s=s.replace('dut.serial_configuration','dut.core.serial_configuration').replace('dut.cfg_read','dut.core.cfg_read').replace('dut.rb_addr','dut.core.rb_addr')
for name in ('nm_active','nm_busy','uartq_level','own_valid','u_nm','u_tdm','cfg_sandbox','u_reg'):
 s=s.replace('dut.'+name,'dut.core.'+name)
s=s.replace('always @(posedge clk)if(rst_n)begin','always @(posedge clk)if(!dut.rst_n)lastsample=-1;else begin')
s=s.replace(' if(pcm_valid)begin',' if(!dut.warm&&(dut.pa_en!==0||dut.dac_din!==0))$fatal(1,"warmup audio leaked");\n if(pcm_valid)begin',1)
s=s.replace(" get(8'hd0,v);", " get(8'hc0,v);if(v!=8'h72)$fatal(1,\"diagnostic identity\");get(8'hc2,v);if(v!=8'h76)$fatal(1,\"wrapper identity\");\n get(8'hd0,v);",1)
reset=''' // Active-note S2 reset must mute immediately, scrub old voices and clear slots.
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
'''
s=s.replace(' if(SMOKE)begin',reset+' if(SMOKE)begin',1)
# The negative scenarios also run after the reset's fresh revision1 commit.
s=s.replace('PASS nominal_serial_config','PASS nominal_board_config S2_scrub_reupload warm_gate').replace('PASS serial_config','PASS board_config S2_scrub_reupload warm_gate')
(R/'tb_board_config.v').write_text(s,encoding='utf-8')
print('Prepared explicit board-wrapper fixture; originals untouched')
