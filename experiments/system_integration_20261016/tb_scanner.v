`timescale 1ns/1ps
module tb_scanner;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ready=0,grant=0;
    reg [1:0] sense=2'b11;
    wire request,sck,mosi,latch,valid,error;
    wire [3:0] address;
    wire [23:0] counts;
    wire [1:0] fault;
    wire [31:0] seq;
    rc_mux_scan #(.LANES(2),.DISCHARGE_CYCLES(16),.TIMEOUT_CYCLES(48),.SPI_HALF_PERIOD(2)) dut(
        .clk(clk),.rst_n(rst_n),.sense_n(sense),.bus_request(request),.bus_grant(grant),.bus_sck(sck),.bus_mosi(mosi),.scan_latch(latch),
        .row_valid(valid),.row_ready(ready),.row_address(address),.row_count(counts),.row_fault(fault),.row_sequence(seq),.grant_error(error));
    reg [7:0] shift=0,control=8'hff;
    integer edges=0,words=0,rows=0,cycle=0,charge_at=0,j,delay0,delay1;
    reg prior_sck=0,prior_latch=0;
    reg [61:0] held;
    reg stalled=0;
    // No real capacitor model: ideal programmable transition time only.
    always @(negedge clk)begin
        cycle=cycle+1;
        if(request&&!grant&&(cycle%7==0))grant=1;
        if(!request)grant=0;
        if(sck&&!prior_sck)begin shift={shift[6:0],mosi};edges=edges+1;if(!grant)$fatal(1,"edge without grant");end
        if(latch&&!prior_latch)begin
            if(edges!=8)$fatal(1,"latched incomplete word %d",edges);
            if(shift[3:0]!=control[3:0]&&!control[4])$fatal(1,"address switched while enabled");
            edges=0;words=words+1;control=shift;
            if(control[5]&&!control[4])charge_at=cycle;
        end
        prior_sck=sck;prior_latch=latch;
        delay0=7+control[3:0];delay1=11+control[3:0];
        sense=2'b11;
        if(!control[4])begin
            if(control[3:0]==5)sense[1]=0;
            if(control[5])begin
                if(control[3:0]!=3&&cycle-charge_at>=delay0)sense[0]=0;
                if(cycle-charge_at>=delay1)sense[1]=0;
            end
        end
        ready=(cycle%13>3);
        if(stalled&&({seq,address,fault,counts}!==held))$fatal(1,"backpressure changed row");
        stalled=valid&&!ready;held={seq,address,fault,counts};
    end
    always @(posedge clk)if(rst_n&&valid&&ready)begin
        if(address!=rows%16||seq!=rows/16)$fatal(1,"order");
        if(address==3)begin if(!fault[0]||counts[11:0]!=48)$fatal(1,"timeout missing");end
        else if(fault[0]||counts[11:0]!=(8+address))$fatal(1,"lane0 timing addr=%0d count=%0d",address,counts[11:0]);
        if(address==5)begin if(!fault[1])$fatal(1,"stuck polarity missing");end
        else if(fault[1]||counts[23:12]!=(12+address))$fatal(1,"lane1 timing addr=%0d count=%0d",address,counts[23:12]);
        rows=rows+1;
        if(rows==32)begin
            if(error)$fatal(1,"grant error");
            $display("PASS scanner rows=%0d words=%0d ordered timeout stuck_input backpressure grant_delays physical_latch_timing",rows,words);$finish;
        end
    end
    initial begin repeat(4)@(negedge clk);rst_n=1;end
    initial begin #2000000;$fatal(1,"watchdog");end
endmodule
