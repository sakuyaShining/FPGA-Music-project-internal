`timescale 1ns/1ps
module tb_positions;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,calibrate=0,row_valid=0,report_ready=0;
    wire row_ready,frame_valid,frame_ready,frame_cal,protocol_error;
    reg [3:0] row_address=0;
    reg [23:0] row_count=0;
    reg [1:0] row_fault=0;
    reg [31:0] row_sequence=0;
    wire [31:0] frame_sequence,report_sequence;
    wire [6:0] read_address;
    wire [11:0] read_delta;
    wire read_valid,report_valid,report_cal;
    wire [3:0] contact,invalid;
    wire [35:0] position;
    function [83:0] make_map;
        input integer ignored;integer n;
        begin for(n=0;n<12;n=n+1)make_map[n*7+:7]=n;end
    endfunction
    rc_delta_store #(.LANES(2)) store(.clk(clk),.rst_n(rst_n),.calibrate(calibrate),.row_valid(row_valid),.row_ready(row_ready),.row_address(row_address),.row_count(row_count),.row_fault(row_fault),.row_sequence(row_sequence),
        .frame_valid(frame_valid),.frame_ready(frame_ready),.frame_sequence(frame_sequence),.frame_calibration(frame_cal),.read_address(read_address),.read_delta(read_delta),.read_valid(read_valid),.protocol_error(protocol_error));
    rc_strip_positions #(.STRIPS(4),.NODE_MAP(make_map(0))) positions(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_sequence(frame_sequence),.frame_calibration(frame_cal),
        .read_address(read_address),.read_delta(read_delta),.read_valid(read_valid),.threshold_on(14'd60),.threshold_off(14'd30),
        .report_valid(report_valid),.report_ready(report_ready),.contact(contact),.invalid(invalid),.position(position),.report_sequence(report_sequence),.report_calibration(report_cal));
    reg [31:0] rows[0:2559];
    reg [3:0] meta[0:159];
    reg [47:0] expected[0:159];
    reg [44:0] held;
    integer f,a,k,reports=0;
    task send_row;
        input [3:0] addr;
        input [31:0] seq,data;
        begin
            @(negedge clk);row_address=addr;row_sequence=seq;row_count=data[23:0];row_fault=data[25:24];row_valid=1;
            @(posedge clk);while(!row_ready)@(posedge clk);
            @(negedge clk);row_valid=0;
        end
    endtask
    initial begin
        $readmemh("row_vectors.hex",rows);$readmemh("meta_vectors.hex",meta);$readmemh("expected_vectors.hex",expected);
        repeat(4)@(negedge clk);rst_n=1;
        // Out-of-order input must be rejected, then a proper row0 resynchronizes.
        send_row(4'd2,0,0);if(!protocol_error)$fatal(1,"missing protocol diagnostic");
        for(f=0;f<160;f=f+1)begin
            @(negedge clk);calibrate=meta[f][0];@(negedge clk);calibrate=0;
            for(a=0;a<16;a=a+1)send_row(a,f,rows[f*16+a]);
            wait(report_valid);#1;
            if({report_cal,invalid,contact,position}!==expected[f][44:0]||report_sequence!=f)
                $fatal(1,"reference frame=%0d got=%h expected=%h",f,{report_cal,invalid,contact,position},expected[f]);
            held={report_cal,invalid,contact,position};
            for(k=0;k<17;k=k+1)begin @(negedge clk);if(!report_valid||{report_cal,invalid,contact,position}!==held||row_ready)$fatal(1,"coherent report/backpressure");end
            report_ready=1;@(negedge clk);report_ready=0;reports=reports+1;
        end
        $display("PASS positions frames=%0d independent_reference calibration invalid_nodes endpoints wide_centroid debounce hysteresis coherent_backpressure protocol_resync",reports);$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
