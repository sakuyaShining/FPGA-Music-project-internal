// Transport primitive only: no file format, start/stop UI, mix or media backend.
// All ports use clk. Backends must quiesce/drain old transactions before clear
// and starting a new session; clear is NOT cancellation of external requests.
module pcm_storage_buffers #(parameter AW=10)(
 input wire clk,rst_n,
 input wire rec_clear,rec_enable,pcm_valid,input wire [15:0] pcm_data,
 output wire rec_valid,input wire rec_ready,output wire [15:0] rec_data,
 output wire [AW:0] rec_level,output reg rec_overflow,
 input wire play_clear,play_enable,sample_tick,
 input wire feed_valid,output wire feed_ready,input wire [15:0] feed_data,
 output reg play_valid,output reg [15:0] play_data,
 output wire [AW:0] play_level,output reg play_underflow,output reg play_miss
);
 wire capture_ready;
 // Preserve a contiguous prefix on overflow. Queued data can still drain.
 // Recovery requires rec_clear; never silently resume a file with a hole.
 pcm_sync_fifo #(.AW(AW)) recording(
  .clk(clk),.rst_n(rst_n),.clear(rec_clear),
  .in_valid(rec_enable && pcm_valid && !rec_overflow),.in_ready(capture_ready),.in_data(pcm_data),
  .out_valid(rec_valid),.out_ready(rec_ready),.out_data(rec_data),.level(rec_level));
 wire queued_valid;wire [15:0] queued_data;
 wire request=play_enable && sample_tick;
 pcm_sync_fifo #(.AW(AW)) playback(
  .clk(clk),.rst_n(rst_n),.clear(play_clear),
  .in_valid(feed_valid),.in_ready(feed_ready),.in_data(feed_data),
  .out_valid(queued_valid),.out_ready(request),.out_data(queued_data),.level(play_level));
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin rec_overflow<=0;play_underflow<=0;play_valid<=0;play_data<=0;play_miss<=0;end
  else begin
   if(rec_clear)rec_overflow<=0;
   else if(rec_enable && pcm_valid && !capture_ready)rec_overflow<=1;
   play_valid<=0;play_miss<=0;
   if(play_clear)begin play_underflow<=0;play_data<=0;end
   else if(request)begin
    if(queued_valid)begin play_data<=queued_data;play_valid<=1;end
    else begin play_underflow<=1;play_miss<=1;end
   end
  end
 end
endmodule
