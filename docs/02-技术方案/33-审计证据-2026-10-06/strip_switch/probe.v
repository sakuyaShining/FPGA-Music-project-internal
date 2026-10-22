module probe;
reg clk=0; always #5 clk=~clk; reg rst_n=0; reg[4:0] cells=0; wire[2:0] pos; wire[4:0] led;
strip_ctrl #(.CLK_HZ(1000),.HOLD_MS(10)) d(clk,rst_n,cells,pos,led);
initial begin #22 rst_n=1; @(negedge clk) cells=1; repeat(9) @(negedge clk); cells=16; repeat(2) @(negedge clk);
$display("switch_after_9_of_10: pos=%0d expected=1 (new cell held only 2 clocks)",pos);
repeat(15) @(negedge clk); cells=4; repeat(15) @(negedge clk);
$display("switch_without_gap: pos=%0d expected=2 after full hold",pos); $finish; end
endmodule