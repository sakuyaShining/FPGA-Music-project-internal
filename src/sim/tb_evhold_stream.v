`timescale 1ns/1ps
// Consecutive transfers, stalls and wraparound; drive on falling edges.
module evhold_stream_case #(parameter DEPTH=2)(output reg done=0, output reg failed=0);
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, iv=0, ion=0, ready=0;
    reg [6:0] note=0;
    reg [3:0] vel=0;
    wire ir, ov, oon;
    wire [6:0] onote;
    wire [3:0] ovel;
    wire [$clog2(DEPTH+1)-1:0] level;
    wire [15:0] overflow;
    event_hold #(.DEPTH(DEPTH)) dut(clk,rst_n,iv,ion,note,vel,ir,ov,oon,onote,ovel,ready,level,overflow);
    integer sent=0, received=0, cycle=0;
    reg [11:0] expected [0:255];
    reg stalled=0;
    reg [11:0] held;
    always @(posedge clk) if (rst_n) begin
        if (stalled && (!ov || {oon,onote,ovel} !== held)) begin
            $display("FAIL depth=%0d changed stalled head",DEPTH); failed=1;
        end
        stalled=ov && !ready;
        held={oon,onote,ovel};
        if (iv && ir) begin expected[sent]={ion,note,vel}; sent=sent+1; end
        if (ov && ready) begin
            if (received>=sent || {oon,onote,ovel} !== expected[received]) begin
                $display("FAIL depth=%0d item=%0d got=%h expected=%h sent=%0d",DEPTH,received,{oon,onote,ovel},expected[received],sent);
                failed=1;
            end
            received=received+1;
        end
    end
    initial begin
        repeat(3) @(negedge clk);
        rst_n=1;
        // Fill a burst, then consume at one transfer per clock.
        for(cycle=0;cycle<DEPTH;cycle=cycle+1) begin
            iv=1; note=40+cycle; ion=cycle%2; vel=cycle;
            @(negedge clk);
        end
        iv=0; ready=1;
        repeat(DEPTH+6) @(negedge clk);
        if(received!=DEPTH || ov || level!=0) begin
            $display("FAIL depth=%0d drain received=%0d level=%0d valid=%b",DEPTH,received,level,ov); failed=1;
        end
        // Simultaneous push/pop, stalled output and multiple pointer wraps.
        for(cycle=0;cycle<100;cycle=cycle+1) begin
            ready=(cycle%7<4);
            iv=ir;
            note=cycle; ion=cycle%2; vel=cycle%16;
            @(negedge clk);
        end
        iv=0; ready=1;
        repeat(DEPTH+8) @(negedge clk);
        if(received!=sent || level!=0 || ov || overflow!=0) begin
            $display("FAIL depth=%0d final sent=%0d received=%0d level=%0d ovf=%0d",DEPTH,sent,received,level,overflow); failed=1;
        end
        done=1;
    end
endmodule
module tb_evhold_stream;
    wire [2:0] done, failed;
    evhold_stream_case #(2) a(done[0],failed[0]);
    evhold_stream_case #(4) b(done[1],failed[1]);
    evhold_stream_case #(8) c(done[2],failed[2]);
    initial begin
        wait(&done);
        if(|failed) $display("RESULT evhold_stream=FAIL");
        else $display("RESULT evhold_stream=PASS");
        $finish;
    end
    initial begin #20000; $display("RESULT evhold_stream=TIMEOUT"); $finish; end
endmodule
