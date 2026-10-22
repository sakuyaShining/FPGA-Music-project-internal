// Independent slow memory: actual address-indexed store, one pending response.
// Bus pause, latency and consumer stalls are controlled independently of DUT.
module memory_backend_model #(parameter AW=3)(
 input wire clk,rst_n,pause,input wire [7:0] latency,
 input wire req_valid,output wire req_ready,input wire req_write,
 input wire [21:0] req_addr,input wire [15:0] req_data,
 output reg rsp_valid,input wire rsp_ready,output reg [15:0] rsp_data
);
 reg [15:0] memory[0:(2<<AW)-1];
 reg pending;reg [7:0] wait_left;reg [15:0] result;
 assign req_ready=rst_n && !pause && !pending && !rsp_valid;
 always @(posedge clk or negedge rst_n)begin
  if(!rst_n)begin pending<=0;wait_left<=0;rsp_valid<=0;rsp_data<=0;result<=0;end
  else begin
   if(rsp_valid && rsp_ready)rsp_valid<=0;
   if(pending)begin
    if(wait_left==0)begin rsp_valid<=1;rsp_data<=result;pending<=0;end
    else wait_left<=wait_left-1'b1;
   end
   if(req_valid && req_ready)begin
    if(req_addr>=(2<<AW))$fatal(1,"memory address outside both regions");
    if(req_write)begin memory[req_addr]<=req_data;result<=0;end
    else begin
     if((^memory[req_addr])===1'bx)$fatal(1,"read before initialization");
     result<=memory[req_addr];
    end
    pending<=1;wait_left<=latency;
   end
  end
 end
endmodule
