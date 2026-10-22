// Configurable control-group -> partial mapping and a replaceable audition LUT.
// gain_valid stays asserted until accepted. Restore cancels stale in-flight work.
module rh_fader_gain_map #(
    parameter integer NF=8,
    parameter integer PART=16,
    parameter LUT_FILE="fader_gain_q8.hex"
)(
    input wire clk,rst_n,
    input wire fader_valid,
    output wire fader_ready,
    input wire [NF*10-1:0] fader_y,
    input wire [PART*((NF<2)?1:$clog2(NF))-1:0] part_to_control,
    input wire restore_valid,
    output wire gain_valid,
    input wire gain_ready,
    output reg [PART*10-1:0] gain_target,
    output reg map_error
);
    localparam CW=(NF<2)?1:$clog2(NF);
    localparam PW=(PART<2)?1:$clog2(PART);
    localparam IDLE=2'd0,READ=2'd1,STORE=2'd2,PUBLISH=2'd3;
    reg [1:0] state;
    reg [NF*10-1:0] positions_q;
    reg [PART*CW-1:0] map_q;
    reg [PW-1:0] part;
    // Three hexadecimal digits are twelve bits; slice explicitly at the port.
    // Asset generation proves all table values fit the ten-bit Q8 interface.
    reg [11:0] rom[0:1023];
    reg [11:0] rom_q;
    wire [CW-1:0] control=map_q[part*CW+:CW];
    wire [9:0] y=positions_q[control*10+:10];
    wire [PART-1:0] valid_map;
    genvar g;
    generate for(g=0;g<PART;g=g+1)begin: validate_map
        assign valid_map[g]=part_to_control[g*CW+:CW]<NF;
    end endgenerate
    initial $readmemh(LUT_FILE,rom);
    assign fader_ready=state==IDLE&&!restore_valid;
    assign gain_valid=state==PUBLISH&&!restore_valid;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;positions_q<=0;map_q<=0;part<=0;rom_q<=256;
            gain_target<={PART{10'd256}};map_error<=0;
        end else begin
            map_error<=0;
            if(restore_valid)state<=IDLE;
            else case(state)
                IDLE:if(fader_valid)begin
                    if(!(&valid_map))map_error<=1;
                    else begin positions_q<=fader_y;map_q<=part_to_control;part<=0;state<=READ;end
                end
                READ:begin rom_q<=rom[y];state<=STORE;end
                STORE:begin
                    gain_target[part*10+:10]<=rom_q[9:0];
                    if(part==PART-1)state<=PUBLISH;else begin part<=part+1'b1;state<=READ;end
                end
                PUBLISH:if(gain_ready)state<=IDLE;
                default:state<=IDLE;
            endcase
        end
    end
endmodule
