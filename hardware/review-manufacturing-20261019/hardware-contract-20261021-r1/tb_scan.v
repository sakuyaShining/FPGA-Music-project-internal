`timescale 1ns/1ps
module tb_scan;
reg clk=0;always #5 clk=~clk;
reg rst_n=0;reg [1:0] resets=3;reg grant=1,ready=1;
wire sck,mosi,latch,request,row_valid,grant_error;
wire [3:0] addr;wire [71:0] counts;wire [5:0] faults;wire [31:0] seq;
reg [7:0] shift=0,q=0;integer bits=0,latches=0,rows=0,errors=0,k;reg [3:0] expected_addr=0;
integer charge_age=0;reg [5:0] sense=6'b111111;reg [7:0] q_prev=0;
`ifdef PATCHED
rc_mux_scan_hw #(.DISCHARGE_CYCLES(12),.TIMEOUT_CYCLES(40),.SPI_HALF_PERIOD(2)) dut(
 .peripheral_reset_n(resets),
`else
rc_mux_scan #(.DISCHARGE_CYCLES(12),.TIMEOUT_CYCLES(40),.SPI_HALF_PERIOD(2)) dut(
`endif
 .clk(clk),.rst_n(rst_n),.sense_n(sense),.bus_request(request),.bus_grant(grant),
 .bus_sck(sck),.bus_mosi(mosi),.scan_latch(latch),.row_valid(row_valid),.row_ready(ready),
 .row_address(addr),.row_count(counts),.row_fault(faults),.row_sequence(seq),.grant_error(grant_error));
always @(posedge sck)begin shift={shift[6:0],mosi};bits=bits+1;end
always @(posedge latch)begin
 q=shift;
 if(bits!=8)begin $display("BAD_WORD_LENGTH %0d",bits);errors=errors+1;end
 bits=0;
 if(q[7:6]!==resets)begin $display("RESET_COLLISION q=%h expected=%b",q,resets);errors=errors+1;end
 case(latches%4)
 0,1:if(q[5:4]!==2'b01)errors=errors+1;
 2:if(q[5:4]!==2'b00)errors=errors+1;
 3:if(q[5:4]!==2'b10)errors=errors+1;
 endcase
 latches=latches+1;
end
always @(posedge clk)begin
 if(!q[5]||q[4])charge_age<=0;else charge_age<=charge_age+1;
 for(k=0;k<6;k=k+1)begin
  if(!q[5]||q[4])sense[k]<=1;
  else if(k==5&&rows>=16)sense[k]<=1; // deliberate stuck-untransitioned input
  else sense[k]<=charge_age<(4+k);
 end
 q_prev<=q;
end
always @(posedge clk)if(rst_n&&row_valid&&ready)begin
 if(addr!==expected_addr)begin $display("ADDRESS_ORDER %d != %d",addr,expected_addr);errors=errors+1;end
 if(seq!==rows/16)begin $display("SEQUENCE_ORDER");errors=errors+1;end
 expected_addr=expected_addr+1'b1;
 for(k=0;k<6;k=k+1)begin
  if(rows>=16&&k==5)begin
   if(!faults[k]||counts[k*12+:12]!=40)begin $display("MISSING_TIMEOUT");errors=errors+1;end
  end else if(faults[k]||counts[k*12+:12]==0||counts[k*12+:12]>20)begin
   $display("BAD_MEASURE lane=%d count=%d fault=%b",k,counts[k*12+:12],faults[k]);errors=errors+1;
  end
 end
 rows=rows+1;
 // At a quiet word boundary, exercise independent reset states.
 if(rows==8)resets=2'b10;
 if(rows==16)resets=2'b01;
 if(rows==24)resets=2'b11;
 if(rows==32)begin
  if(grant_error)errors=errors+1;
  if(errors)$fatal(1,"SCAN_CONTRACT_FAIL errors=%0d rows=%0d words=%0d",errors,rows,latches);
  $display("SCAN_CONTRACT_PASS rows=%0d words=%0d reset_states=3 timeout=detected",rows,latches);$finish;
 end
end
initial begin repeat(8)@(negedge clk);rst_n=1;end
// Grant stalls only before a word begins; report backpressure does not relatch.
initial begin wait(rst_n);repeat(12)begin wait(!request);@(negedge clk);grant=0;repeat(7)@(negedge clk);grant=1;wait(request);wait(!request);end end
initial begin wait(rst_n);repeat(5)begin wait(row_valid);@(negedge clk);ready=0;repeat(9)@(negedge clk);ready=1;wait(!row_valid);end end
initial begin #1000000;$fatal(1,"SCAN_TIMEOUT");end
endmodule
