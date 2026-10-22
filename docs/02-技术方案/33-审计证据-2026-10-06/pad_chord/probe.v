module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0;
wire[5:0] led; wire tx,di,ws,bck,pa; wire[15:0] pad;
tdm_ship d(.clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.uart_tx_pin(tx),.led(led),.dac_din(di),.dac_ws(ws),.dac_bck(bck),.pa_en(pa),.pad(pad));
initial begin #22 rst_n=1; repeat(500) @(negedge clk);
force d.u_top.pad_state=16'h00ff; repeat(500) @(negedge clk);
$display("8_pad_chord active=%h expected=000000ff seen=%h",d.u_top.nm_active,d.u_top.u_pitch.seen);
$finish; end
endmodule