`timescale 1ns/1ps
module budget_case #(parameter GRANT_DELAY=0)(output reg done=0,output reg [31:0] period_cycles=0);
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,calibrate=0,grant=0;
    reg [5:0] sense=6'b111111;
    wire request,sck,mosi,latch,valid,cal,error1,error2;
    wire [25:0] contact,invalid;
    wire [233:0] position;
    wire [31:0] seq;
    instrument_sensor_probe dut(.clk(clk),.rst_n(rst_n),.calibrate(calibrate),.sense_n(sense),.bus_request(request),.bus_grant(grant),.bus_sck(sck),.bus_mosi(mosi),.scan_latch(latch),
        .threshold_on(14'd1000),.threshold_off(14'd500),.report_valid(valid),.report_ready(1'b1),.contact(contact),.invalid(invalid),.position(position),.report_sequence(seq),.report_calibration(cal),.protocol_error(error1),.grant_error(error2));
    reg old_sck=0,old_latch=0;
    reg [7:0] shift=0,control=8'hff;
    integer cycle=0,charge_at=0,charge_frame=0,grant_wait=0,delay,reports=0,last_cycle=0,i;
    always @(negedge clk)begin
        cycle=cycle+1;
        if(!request)begin grant=0;grant_wait=0;end
        else if(!grant)begin if(grant_wait==GRANT_DELAY)grant=1;else grant_wait=grant_wait+1;end
        if(sck&&!old_sck)shift={shift[6:0],mosi};
        if(latch&&!old_latch)begin control=shift;if(control[5]&&!control[4])begin charge_at=cycle;charge_frame=dut.scanner.scan_sequence;end end
        old_sck=sck;old_latch=latch;
        delay=charge_frame==0?100:2040;
        sense=(!control[4]&&control[5]&&cycle-charge_at>=delay)?6'd0:6'b111111;
    end
    always @(posedge clk)if(rst_n&&valid)begin
        if(invalid||error1||error2||seq!=reports)$fatal(1,"budget sensor fault");
        if(seq>=1)for(i=0;i<26;i=i+1)if(position[i*9+:9]!=128)$fatal(1,"wide centroid");
        if(seq==2)begin
            if(contact!={26{1'b1}})$fatal(1,"all26 debounce");
            period_cycles=cycle-last_cycle;done=1;
        end
        last_cycle=cycle;reports=reports+1;
    end
    initial begin repeat(4)@(negedge clk);rst_n=1;calibrate=1;@(negedge clk);calibrate=0;end
endmodule
module tb_scan_budget;
    wire done0,done64;wire [31:0] cycles0,cycles64;
    budget_case #(.GRANT_DELAY(0)) no_contention(done0,cycles0);
    budget_case #(.GRANT_DELAY(64)) bounded_contention(done64,cycles64);
    initial begin
        wait(done0&&done64);
        $display("PASS scan_budget default6x16 frame_cycles_grant0=%0d frame_cycles_grant64=%0d clock_hz=27000000 all26positions debounce2 latency_scope_scan_only",cycles0,cycles64);$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
