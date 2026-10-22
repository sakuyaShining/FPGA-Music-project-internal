`timescale 1ns/1ps
module tb_board;
 parameter real ACCESS_DELAY=3.0;
 localparam DIV=16;
 reg clk=0;always #18.519 clk=~clk;reg button=1;
 wire tx,sc,cke,cs,ras,cas,we,pa,di,ws,bck;wire[5:0] led;
 wire[10:0] addr;wire[1:0] bank;wire[3:0] mask;tri[31:0] dq;
 wire[31:0] refreshes,reads,writes,maxgap;
 sdram_board_top #(.ADDR_BITS(5),.UART_BAUD(27000000/DIV),.HEARTBEAT(4000)) dut(
 .clk(clk),.reset_button(button),.uart_tx_pin(tx),.led(led),.dac_din(di),.dac_ws(ws),.dac_bck(bck),.pa_en(pa),
 .O_sdram_clk(sc),.O_sdram_cke(cke),.O_sdram_cs_n(cs),.O_sdram_ras_n(ras),.O_sdram_cas_n(cas),.O_sdram_wen_n(we),
 .O_sdram_addr(addr),.O_sdram_ba(bank),.O_sdram_dqm(mask),.IO_sdram_dq(dq));
 sdram_timing_model #(.ACCESS_DELAY(ACCESS_DELAY)) model(sc,cke,cs,ras,cas,we,addr,bank,mask,dq,dut.initialized,refreshes,reads,writes,maxgap);
 integer cycles=0,frames=0,k,n=0,j,goodpass=0;reg[7:0] bytes[0:15];reg[7:0] v,checksum;
 always @(posedge clk)begin
  cycles=cycles+1;if({pa,di,ws,bck}!==4'd0)$fatal(1,"diagnostic audio not muted");
 end
 initial forever begin
  fork: receive_or_reset
  begin
  @(negedge tx);repeat(DIV/2)@(negedge clk);
  for(k=0;k<8;k=k+1)begin repeat(DIV)@(negedge clk);v[k]=tx;end
  repeat(DIV)@(negedge clk);
  if(tx!==1)$fatal(1,"UART stop");
  bytes[n]=v;n=n+1;
  if(n==16)begin
   if(bytes[0]!==8'ha5||bytes[1]!==8'h81||bytes[2]!==1)$fatal(1,"frame identity/alignment");
   checksum=0;for(j=0;j<15;j=j+1)checksum=checksum^bytes[j];
   if(checksum!==bytes[15])$fatal(1,"torn UART snapshot");
   if(bytes[3][0])goodpass=goodpass+1;
   frames=frames+1;n=0;
  end
  end
  begin @(negedge dut.rst_n);n=0;end
  join_any
  disable receive_or_reset;
 end
 initial begin
  repeat(4)@(negedge clk);button=0;
  while(dut.state!=5&&dut.state!=6&&cycles<20000)@(negedge clk);
  if(ACCESS_DELAY>=18.519)begin
   if(dut.state!=6)$fatal(1,"late data did not trigger BIST failure");
   $display("PASS late-return negative case ACCESS=%0f BIST rejected data cycles=%0d",ACCESS_DELAY,cycles);$finish;
  end
  if(dut.state!=5||dut.completed!=128)$fatal(1,"BIST sweep/count");
  repeat(12000)@(negedge clk);
  if(frames<2||goodpass==0)$fatal(1,"UART pass snapshot missing");
  // S2 active-high: abort and reinitialize while a transaction is in flight.
  button=1;repeat(4)@(negedge clk);button=0;
  while(dut.state!=2)@(negedge clk);
  repeat(2)@(negedge clk);button=1;repeat(4)@(negedge clk);
  if(dut.rst_n||dut.completed||dut.ram.rsp_valid)$fatal(1,"reset abort");
  button=0;while(dut.state!=5&&dut.state!=6)@(negedge clk);
  if(dut.state!=5||dut.completed!=128)$fatal(1,"reinitialized sweep failed");
  $display("PASS board wrapper ACCESS=%0f cycles=%0d frames=%0d UART_snapshot S2_abort_reinit two_patterns 128_operations muted",ACCESS_DELAY,cycles,frames);$finish;
 end
 initial begin #3000000;$fatal(1,"timeout");end
endmodule
