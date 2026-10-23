// Diagnostic scan history: MAC registers store active controls, a circular
// block RAM preserves the optional configuration span's exact serial delay.
// Parallel views of that span remain ordinary FFs; unused views are optimized
// away in the serial-configuration timing harness, but remain correct if used.
module probe_scan_store #(parameter WIDTH=587,HARD_WORDS=6,GAP_START=26,GAP_SIZE=0)(
 input wire clk,din,output wire [WIDTH-1:0] q
);
 localparam ACTIVE=WIDTH-GAP_SIZE,HARD_BITS=HARD_WORDS*54;
 wire [ACTIVE-1:0] active_q;
 wire [ACTIVE-1:0] active_next;
 wire gap_out;
 genvar i;
 generate for(i=0;i<ACTIVE;i=i+1)begin: serial_wiring
  if(i==0)assign active_next[i]=din;
  else if(GAP_SIZE>0 && i==GAP_START)assign active_next[i]=gap_out;
  else assign active_next[i]=active_q[i-1];
 end endgenerate
 generate if(GAP_SIZE>0)begin: gap
  localparam AW=$clog2(GAP_SIZE),DEPTH=1<<AW;
  reg memory[0:DEPTH-1] /* synthesis syn_ramstyle="block_ram" */;
  reg [AW-1:0] pointer=0;
  wire [AW-1:0] read_address=pointer-(GAP_SIZE-1);
  reg delay_q;
  reg [GAP_SIZE-2:0] parallel_view;
  integer j;
  initial for(j=0;j<DEPTH;j=j+1)memory[j]=0;
  always @(posedge clk)begin
   memory[pointer]<=active_q[GAP_START-1];
   delay_q<=memory[read_address];
   pointer<=pointer+1'b1;
   parallel_view<={parallel_view[GAP_SIZE-3:0],active_q[GAP_START-1]};
  end
  assign gap_out=delay_q;
  assign q={active_q[ACTIVE-1:GAP_START],gap_out,parallel_view,active_q[GAP_START-1:0]};
 end else begin: no_gap
  assign gap_out=1'b0;
  assign q=active_q;
 end endgenerate
 genvar k;
 generate for(k=0;k<HARD_WORDS;k=k+1)begin: hard_register
  MULTALU18X18 #(.AREG(1'b0),.BREG(1'b0),.CREG(1'b0),.DREG(1'b0),
   .ASIGN_REG(1'b0),.BSIGN_REG(1'b0),.DSIGN_REG(1'b0),.ACCLOAD_REG0(1'b0),.ACCLOAD_REG1(1'b0),
   .OUT_REG(1'b1),.PIPE_REG(1'b0),.B_ADD_SUB(1'b0),.C_ADD_SUB(1'b0),
   .MULTALU18X18_MODE(0),.MULT_RESET_MODE("SYNC")) cell_register(
   .DOUT(active_q[k*54+:54]),.CASO(),.A(18'd0),.B(18'd0),.C(active_next[k*54+:54]),.D(54'd0),.CASI(55'd0),
   .ACCLOAD(1'b0),.ASIGN(1'b0),.BSIGN(1'b0),.DSIGN(1'b0),.CLK(clk),.CE(1'b1),.RESET(1'b0));
 end endgenerate
 generate if(ACTIVE>HARD_BITS)begin: tail
  reg [ACTIVE-HARD_BITS-1:0] bits;
  always @(posedge clk)bits<=active_next[ACTIVE-1:HARD_BITS];
  assign active_q[ACTIVE-1:HARD_BITS]=bits;
 end endgenerate
endmodule
