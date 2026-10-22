`timescale 1ns/1ps
module tb_spi_fault;
    parameter integer HALF=2;
    reg clk=0,rst_n=0,valid=0;
    always #18.519 clk=~clk;
    wire ready,done,cs_n,sck,mosi,dc;
    integer bits=0;
    reg [7:0] received=0;
    realtime last_rise=-1;
    ili9341_spi_byte #(.HALF_CYCLES(HALF)) dut(.clk(clk),.rst_n(rst_n),
        .valid(valid),.dc_in(1'b1),.data_in(8'hA6),.ready(ready),.done(done),
        .cs_n(cs_n),.sck(sck),.mosi(mosi),.dc(dc));
    always @(posedge sck) if (!cs_n) begin
        if (last_rise>=0 && $realtime-last_rise<99.999) begin
            $display("EXPECTED_TIMING_REJECTION cycle=%.3fns",$realtime-last_rise);
            $fatal(1);
        end
        last_rise=$realtime; received={received[6:0],mosi}; bits=bits+1;
    end
    initial begin
        #1 rst_n=0;
        repeat(3) @(negedge clk);
        rst_n=1;
        @(negedge clk); valid=1;
        @(negedge clk); valid=0;
        wait(done);
        if (bits!=8 || received!=8'hA6 || !dc) $fatal(1,"SPI byte mismatch");
        $display("PASS serializer byte and clock period"); $finish;
    end
    initial begin #10000; $fatal(1,"timeout"); end
endmodule
