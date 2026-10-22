`timescale 1ns/1ps
`include "transport_fixture.vh"
module tb_transport;
reg clk=0;always #5 clk=~clk;reg rst_n=0,wr_en=0;reg [7:0] addr=0,data=0,rd_addr=0;reg allowed=1;
wire [7:0] rd;wire sandbox,pair_reset,valid,commit,applied,error;wire [1:0] slot;wire [3:0] part,enabled,banks;wire [87:0] word;
reg [7:0] stalls=0;always @(posedge clk)stalls<=stalls+1'b1;
wire ready=stalls[2:0]!=0;
uart_cfg_transport #(.QUIET_CYCLES(64),.TIMEOUT_CYCLES(4000)) dut(.clk(clk),.rst_n(rst_n),.rx_byte(wr_en),.wr_en(wr_en),.wr_addr(addr),.wr_data(data),.rd_addr(rd_addr),.idle_allowed(allowed),.enabled_slots(enabled),.rd_data(rd),.sandbox(sandbox),.pair_reset(pair_reset),.cfg_valid(valid),.cfg_commit(commit),.cfg_slot(slot),.cfg_part(part),.cfg_word(word),.cfg_ready(ready),.cfg_applied(applied),.cfg_error(error));
instrument_table #(.STRICT_FAILURE(1)) store(.clk(clk),.rst_n(rst_n),.valid(valid&&ready),.commit(commit),.slot(slot),.part(part),.word(word),.applied(applied),.error(error),.enabled(enabled),.banks(banks),.read_addr(7'd0));
reg [7:0] payload[0:175];reg [87:0] words[0:15];integer writes=0,publications=0,i,writes_before;reg bank_before;
always @(posedge clk)if(rst_n)begin if(valid&&ready&&!commit)writes=writes+1;if(applied)publications=publications+1;end
task put;input [7:0] a,d;begin @(negedge clk);wr_en=1;addr=a;data=d;@(negedge clk);wr_en=0;end endtask
task header;begin put(8'he0,8'ha5);put(8'he1,0);put(8'he2,8'h34);put(8'he3,8'h12);end endtask
task finish;input [15:0] crc;begin put(8'he5,crc[7:0]);put(8'he6,crc[15:8]);put(8'he7,8'h5a);repeat(1000)@(negedge clk);end endtask
task release_lock;begin repeat(70)@(negedge clk);put(8'he0,8'hc3);if(sandbox)$fatal(1,"sandbox release");end endtask
initial begin
 $readmemh("../transport-payload.hex",payload);$readmemh("../config-fast.hex",words);
 repeat(4)@(negedge clk);rst_n=1;
 header;for(i=0;i<176;i=i+1)put(8'he4,payload[i]);finish(`GOOD_CRC);
 if(publications!=1||writes!=16||enabled!=1||dut.result!=1||dut.revision!=1||!sandbox)$fatal(1,"complete upload confirmation");
 for(i=0;i<16;i=i+1)if(store.words[16+i]!==words[i])$fatal(1,"payload read pipeline/endian %0d",i);
 release_lock;bank_before=banks[0];writes_before=writes;
 header;for(i=0;i<176;i=i+1)put(8'he4,i==13?payload[i]^8'h80:payload[i]);finish(`GOOD_CRC);
 if(dut.result!=2||publications!=1||writes!=writes_before||banks[0]!=bank_before)$fatal(1,"bad CRC touched table");release_lock;
 header;for(i=0;i<175;i=i+1)put(8'he4,payload[i]);finish(`GOOD_CRC);
 if(dut.result!=3||publications!=1||writes!=writes_before)$fatal(1,"truncated payload published");release_lock;
 header;for(i=0;i<176;i=i+1)put(8'he4,i==175?payload[i]|8'h10:payload[i]);finish(`BAD_FIELD_CRC);
 if(dut.result!=4||publications!=1||banks[0]!=bank_before||store.written[0]!=0)$fatal(1,"invalid word published or stale staging survived");release_lock;
 header;put(8'he4,payload[0]);
 // Status polls must not extend an incomplete upload forever.
 for(i=0;i<260;i=i+1)begin put(8'h0f,8'hd6);repeat(16)@(negedge clk);end
 repeat(70)@(negedge clk);
 if(dut.result!=5||publications!=1||dut.revision!=1||!sandbox)$fatal(1,"missing payload timeout or sandbox lost");release_lock;
 allowed=0;put(8'he0,8'ha5);repeat(70)@(negedge clk);
 if(dut.result!=6||publications!=1)$fatal(1,"busy device accepted upload");release_lock;allowed=1;
 header;for(i=0;i<176;i=i+1)put(8'he4,payload[i]);finish(`GOOD_CRC);release_lock;
 if(publications!=2||dut.revision!=2||banks[0]==bank_before)$fatal(1,"retry after failures");
 $display("PASS transport valid CRC length semantic_error staging_clear poll_timeout busy recovery backpressure endian revisions=%0d",dut.revision);$finish;
end
initial begin #3000000;$fatal(1,"timeout");end
endmodule
