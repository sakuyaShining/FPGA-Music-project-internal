`timescale 1ns/1ps
//=============================================================================
// uart_beacon.v -- diagnostic heartbeat transmitter (byte supplied externally)
//
// PURPOSE: first-order board bring-up question -- "is the board really running
//          MY bitstream?". If no heartbeat arrives, the problem is in the
//          bitstream / pins / clock layer, not in the synth engine.
//
// FEATURES:
//   * no reset dependency: self-starting, transmits as long as clk runs
//   * the byte comes from byte_i in real time, so it doubles as an on-board
//     probe: encode rst_n / por_done / a slow counter bit into the byte and you
//     can see at a glance where the design is stuck
//
// FIXED 2026-10-23 (two real bugs found while reading probe bytes on the board):
//   1) The stop bit was never driven. The old `bi == 9` branch reloaded the
//      shifter but never assigned tx, so the line kept the last DATA bit value
//      through the stop-bit slot. Any byte whose MSB is 0 therefore had no
//      stop bit at all and the receiver could merge frames.
//      -> now every one of the 10 bit slots drives tx from sh[0].
//   2) GAP was documented as "how many BIT TIMES of idle between bytes" but was
//      decremented once per CLOCK, so GAP=200 meant 200 clocks (7.4 us), not
//      200 bit times (1.74 ms). Measured frame rate on the board was ~12.7 kB/s,
//      which exceeds the 11.52 kB/s ceiling of 115200 8N1 -- proof that frames
//      were being packed tighter than a legal UART frame.
//      -> GAP now really counts bit times.
//
// Frame format: 8N1, LSB first. Frame period = (10 + GAP) bit times.
//=============================================================================
module uart_beacon #(
    parameter integer CLK_HZ = 27000000,
    parameter integer BAUD   = 115200,
    parameter integer GAP    = 200       // idle bit times between bytes
)(
    input  wire       clk,
    input  wire [7:0] byte_i,
    output reg        tx
);

    localparam integer BIT = CLK_HZ / BAUD;

    reg [15:0] div;      // clock divider within one bit time
    reg [3:0]  bi;       // bit index: 0 = start, 1..8 = data, 9 = stop
    reg [9:0]  sh;       // {stop, data[7:0], start} -- LSB goes out first
    reg [15:0] gap;      // remaining idle BIT TIMES
    reg [7:0]  lat;      // payload latched at frame start

    always @(posedge clk) begin
        if (gap != 16'd0) begin
            // ---- idle: line high, burn GAP bit times ----
            tx <= 1'b1;
            if (div == BIT - 1) begin
                div <= 16'd0;
                gap <= gap - 1'b1;
            end else begin
                div <= div + 1'b1;
            end
        end
        else if (div == BIT - 1) begin
            // ---- end of a bit slot: present the next bit ----
            div <= 16'd0;
            tx  <= sh[0];
            sh  <= {1'b1, sh[9:1]};
            if (bi == 4'd9) begin
                // stop bit just finished -> reload and go idle
                bi  <= 4'd0;
                lat <= byte_i;
                sh  <= {1'b1, byte_i, 1'b0};
                gap <= GAP[15:0];
            end else begin
                bi <= bi + 1'b1;
            end
        end
        else begin
            div <= div + 1'b1;
        end
    end

    initial begin
        div = 16'd0;
        bi  = 4'd0;
        sh  = {1'b1, 8'h5A, 1'b0};
        gap = 16'd0;
        tx  = 1'b1;
        lat = 8'h5A;
    end

endmodule
