//=============================================================================
// strip_ctrl.v -- octave strip: 5-cell_t absolute position selector
//
// Per pitch/octave spec v2.0 section 3.2:
//   cell_t 0 = -1 octave, cell_t 1 = 0 (default), cell_t 2/3/4 = +1/+2/+3
//   a press must be held >= HOLD_MS ms to take effect (anti-mistouch, P13)
//   several cells touched at once -> no action
//   one-hot LED output for the current position (active high, external LED)
//   this module never emits note events (P11, P15)
//
// NOTE: deliberately conservative Verilog (no parameterised port widths,
// no loops inside always @(*), no part-selects of integer variables,
// no reserved words as signal names -- note: 'hold' is a Verilog keyword),
// because older iverilog builds reject those combinations.
//=============================================================================
module strip_ctrl #(
    parameter CLK_HZ  = 27000000,
    parameter HOLD_MS = 100
)(
    clk, rst_n, cell_t, pos, led
);
    input  wire        clk;
    input  wire        rst_n;
    input  wire [4:0]  cell_t;      // 1 = this cell_t is touched
    output reg  [2:0]  pos;       // 0..4, power-on default 1 (= 0 position)
    output reg  [4:0]  led;       // one-hot, active high

    localparam [31:0] CNT = (CLK_HZ / 1000) * HOLD_MS;   // clocks for HOLD_MS

    reg [31:0] hold_cnt;
    reg        committed;

    // how many cells are touched, and the index of the highest one
    wire [2:0] hit = {2'b00, cell_t[0]} + {2'b00, cell_t[1]} + {2'b00, cell_t[2]}
                   + {2'b00, cell_t[3]} + {2'b00, cell_t[4]};
    wire [2:0] idx = cell_t[4] ? 3'd4 :
                     cell_t[3] ? 3'd3 :
                     cell_t[2] ? 3'd2 :
                     cell_t[1] ? 3'd1 : 3'd0;
    wire       onehot = (hit == 3'd1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pos       <= 3'd1;
            led       <= 5'b00010;
            hold_cnt      <= 32'd0;
            committed <= 1'b0;
        end else begin
            if (!onehot) begin
                hold_cnt      <= 32'd0;
                committed <= 1'b0;
            end else if (!committed) begin
                if (hold_cnt >= (CNT - 32'd1)) begin
                    pos       <= idx;
                    committed <= 1'b1;
                end else begin
                    hold_cnt <= hold_cnt + 32'd1;
                end
            end
            led <= (5'b00001 << pos);
        end
    end

endmodule
