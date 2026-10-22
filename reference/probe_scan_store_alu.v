// Diagnostic scan storage only. Six ALU output registers replace 324 ordinary
// FFs; A+0, accumulator off, OUT_REG=1 gives exactly one clock of delay.
// This consumes spare DSP resources in the timing harness, not the music core.
module probe_scan_store #(parameter WIDTH=587,HARD_WORDS=6)(
 input wire clk,din,output wire [WIDTH-1:0] q
);
 localparam HARD_BITS=HARD_WORDS*54;
 wire [WIDTH-1:0] next={q[WIDTH-2:0],din};
 genvar k;
 generate for(k=0;k<HARD_WORDS;k=k+1)begin: hard_register
  ALU54D #(.AREG(1'b0),.BREG(1'b0),.ASIGN_REG(1'b0),.BSIGN_REG(1'b0),
   .ACCLOAD_REG(1'b0),.OUT_REG(1'b1),.B_ADD_SUB(1'b0),.C_ADD_SUB(1'b0),
   .ALUD_MODE(0),.ALU_RESET_MODE("SYNC")) cell_register(
   .DOUT(q[k*54+:54]),.CASO(),.A(next[k*54+:54]),.B(54'd0),.CASI(55'd0),
   .ACCLOAD(1'b0),.ASIGN(1'b0),.BSIGN(1'b0),.CLK(clk),.CE(1'b1),.RESET(1'b0));
 end endgenerate
 generate if(WIDTH>HARD_BITS)begin: tail
  reg [WIDTH-HARD_BITS-1:0] bits;
  always @(posedge clk)bits<=next[WIDTH-1:HARD_BITS];
  assign q[WIDTH-1:HARD_BITS]=bits;
 end endgenerate
endmodule
