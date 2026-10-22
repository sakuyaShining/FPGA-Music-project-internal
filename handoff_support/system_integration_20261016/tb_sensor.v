`timescale 1ns/1ps
module tb_sensor;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,calibrate=0,report_ready=0,grant=0;
    reg [5:0] sense_n=6'b111111;
    wire bus_request,bus_sck,bus_mosi,scan_latch,report_valid,report_calibration,protocol_error,grant_error;
    wire [25:0] contact,invalid;
    wire [233:0] position;
    wire [31:0] report_sequence;
    instrument_sensor_probe #(.DISCHARGE_CYCLES(32),.TIMEOUT_CYCLES(192),.SPI_HALF_PERIOD(1)) dut(
        .clk(clk),.rst_n(rst_n),.calibrate(calibrate),.sense_n(sense_n),.bus_request(bus_request),.bus_grant(grant),.bus_sck(bus_sck),.bus_mosi(bus_mosi),.scan_latch(scan_latch),
        .threshold_on(14'd20),.threshold_off(14'd10),.report_valid(report_valid),.report_ready(report_ready),.contact(contact),.invalid(invalid),.position(position),
        .report_sequence(report_sequence),.report_calibration(report_calibration),.protocol_error(protocol_error),.grant_error(grant_error));
    integer cycle=0,charge_at=0,charge_frame=0,i,node,delay,edges=0,words=0,f,k,start_cycle=0;
    reg old_sck=0,old_latch=0;
    reg [7:0] shift=0,control=8'hff;
    reg [285:0] held;
    always @(negedge clk)begin
        cycle=cycle+1;
        if(bus_request&&!grant&&cycle%5==0)grant=1;
        if(!bus_request)grant=0;
        if(bus_sck&&!old_sck)begin shift={shift[6:0],bus_mosi};edges=edges+1;end
        if(scan_latch&&!old_latch)begin
            if(edges!=8)$fatal(1,"corrupt word");edges=0;words=words+1;control=shift;
            if(control[5]&&!control[4])begin charge_at=cycle;charge_frame=dut.scanner.scan_sequence;end
        end
        old_sck=bus_sck;old_latch=scan_latch;
        for(i=0;i<6;i=i+1)begin
            node=control[3:0]*6+i;delay=15+node;
            if(charge_frame>=1&&charge_frame<=2)begin if(node==2)delay=delay+30;if(node==75)delay=delay+40;end
            sense_n[i]=!(!control[4]&&control[5]&&cycle-charge_at>=delay);
        end
    end
    initial begin
        repeat(4)@(posedge clk);@(negedge clk);rst_n=1;calibrate=1;
        @(negedge clk);calibrate=0;
        for(f=0;f<5;f=f+1)begin
            wait(report_valid);#1;
            if(report_sequence!=f||invalid||protocol_error||grant_error)$fatal(1,"sensor sequence/fault %d",f);
            if(report_calibration!=(f==0))$fatal(1,"cal frame");
            if((f==2||f==3)?(contact!==26'h2000001):(contact!==0))$fatal(1,"contacts f=%0d bits=%h",f,contact);
            if(f>=1&&(position[8:0]!=256||position[25*9+:9]!=0))$fatal(1,"positions %d %d",position[8:0],position[25*9+:9]);
            held={contact,invalid,position};
            repeat(100)begin @(posedge clk);#1;if(!report_valid||{contact,invalid,position}!==held)$fatal(1,"output hold");end
            @(negedge clk);report_ready=1;@(negedge clk);report_ready=0;
        end
        $display("PASS sensor lanes=6 nodes=96 strips=26 frames=5 cycles=%0d words=%0d physical_words_to_calibrated_positions backpressure",cycle,words);$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
