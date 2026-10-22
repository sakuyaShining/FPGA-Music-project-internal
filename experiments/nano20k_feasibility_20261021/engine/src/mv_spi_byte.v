// Controller-level candidate, not yet wired to the user's module.
// Mode 0, MSB first. HALF_CYCLES=2 at 27MHz gives SCK=6.75MHz.
module mv_spi_byte #(parameter integer HALF_CYCLES=2)(
    input wire clk, rst_n,
    input wire valid, dc_in,
    input wire [7:0] data_in,
    output wire ready,
    output reg done,
    output reg cs_n, sck, mosi, dc
);
    localparam IDLE=0, SHIFT=1, HOLD=2, GAP=3;
    reg [1:0] state;
    reg [15:0] divider;
    reg [2:0] bit_index;
    reg [7:0] shift;
    assign ready = state==IDLE;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state<=IDLE; divider<=0; bit_index<=7; shift<=0;
            done<=0; cs_n<=1; sck<=0; mosi<=0; dc<=0;
        end else begin
            done<=0;
            case (state)
                IDLE: if (valid) begin
                    cs_n<=0; dc<=dc_in; mosi<=data_in[7]; shift<=data_in;
                    divider<=HALF_CYCLES-1; bit_index<=7; state<=SHIFT;
                end
                SHIFT: if (divider!=0) divider<=divider-1;
                else begin
                    divider<=HALF_CYCLES-1;
                    if (!sck) sck<=1;
                    else begin
                        sck<=0;
                        if (bit_index==0) state<=HOLD;
                        else begin
                            bit_index<=bit_index-1;
                            shift<={shift[6:0],1'b0}; mosi<=shift[6];
                        end
                    end
                end
                HOLD: if (divider!=0) divider<=divider-1;
                else begin
                    cs_n<=1; divider<=HALF_CYCLES-1; state<=GAP;
                end
                GAP: if (divider!=0) divider<=divider-1;
                else begin state<=IDLE; done<=1; end
            endcase
        end
    end
endmodule
