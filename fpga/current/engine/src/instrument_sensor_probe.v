// Full raw 6x16 acquisition + calibrated 25-strip centroid report. Digital
// prototype only: routing of node groups and calibration policy need real tests.
module instrument_sensor_probe #(
    parameter integer LANES=6,STRIPS=25,CW=12,
    parameter integer DISCHARGE_CYCLES=512,TIMEOUT_CYCLES=2047,SPI_HALF_PERIOD=8,
    parameter integer CONFIRM_FRAMES=2
)(
    input wire clk,rst_n,calibrate,
    input wire [LANES-1:0] sense_n,
    output wire bus_request,
    input wire bus_grant,
    output wire bus_sck,bus_mosi,scan_latch,
    input wire [CW+1:0] threshold_on,threshold_off,
    output wire report_valid,
    input wire report_ready,
    output wire [STRIPS-1:0] contact,invalid,
    output wire [STRIPS*9-1:0] position,
    output wire [STRIPS*(CW+2)-1:0] area,
    output wire [31:0] report_sequence,
    output wire report_calibration,protocol_error,grant_error
);
    function [STRIPS*21-1:0] example_map;
        input integer unused;
        integer n;
        begin for(n=0;n<STRIPS*3;n=n+1)example_map[n*7+:7]=n;end
    endfunction
    localparam [STRIPS*21-1:0] MAP=example_map(0);
    wire row_valid,row_ready,frame_valid,frame_ready,frame_cal;
    wire [3:0] row_address;
    wire [LANES*CW-1:0] row_count;
    wire [LANES-1:0] row_fault;
    wire [31:0] row_sequence,frame_sequence;
    wire [6:0] read_address;
    wire [CW-1:0] read_delta;
    wire read_valid;
    rc_mux_scan #(.LANES(LANES),.CW(CW),.DISCHARGE_CYCLES(DISCHARGE_CYCLES),.TIMEOUT_CYCLES(TIMEOUT_CYCLES),.SPI_HALF_PERIOD(SPI_HALF_PERIOD)) scanner(
        .clk(clk),.rst_n(rst_n),.sense_n(sense_n),.bus_request(bus_request),.bus_grant(bus_grant),.bus_sck(bus_sck),.bus_mosi(bus_mosi),.scan_latch(scan_latch),
        .row_valid(row_valid),.row_ready(row_ready),.row_address(row_address),.row_count(row_count),.row_fault(row_fault),.row_sequence(row_sequence),.grant_error(grant_error));
    rc_delta_store #(.LANES(LANES),.CW(CW)) store(
        .clk(clk),.rst_n(rst_n),.calibrate(calibrate),.row_valid(row_valid),.row_ready(row_ready),.row_address(row_address),.row_count(row_count),.row_fault(row_fault),.row_sequence(row_sequence),
        .frame_valid(frame_valid),.frame_ready(frame_ready),.frame_sequence(frame_sequence),.frame_calibration(frame_cal),.read_address(read_address),.read_delta(read_delta),.read_valid(read_valid),.protocol_error(protocol_error));
    rc_strip_positions #(.STRIPS(STRIPS),.CW(CW),.CONFIRM_FRAMES(CONFIRM_FRAMES),.NODE_MAP(MAP)) positions(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_sequence(frame_sequence),.frame_calibration(frame_cal),.read_address(read_address),.read_delta(read_delta),.read_valid(read_valid),
        .threshold_on(threshold_on),.threshold_off(threshold_off),.report_valid(report_valid),.report_ready(report_ready),.contact(contact),.invalid(invalid),.position(position),.area(area),.report_sequence(report_sequence),.report_calibration(report_calibration));
endmodule
