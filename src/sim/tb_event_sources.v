`timescale 1ns/1ps
// Source-boundary stress (not a UART RX/physical pad test). Existing evmerge
// covers real UART bytes; padfast covers RC pads. Here TX readback is decoded.
module tb_event_sources;
    reg clk=0;
    always #18.5185 clk=~clk;
    reg rst_n=0, pv=0, pon=0;
    reg [6:0] pn=0;
    reg [3:0] pvel=0;
    wire [15:0] pad;
    wire tx;
    tdm_top dut(.clk(clk),.rst_n(rst_n),.ev_valid(pv),.ev_on(pon),.ev_note(pn),.ev_vel(pvel),
        .preset(2'd0),.test_mode(1'b0),.uart_rx_pin(1'b1),.uart_tx_pin(tx),
        .pad(pad),.led(),.dac_din(),.dac_ws(),.dac_bck(),.pa_en());
    reg we=0, sv=0, son=0, padv=0, padon=0, seqenable=1;
    reg [7:0] wa=0, wd=0, svel=0;
    reg [6:0] sn=0, padn=0;
    reg [3:0] padvel=0;
    reg monitor=0;
    reg [11:0] expected[0:255];
    integer sent[0:3], received[0:3];
    integer fails=0, i, j, src, total=0;
    integer transfers=0;
    task check;
        input [255:0] label;
        input integer got, want;
        begin
            if(got===want) $display("PASS %0s (%0d)",label,got);
            else begin $display("FAIL %0s got=%0d want=%0d",label,got,want); fails=fails+1; end
        end
    endtask
    task expect_event;
        input integer source;
        input on;
        input [6:0] note;
        input [3:0] vel;
        begin expected[source*64+sent[source]]={on,note,vel}; sent[source]=sent[source]+1; end
    endtask
    always @(posedge clk) if(rst_n && monitor) begin
        // Under four-source contention a nonempty source waits <= four grants.
        if(dut.mh_valid && dut.ev_in_ready) begin
            transfers=transfers+1;
            if(dut.sel_u) src=0;
            else if(dut.sel_s) src=1;
            else if(dut.sel_p) src=2;
            else src=3;
            if(transfers<=12 && src!=(transfers-1)%4) begin
                $display("FAIL round-robin grant=%0d source=%0d",transfers,src); fails=fails+1;
            end
        end
        if(dut.nm_ev_ack) begin
            src=(dut.ev_note_r-40)/16;
            if(src<0 || src>3) begin $display("FAIL unexpected note %0d",dut.ev_note_r); fails=fails+1; end
            else begin
                if(received[src]>=sent[src] ||
                   {dut.ev_on_r,dut.ev_note_r,dut.ev_vel_r} !== expected[src*64+received[src]]) begin
                    $display("FAIL source=%0d item=%0d got=%h expected=%h",src,received[src],
                        {dut.ev_on_r,dut.ev_note_r,dut.ev_vel_r},expected[src*64+received[src]]); fails=fails+1;
                end
                received[src]=received[src]+1; total=total+1;
            end
        end
    end
    task write_reg;
        input [7:0] addr, data;
        begin
            @(negedge clk); we=1; wa=addr; wd=data;
            @(negedge clk); we=0;
        end
    endtask
    localparam BIT=234;
    task rx_byte;
        output [7:0] value;
        integer k, guard;
        begin
            guard=0;
            while(tx!==0 && guard<10000) begin @(posedge clk); guard=guard+1; end
            if(tx!==0) begin $display("FAIL TX timeout"); fails=fails+1; end
            repeat(BIT+BIT/2) @(posedge clk);
            for(k=0;k<8;k=k+1) begin value[k]=tx; repeat(BIT) @(posedge clk); end
            check("TX-stop-bit",tx,1);
        end
    endtask
    reg [7:0] address_byte, data_byte;
    task read_check;
        input [7:0] addr, want;
        begin
            write_reg(8'h0f,addr);
            rx_byte(address_byte); rx_byte(data_byte);
            check("readback-address",address_byte,addr);
            check("readback-data",data_byte,want);
            repeat(300) @(negedge clk);
        end
    endtask
    initial begin
        for(i=0;i<4;i=i+1) begin sent[i]=0; received[i]=0; end
        force dut.uart_wr_en=we; force dut.uart_wr_addr=wa; force dut.uart_wr_data=wd;
        force dut.seq_en=seqenable;
        force dut.sq_ev_valid=sv; force dut.sq_ev_on=son; force dut.sq_ev_note=sn; force dut.sq_ev_vel=svel;
        force dut.pp_ev_valid=padv; force dut.pp_ev_on=padon; force dut.pp_ev_note=padn; force dut.pp_ev_vel=padvel;
        repeat(10) @(negedge clk); rst_n=1;
        repeat(2000) @(negedge clk);
        write_reg(8'h60,8'hA8); // on40, then three consecutive 0x61 writes
        monitor=1;
        for(i=0;i<3;i=i+1) begin
            @(negedge clk);
            we=1; wa=8'h61; wd=i+1;
            sv=1; son=i%2==0; sn=56+i; svel=(i+2)<<4;
            padv=1; padon=i%2==0; padn=72+i; padvel=i+3;
            pv=1; pon=i%2==0; pn=88+i; pvel=i+4;
            expect_event(0,1,40,i+1); expect_event(1,i%2==0,56+i,i+2);
            expect_event(2,i%2==0,72+i,i+3); expect_event(3,i%2==0,88+i,i+4);
        end
        @(negedge clk); we=0; sv=0; padv=0; pv=0;
        seqenable=0; // already accepted sequencer heads must still drain
        repeat(1500) @(negedge clk);
        check("four-source-total",total,12);
        for(i=0;i<4;i=i+1) check("per-source-three-events",received[i],3);
        check("uart-no-overwrite",dut.uartq_ovf,0); check("seq-no-loss",dut.seqq_ovf,0);
        check("pad-no-loss",dut.padq_ovf,0); check("pin-no-loss",dut.pinq_ovf,0);
        check("shared-stalls-not-drops",dut.ev_q_ovf,0);
        // Cursor points to an empty source: remaining UART/seq must progress.
        seqenable=1;
        write_reg(8'h60,8'hA9);
        @(negedge clk); we=1; wa=8'h61; wd=9; sv=1; son=1; sn=59; svel=8'hA0;
        expect_event(0,1,41,9); expect_event(1,1,59,10);
        @(negedge clk); we=0; sv=0;
        repeat(1000) @(negedge clk);
        check("skip-empty-cursor",total,14);
        monitor=0;
        // Block downstream transfers; each source accepts four of ten pulses.
        force dut.ev_in_ready=0;
        for(i=0;i<10;i=i+1) begin
            @(negedge clk); we=1; wa=8'h61; wd=i;
            sv=1; sn=60; son=1; svel=8'h80;
            padv=1; padn=76; padon=1; padvel=8;
            pv=1; pn=92; pon=1; pvel=8;
        end
        @(negedge clk); we=0; sv=0; padv=0; pv=0;
        check("uart-rejected-six",dut.uartq_ovf,6); check("seq-rejected-six",dut.seqq_ovf,6);
        check("pad-rejected-six",dut.padq_ovf,6); check("pin-rejected-six",dut.pinq_ovf,6);
        read_check(8'h74,6); read_check(8'h75,0);
        read_check(8'h76,6); read_check(8'h77,0);
        read_check(8'h78,6); read_check(8'h79,0);
        read_check(8'h7A,6); read_check(8'h7B,0);
        read_check(8'h7C,8'h0F);
        write_reg(8'h74,8'hff); read_check(8'h74,6); // read-only
        release dut.ev_in_ready;
        @(negedge clk); rst_n=0;
        repeat(3) @(negedge clk); rst_n=1;
        repeat(2000) @(negedge clk);
        read_check(8'h7C,0); read_check(8'h74,0);
        if(fails==0) $display("RESULT event_sources=PASS");
        else $display("RESULT event_sources=FAIL fails=%0d",fails);
        $finish;
    end
    initial begin #20_000_000; $display("RESULT event_sources=TIMEOUT"); $finish; end
endmodule
