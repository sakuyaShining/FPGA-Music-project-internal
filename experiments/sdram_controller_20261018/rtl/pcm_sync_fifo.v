// Single-clock elastic FIFO. Capacity is exactly 2**AW INCLUDING the head.
// RAM output is the prefetched head; never read and write the same address.
// Consumers may use out_data only while out_valid. Clear discards all entries.
module pcm_sync_fifo #(parameter AW=10,DW=16)(
 input wire clk,rst_n,clear,
 input wire in_valid,output wire in_ready,input wire [DW-1:0] in_data,
 output wire out_valid,input wire out_ready,output wire [DW-1:0] out_data,
 output reg [AW:0] level
);
 localparam [AW:0] CAPACITY={1'b1,{AW{1'b0}}};
 reg [DW-1:0] mem[0:(1<<AW)-1];
 reg [AW-1:0] wp,rp;
 reg head_valid;
 reg [DW-1:0] head_data;
 assign out_valid=rst_n && !clear && head_valid;
 wire pop=out_valid && out_ready;
 assign in_ready=rst_n && !clear && ((level<CAPACITY)||pop);
 wire push=in_valid && in_ready;
 wire fetch=rst_n && !clear && (!head_valid || out_ready) &&
            ((level>1)||((level!=0)&&!head_valid));
 always @(posedge clk)begin
  if(push)mem[wp]<=in_data;
  if(fetch)head_data<=mem[rp];
 end
 assign out_data=head_data;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin wp<=0;rp<=0;level<=0;head_valid<=0;end
  else if(clear)begin wp<=0;rp<=0;level<=0;head_valid<=0;end
  else begin
   if(push)wp<=wp+1'b1;
   if(fetch)rp<=rp+1'b1;
   if(fetch)head_valid<=1'b1;else if(pop)head_valid<=1'b0;
   case({push,pop})
    2'b10:level<=level+1'b1;
    2'b01:level<=level-1'b1;
    default:;
   endcase
  end
 end
endmodule
