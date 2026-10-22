`timescale 1ns/1ps
module tb_board;
 parameter real ACCESS_DELAY=3.0;
 reg clk=0,reset_button=1;always #18.5185 clk=~clk;
 wire uart;wire [5:0] led;wire din,ws,bck,pa,sclk,cke,cs,ras,cas,we;
 wire [10:0] addr;wire [1:0] bank;wire [3:0] mask;wire [31:0] dq;
 sdram_board_top #(.FIFO_AW(2),.RING_AW(3),.NORMAL_SAMPLES(48),.RECOVERY_SAMPLES(24),.PREFILL(4),.HOLD_TICKS(4),
 .HEARTBEAT(8000),.UART_BAUD(3375000),.WATCHDOG(300000)) dut(.clk(clk),.reset_button(reset_button),.uart_tx_pin(uart),.led(led),
 .dac_din(din),.dac_ws(ws),.dac_bck(bck),.pa_en(pa),.O_sdram_clk(sclk),.O_sdram_cke(cke),.O_sdram_cs_n(cs),
 .O_sdram_ras_n(ras),.O_sdram_cas_n(cas),.O_sdram_wen_n(we),.O_sdram_addr(addr),.O_sdram_ba(bank),.O_sdram_dqm(mask),.IO_sdram_dq(dq));
 integer refs,reads,writes,gap,cycles=0,frames=0,resets=0,fd;
 sdram_timing_model #(.ACCESS_DELAY(ACCESS_DELAY)) memory(.clk(sclk),.cke(cke),.cs_n(cs),.ras_n(ras),.cas_n(cas),.we_n(we),
 .addr(addr),.ba(bank),.dqm(mask),.dq(dq),.operational(dut.initialized),.refreshes(refs),.reads(reads),.writes(writes),.max_refresh_gap(gap));
 initial begin
  fd=$fopen("board-frames.hex","w");repeat(4)@(negedge clk);reset_button=0;
  wait(dut.state==6&&dut.hold_count==5);@(negedge clk);reset_button=1;resets=1;
  repeat(3)@(negedge clk);reset_button=0;
 end
 always @(posedge clk)begin
  cycles=cycles+1;
  if({din,ws,bck,pa}!==4'b0)$fatal(1,"audio not muted");
  if(!reset_button&&dut.rst_n&&dut.state==19)$fatal(1,"bench failed code=%0d index=%0d got=%h expected=%h state=%0d tests=%h",dut.error_code,dut.failure_index,dut.observed,dut.expected,dut.state,dut.tests);
 end
 task byte_receive;output[7:0] value;integer j;
  begin
   @(negedge uart);repeat(12)@(posedge clk);
   for(j=0;j<8;j=j+1)begin value[j]=uart;repeat(8)@(posedge clk);end
   if(uart!==1'b1)$fatal(1,"UART stop bit");
  end
 endtask
 reg [7:0] b[0:63],check;integer i;reg aborted;
 initial forever begin
  wait(dut.rst_n);aborted=0;
  fork:frame_or_reset
   begin
    for(i=0;i<64;i=i+1)byte_receive(b[i]);
   end
   begin @(negedge dut.rst_n);aborted=1;end
  join_any
  disable frame_or_reset;
  if(!aborted)begin
   check=0;for(i=0;i<64;i=i+1)check=check^b[i];
   if(b[0]!=8'ha5||b[1]!=8'h83||b[2]!=1||check!=0)$fatal(1,"frame identity/checksum");
   for(i=0;i<64;i=i+1)$fwrite(fd,"%02x",b[i]);$fwrite(fd,"\n");frames=frames+1;
   if(b[4]&2)$fatal(1,"reported failure");
   if(b[4]&1)begin
    if(resets!=1||b[3]!=18||b[5]!=8'h3f||dut.prefix_count!=13||dut.misses!=8||dut.clear_count!=6||dut.inflight_clears!=1||dut.hold_count!=32)
     $fatal(1,"final metrics resets=%0d state=%0d tests=%h prefix=%0d misses=%0d clears=%0d inflight=%0d held=%0d",resets,b[3],b[5],dut.prefix_count,dut.misses,dut.clear_count,dut.inflight_clears,dut.hold_count);
    $display("PASS stage83 wrapper cycles=%0d frames=%0d reset_inflight=%0d masks=%h rec=%0d played=%0d after_stop=%0d prefix=%0d miss=%0d clears=%0d held=%0d inflight=%0d SDRAM_ref=%0d gap=%0d",cycles,frames,resets,dut.tests,dut.rec_read,dut.played,dut.after_stop,dut.prefix_count,dut.misses,dut.clear_count,dut.hold_count,dut.inflight_clears,refs,gap);
    $fclose(fd);$finish;
   end
  end
 end
 initial begin #15000000;$fatal(1,"simulation watchdog");end
endmodule
