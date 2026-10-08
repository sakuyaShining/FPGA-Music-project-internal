`timescale 1ns/1ps
// Capacity, rejected pulse count, FIFO order and compliant stalled producers.
// All stimulus changes happen on falling edges, away from DUT sampling.
module tb_evhold;
    localparam DEPTH=8, NEV=20;
    reg clk=0;
    always #5 clk=~clk;
    reg rst_n=0, in_valid=0, in_on=0, out_ready=0;
    reg [6:0] in_note=0;
    reg [3:0] in_vel=0;
    wire in_ready, out_valid, out_on;
    wire [6:0] out_note;
    wire [3:0] out_vel;
    wire [3:0] level;
    wire [15:0] overflow;
    event_hold #(.DEPTH(DEPTH)) dut(clk,rst_n,in_valid,in_on,in_note,in_vel,
        in_ready,out_valid,out_on,out_note,out_vel,out_ready,level,overflow);
    integer fails=0, nr=0, i, producer_i, consumer_i, accepted=0;
    integer r_note[0:63], r_on[0:63], r_vel[0:63];
    always @(posedge clk) if(rst_n && out_valid && out_ready) begin
        if(nr<64) begin r_note[nr]=out_note; r_on[nr]=out_on; r_vel[nr]=out_vel; end
        nr=nr+1;
    end
    task check;
        input [255:0] name;
        input integer got, expected;
        begin
            if(got===expected) $display("PASS %0s (%0d)",name,got);
            else begin $display("FAIL %0s got=%0d expected=%0d",name,got,expected); fails=fails+1; end
        end
    endtask
    task send_ev;
        input on;
        input [6:0] n;
        input [3:0] v;
        integer guard;
        begin
            @(negedge clk); in_valid=1; in_on=on; in_note=n; in_vel=v;
            guard=0;
            while(!in_ready && guard<100) begin @(negedge clk); guard=guard+1; end
            if(!in_ready) begin $display("FAIL producer timeout"); fails=fails+1; end
            @(posedge clk);
            @(negedge clk); in_valid=0;
        end
    endtask
    task consume_one;
        integer guard;
        begin
            @(negedge clk); guard=0;
            while(!out_valid && guard<100) begin @(negedge clk); guard=guard+1; end
            if(!out_valid) begin $display("FAIL consumer timeout"); fails=fails+1; end
            out_ready=1;
            @(posedge clk);
            @(negedge clk); out_ready=0;
        end
    endtask
    initial begin
        repeat(10) @(negedge clk); rst_n=1;
        repeat(10) @(negedge clk);
        check("H1-empty-valid",out_valid,0); check("H1-empty-level",level,0);
        for(i=0;i<DEPTH+3;i=i+1) begin
            in_valid=1; in_note=60+i; in_on=i%2; in_vel=i;
            @(posedge clk); if(in_ready) accepted=accepted+1;
            @(negedge clk);
        end
        in_valid=0;
        check("H2-capacity",accepted,DEPTH); check("H2-full-level",level,DEPTH);
        check("H2-backpressure",in_ready,0); check("H3-rejected-pulses",overflow,3);
        for(i=0;i<DEPTH;i=i+1) consume_one;
        check("H3-drain-count",nr,DEPTH);
        for(i=0;i<DEPTH;i=i+1) begin
            check("H3-note",r_note[i],60+i); check("H3-on",r_on[i],i%2);
            check("H3-vel",r_vel[i],i);
        end
        repeat(3) @(negedge clk); nr=0;
        check("H4-drained-level",level,0); check("H4-drained-valid",out_valid,0);
        for(i=0;i<NEV;i=i+1) begin send_ev(i%2==0,60+i,i%16); consume_one; end
        check("H4-received-count",nr,NEV);
        for(i=0;i<NEV;i=i+1) begin
            check("H4-note",r_note[i],60+i); check("H4-on",r_on[i],i%2==0);
            check("H4-vel",r_vel[i],i%16);
        end
        check("H4-no-extra-overflow",overflow,3);
        // A full FIFO stalls a compliant producer until a delayed consumer
        // frees a slot. This event must still arrive exactly once.
        nr=0;
        for(i=0;i<DEPTH;i=i+1) send_ev(1,80+i,i);
        fork
            begin send_ev(0,90,15); end
            begin
                repeat(6) @(negedge clk);
                for(consumer_i=0;consumer_i<DEPTH+1;consumer_i=consumer_i+1) consume_one;
            end
        join
        check("H5-held-producer-count",nr,DEPTH+1);
        for(i=0;i<DEPTH;i=i+1) begin
            check("H5-held-producer-order",r_note[i],80+i);
            check("H5-held-producer-on",r_on[i],1);
            check("H5-held-producer-vel",r_vel[i],i);
        end
        check("H5-held-note",r_note[DEPTH],90);
        check("H5-held-off",r_on[DEPTH],0);
        check("H5-held-vel",r_vel[DEPTH],15);
        check("H5-blocked-cycles-counted",overflow>3,1);
        // Saturation preserves evidence even after more rejected pulses.
        force dut.overflow=16'hfffe;
        @(negedge clk); release dut.overflow;
        for(i=0;i<DEPTH+3;i=i+1) send_ev_full;
        check("H6-overflow-saturates",overflow,65535);
        if(fails==0) $display("RESULT evhold=PASS");
        else $display("RESULT evhold=FAIL fails=%0d",fails);
        $finish;
    end
    task send_ev_full;
        begin @(negedge clk); in_valid=1; @(negedge clk); in_valid=0; end
    endtask
    initial begin #50000; $display("RESULT evhold=TIMEOUT"); $finish; end
endmodule
