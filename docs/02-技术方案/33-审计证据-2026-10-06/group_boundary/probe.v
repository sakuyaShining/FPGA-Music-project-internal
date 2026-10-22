module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0; reg le=0; reg[8:0] ls=0;
wire[5:0] led; wire tx,di,ws,bck,pa; wire[15:0] pad;
tdm_ship d(.clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.uart_tx_pin(tx),.led(led),.dac_din(di),.dac_ws(ws),.dac_bck(bck),.pa_en(pa),.pad(pad));
integer epoch=0; integer j;
always @(posedge clk) if(rst_n) begin
 if(d.u_top.u_tdm.sc==511) epoch=epoch+1;
 if(d.u_top.u_tdm.consume && d.u_top.u_tdm.sl1<16) $display("consume slot=%0d epoch=%0d ppr1=%0d pp1=%0d",d.u_top.u_tdm.sl1,epoch,d.u_top.u_tdm.ppr1,d.u_top.u_tdm.pp1);
end
initial begin
force d.u_top.nm_load_en=le; force d.u_top.nm_load_slot=ls;
force d.u_top.nm_load_inc=24'd100000; force d.u_top.nm_load_amp=8'd200;
force d.u_top.nm_load_gate=1'b1; force d.u_top.nm_load_epar=23'd3831924;
#22 rst_n=1; repeat(600) @(negedge clk); wait(d.u_top.u_tdm.sc==504);
@(negedge clk); le=1; for(j=0;j<16;j=j+1) begin ls=j; @(negedge clk); end le=0;
repeat(1200) @(negedge clk); $finish; end
endmodule