// Inverting Schmitt inputs: discharged=1, charged=0. Counter starts AFTER the
// charge word has physically latched, including the known synchronizer delay.
// Abstract logical pins, not Nano20K pin assignments. RC constants are fixtures.
module rc_mux_scan_hw #(
    parameter integer LANES=6,CW=12,DISCHARGE_CYCLES=512,
    parameter integer TIMEOUT_CYCLES=2047,SPI_HALF_PERIOD=8
)(
    input wire clk,rst_n,
    input wire [1:0] peripheral_reset_n, // Q7 touch reset, Q6 shared display reset; active low
    input wire [LANES-1:0] sense_n,
    output wire bus_request,
    input wire bus_grant,
    output wire bus_sck,bus_mosi,scan_latch,
    output reg row_valid,
    input wire row_ready,
    output reg [3:0] row_address,
    output reg [LANES*CW-1:0] row_count,
    output reg [LANES-1:0] row_fault,
    output reg [31:0] row_sequence,
    output wire grant_error
);
    localparam DISABLE=0,ADDRESS=1,CONNECT=2,DISCHARGE=3,CHARGE=4,MEASURE=5,PUBLISH=6;
    reg [2:0] state;
    reg waiting;
    reg [3:0] address,previous_address;
    reg [31:0] scan_sequence;
    localparam DW=(DISCHARGE_CYCLES<2)?1:$clog2(DISCHARGE_CYCLES);
    reg [DW-1:0] dis_timer;
    reg [CW-1:0] timer;
    (* syn_preserve=1 *) reg [LANES-1:0] sense_meta,sense_sync;
    reg [LANES-1:0] finished,fault;
    reg [CW-1:0] counts[0:LANES-1];
    wire send_state=state==DISABLE||state==ADDRESS||state==CONNECT||state==CHARGE;
    wire word_valid=send_state&&!waiting;
    wire word_ready,word_done,word_latched;
    wire [3:0] word_address=(state==DISABLE)?previous_address:address;
    wire [7:0] word_data={peripheral_reset_n,(state==CHARGE),(state==DISABLE||state==ADDRESS),word_address};
    scan_shift595 #(.HALF_PERIOD(SPI_HALF_PERIOD)) writer(
        .clk(clk),.rst_n(rst_n),.word_valid(word_valid),.word_ready(word_ready),.word_data(word_data),
        .bus_request(bus_request),.bus_grant(bus_grant),.sck(bus_sck),.mosi(bus_mosi),.latch(scan_latch),
        .word_latched(word_latched),.word_done(word_done),.grant_error(grant_error));
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n)begin
            sense_meta<=0;sense_sync<=0;state<=DISABLE;waiting<=0;address<=0;previous_address<=0;scan_sequence<=0;
            dis_timer<=0;timer<=0;finished<=0;fault<=0;row_valid<=0;row_address<=0;row_count<=0;row_fault<=0;row_sequence<=0;
            for(i=0;i<LANES;i=i+1)counts[i]<=0;
        end else begin
            sense_meta<=sense_n;sense_sync<=sense_meta;
            if(word_valid&&word_ready)waiting<=1;
            if(state==CHARGE&&waiting&&word_latched)begin timer<=0;finished<=0;state<=MEASURE;end
            if(waiting&&word_done)begin
                waiting<=0;
                case(state)
                    DISABLE:state<=ADDRESS;
                    ADDRESS:state<=CONNECT;
                    CONNECT:begin dis_timer<=0;state<=DISCHARGE;end
                endcase
            end
            case(state)
                DISCHARGE:if(dis_timer==DISCHARGE_CYCLES-1)begin
                    // Bad starting polarity is a fault, not a small capacitance.
                    fault<=~sense_sync;state<=CHARGE;
                end else dis_timer<=dis_timer+1'b1;
                MEASURE:begin
                    timer<=timer+1'b1;
                    for(i=0;i<LANES;i=i+1)if(!finished[i])begin
                        if(!sense_sync[i])begin counts[i]<=timer;finished[i]<=1;end
                        else if(timer==TIMEOUT_CYCLES-1)begin
                            counts[i]<=TIMEOUT_CYCLES[CW-1:0];finished[i]<=1;fault[i]<=1;
                        end
                    end
                    if(&finished)state<=PUBLISH;
                end
                PUBLISH:begin
                    if(!row_valid)begin
                        for(i=0;i<LANES;i=i+1)row_count[i*CW+:CW]<=counts[i];
                        row_address<=address;row_sequence<=scan_sequence;row_fault<=fault;row_valid<=1;
                    end else if(row_ready)begin
                        row_valid<=0;previous_address<=address;address<=address+1'b1;
                        if(address==15)scan_sequence<=scan_sequence+1'b1;
                        state<=DISABLE;
                    end
                end
            endcase
        end
    end
endmodule
