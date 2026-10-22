// RAM-only diagnostic. Automatic volatile-RAM sweeps; no Flash/TF access.
// Exact O_sdram*/IO_sdram* names are the vendor embedded-SDRAM interface.
module sdram_board_top #(parameter ADDR_BITS=22,UART_BAUD=115200,HEARTBEAT=27000000)(
 input wire clk,reset_button,
 output wire uart_tx_pin,output wire [5:0] led,
 output wire dac_din,dac_ws,dac_bck,pa_en,
 output wire O_sdram_clk,O_sdram_cke,O_sdram_cs_n,
 output wire O_sdram_ras_n,O_sdram_cas_n,O_sdram_wen_n,
 output wire [10:0] O_sdram_addr,output wire [1:0] O_sdram_ba,
 output wire [3:0] O_sdram_dqm,inout wire [31:0] IO_sdram_dq
);
 reg [1:0] reset_release=0;
 always @(posedge clk or posedge reset_button)
  if(reset_button)reset_release<=0;else reset_release<={reset_release[0],1'b1};
 wire rst_n=reset_release[1];
 assign dac_din=0;assign dac_ws=0;assign dac_bck=0;assign pa_en=0;
 localparam BOOT=0,WREQ=1,WWAIT=2,RREQ=3,RWAIT=4,PASS=5,FAIL=6;
 reg [2:0] state;
 reg [21:0] index;
 reg phase;
 reg [15:0] observed,expected;
 reg [24:0] completed;
 wire ready,valid,initialized;wire [15:0] response;
 wire last=index==((1<<ADDR_BITS)-1);
 function [15:0] pattern;input[21:0] a;input p;
  begin pattern=a[15:0]^{10'd0,a[21:16]}^(p?16'h5aa5:16'ha55a);end
 endfunction
 sdram_word_controller ram(.clk(clk),.rst_n(rst_n),.req_valid(state==WREQ||state==RREQ),
  .req_ready(ready),.req_write(state==WREQ),.req_addr(index),.req_data(pattern(index,phase)),
  .rsp_valid(valid),.rsp_ready(1'b1),.rsp_data(response),.init_done(initialized),
  .sd_clk(O_sdram_clk),.sd_cke(O_sdram_cke),.sd_cs_n(O_sdram_cs_n),
  .sd_ras_n(O_sdram_ras_n),.sd_cas_n(O_sdram_cas_n),.sd_we_n(O_sdram_wen_n),
  .sd_addr(O_sdram_addr),.sd_bank(O_sdram_ba),.sd_dqm(O_sdram_dqm),.sd_dq(IO_sdram_dq));
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin state<=BOOT;index<=0;phase<=0;observed<=0;expected<=0;completed<=0;end
  else case(state)
   BOOT:if(initialized)state<=WREQ;
   WREQ:if(ready)state<=WWAIT;
   WWAIT:if(valid)begin
    completed<=completed+1'b1;
    if(last)begin index<=0;state<=RREQ;end else begin index<=index+1'b1;state<=WREQ;end
   end
   RREQ:if(ready)state<=RWAIT;
   RWAIT:if(valid)begin
    completed<=completed+1'b1;observed<=response;expected<=pattern(index,phase);
    if(response!==pattern(index,phase))state<=FAIL;
    else if(last)begin
     if(phase)state<=PASS;
     else begin phase<=1;index<=0;state<=WREQ;end
    end else begin index<=index+1'b1;state<=RREQ;end
   end
   default:;
  endcase
 end
 assign led=~{state==FAIL,state==PASS,phase,initialized,rst_n,state==WREQ||state==RREQ};
 localparam HW=$clog2(HEARTBEAT+1);
 reg [HW-1:0] heartbeat;
 reg [127:0] frame;
 reg [4:0] byte_index;
 reg transmitting,start;
 wire done,busy;
 reg [7:0] tx_byte;
 reg [127:0] snapshot;
 reg [7:0] checksum;
 integer k;
 always @*begin
  snapshot=0;snapshot[0+:8]=8'ha5;snapshot[8+:8]=8'h81;snapshot[16+:8]=1;
  snapshot[24+:8]={2'd0,state,initialized,state==FAIL,state==PASS};
  snapshot[32+:8]={6'd0,completed[24],phase};snapshot[40+:24]={2'd0,index};
  snapshot[64+:16]=observed;snapshot[80+:16]=expected;snapshot[96+:24]=completed[23:0];
  checksum=0;for(k=0;k<15;k=k+1)checksum=checksum^snapshot[k*8+:8];
  snapshot[120+:8]=checksum;
 end
 uart_tx #(.CLK_HZ(27000000),.BAUD(UART_BAUD)) serial(
  .clk(clk),.rst_n(rst_n),.tx_data(tx_byte),.tx_start(start),.tx(uart_tx_pin),.busy(busy),.done(done));
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin heartbeat<=0;frame<=0;byte_index<=0;transmitting<=0;start<=0;tx_byte<=0;end
  else begin
   start<=0;
   if(heartbeat==HEARTBEAT-1)heartbeat<=0;else heartbeat<=heartbeat+1'b1;
   if(!transmitting && heartbeat==0)begin frame<=snapshot;byte_index<=0;transmitting<=1;end
   else if(transmitting && !busy && !start)begin
    if(byte_index<16)begin tx_byte<=frame[byte_index*8+:8];start<=1;byte_index<=byte_index+1'b1;end
    else transmitting<=0;
   end
  end
 end
endmodule
