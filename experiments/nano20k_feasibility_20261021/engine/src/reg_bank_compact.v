// Stage78: full 128-byte synchronous readback in RAM, selected live mirrors.
// No reset on parameter memory/mirrors. Read is one edge, read-before-write.
// Unselected flat bytes are intentionally zero and must have no consumers.
`timescale 1ns/1ps
module reg_bank_compact #(
 parameter [127:0] FLAT_MASK=128'h000b78011c1f03ff00ff000000000001
)(
 input wire clk,rst_n,wr_en,
 input wire [7:0] wr_addr,wr_data,
 input wire rd_en,
 input wire [7:0] rd_addr,
 output wire [7:0] rd_data,
 output wire [1023:0] regs_flat
);
 localparam [1023:0] DEFAULTS=1024'h110000000000000000000000000000000000000000000000000000000000000000000070000200000000008000027c000000000000000380004001ae6005dc0100000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002;
 reg [7:0] mem[0:127];
 genvar g;
 generate for(g=0;g<128;g=g+1)begin: BYTES
  initial mem[g]=DEFAULTS[g*8+:8];
  if(FLAT_MASK[g])begin: LIVE
   reg [7:0] value;
   initial value=DEFAULTS[g*8+:8];
   always @(posedge clk) if(wr_en && wr_addr==g) value<=wr_data;
   assign regs_flat[g*8+:8]=value;
  end else begin: UNUSED
   assign regs_flat[g*8+:8]=8'd0;
  end
 end endgenerate
 always @(posedge clk) if(wr_en && !wr_addr[7]) mem[wr_addr[6:0]]<=wr_data;
 // Keep asynchronous output reset outside the RAM primitive. The RAM itself
 // is never reset. Out-of-range reads preserve the reference simulation X.
 reg [7:0] read_raw;
 reg read_valid;
 always @(posedge clk) if(rd_en)begin
  if(!rd_addr[7]) read_raw<=mem[rd_addr[6:0]];
  else read_raw<=8'hxx;
 end
 always @(posedge clk or negedge rst_n)
  if(!rst_n) read_valid<=1'b0;
  else if(rd_en) read_valid<=1'b1;
 assign rd_data=read_valid ? read_raw : 8'd0;
endmodule
