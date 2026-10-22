// Single-clock bridge: live PCM -> short FIFO -> recording SDRAM ring -> host;
// host -> playback SDRAM ring -> short FIFO -> sample consumer. No file/mixer.
// Stop rec_enable stops capture, queued data continues draining. play_enable
// controls sample consumption only; prefetch can continue while paused.
module pcm_sdram_stream #(parameter FIFO_AW=10,RING_AW=17)(
 input wire clk,rst_n,
 input wire rec_clear,play_clear,
 output wire rec_clear_ready,play_clear_ready,rec_clear_done,play_clear_done,
 output wire rec_clearing,play_clearing,
 input wire rec_enable,pcm_valid,input wire [15:0] pcm_data,
 output wire rec_valid,input wire rec_ready,output wire [15:0] rec_data,
 output wire [FIFO_AW:0] rec_level,play_level,
 output wire [RING_AW:0] rec_ring_level,play_ring_level,
 output wire rec_overflow,
 input wire play_enable,sample_tick,
 input wire feed_valid,output wire feed_ready,input wire [15:0] feed_data,
 output wire play_valid,output wire [15:0] play_data,
 output wire play_underflow,play_miss,
 output wire mem_req_valid,input wire mem_req_ready,output wire mem_req_write,
 output wire [21:0] mem_req_addr,output wire [15:0] mem_req_data,
 input wire mem_rsp_valid,output wire mem_rsp_ready,input wire [15:0] mem_rsp_data,
 output wire mem_busy
);
 wire fifo_rec_valid,fifo_rec_ready,fifo_feed_valid,fifo_feed_ready;
 wire [15:0] fifo_rec_data,fifo_feed_data;
 wire host_rec_valid,host_feed_ready;
 wire buffered_play_valid,buffered_play_miss;
 // Suppress all handshakes on the clear request edge as well as pending/done.
 assign rec_valid=host_rec_valid && !rec_clearing;
 assign feed_ready=host_feed_ready && !play_clearing;
 assign play_valid=buffered_play_valid;
 assign play_miss=buffered_play_miss && !play_clearing;
 pcm_storage_buffers #(.AW(FIFO_AW)) buffers(.clk(clk),.rst_n(rst_n),
  .rec_clear(rec_clear_done),.rec_enable(rec_enable && !rec_clearing),.pcm_valid(pcm_valid),.pcm_data(pcm_data),
  .rec_valid(fifo_rec_valid),.rec_ready(fifo_rec_ready),.rec_data(fifo_rec_data),.rec_level(rec_level),.rec_overflow(rec_overflow),
  .play_clear(play_clear_done),.play_enable(play_enable && !play_clearing),.sample_tick(sample_tick),
  .feed_valid(fifo_feed_valid && !play_clearing),.feed_ready(fifo_feed_ready),.feed_data(fifo_feed_data),
  .play_valid(buffered_play_valid),.play_data(play_data),.play_level(play_level),.play_underflow(play_underflow),.play_miss(buffered_play_miss));
 pcm_sdram_arbiter #(.AW(RING_AW)) arbiter(.clk(clk),.rst_n(rst_n),
  .rec_clear_valid(rec_clear),.play_clear_valid(play_clear),.rec_clear_ready(rec_clear_ready),.play_clear_ready(play_clear_ready),
  .rec_clear_done(rec_clear_done),.play_clear_done(play_clear_done),.rec_clearing(rec_clearing),.play_clearing(play_clearing),
  .rec_in_valid(fifo_rec_valid),.rec_in_ready(fifo_rec_ready),.rec_in_data(fifo_rec_data),
  .rec_out_valid(host_rec_valid),.rec_out_ready(rec_ready && !rec_clearing),.rec_out_data(rec_data),
  .play_in_valid(feed_valid),.play_in_ready(host_feed_ready),.play_in_data(feed_data),
  .play_out_valid(fifo_feed_valid),.play_out_ready(fifo_feed_ready && !play_clearing),.play_out_data(fifo_feed_data),
  .rec_level(rec_ring_level),.play_level(play_ring_level),
  .mem_req_valid(mem_req_valid),.mem_req_ready(mem_req_ready),.mem_req_write(mem_req_write),
  .mem_req_addr(mem_req_addr),.mem_req_data(mem_req_data),.mem_rsp_valid(mem_rsp_valid),.mem_rsp_ready(mem_rsp_ready),.mem_rsp_data(mem_rsp_data),.busy(mem_busy));
endmodule
