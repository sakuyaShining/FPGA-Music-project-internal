//=============================================================================
// led_ind.v -- LED indication for the 6 on-board LEDs
//
// Per pitch/octave spec v2.0 section 6 (mode-dependent allocation):
//
//   score playback mode:  led[5] = beat flash (stretched so it is visible)
//                         led[4:0] = pitch ladder of the next score note
//   manual play mode:     led[5] = heartbeat (1 Hz)
//                         led[2:0] = octave position pattern
//                         led[3] = sequencer running, led[4] = test mode
//
// Internal logic uses "1 = ON"; the final output is inverted when the board
// LEDs are common-anode (active low). External panel LEDs are active high,
// so the two polarities are handled by the ACTIVE_LOW parameter.
//=============================================================================
module led_ind #(
    parameter CLK_HZ     = 27000000,
    parameter ACTIVE_LOW = 1,          // 1 = board LEDs are common anode (active low)
    parameter BEAT_MS    = 80          // how long the beat indication stays on
)(
    clk, rst_n, score_mode, beat, next_note, pos, seq_run, test_mode, led
);
    input  wire       clk;
    input  wire       rst_n;
    input  wire       score_mode;      // 1 = sequencer/score is playing
    input  wire       beat;            // single-cycle pulse from the sequencer
    input  wire [6:0] next_note;       // next note of the score (pitch ladder)
    input  wire [2:0] pos;             // octave position 0..4
    input  wire       seq_run;         // sequencer running
    input  wire       test_mode;       // test mode active
    output wire [5:0] led;             // final LED outputs (polarity applied)

    //-------------------------------------------------------------------------
    // heartbeat: toggle every 0.5 s -> 1 Hz
    //-------------------------------------------------------------------------
    localparam [31:0] HB_HALF = CLK_HZ / 2;
    reg [31:0] hb_cnt;
    reg        hb;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            hb_cnt <= 32'd0;
            hb     <= 1'b0;
        end else if (hb_cnt >= (HB_HALF - 32'd1)) begin
            hb_cnt <= 32'd0;
            hb     <= ~hb;
        end else begin
            hb_cnt <= hb_cnt + 32'd1;
        end
    end

    //-------------------------------------------------------------------------
    // beat flash: stretch the single-cycle pulse so a human can see it
    //-------------------------------------------------------------------------
    localparam [31:0] BEAT_CNT = (CLK_HZ / 1000) * BEAT_MS;
    reg [31:0] beat_cnt;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            beat_cnt <= 32'd0;
        end else if (beat) begin
            beat_cnt <= BEAT_CNT;
        end else if (beat_cnt != 32'd0) begin
            beat_cnt <= beat_cnt - 32'd1;
        end
    end
    wire beat_on = (beat_cnt != 32'd0);

    //-------------------------------------------------------------------------
    // pitch ladder: absolute note -> one of 5 bands
    //   band 0: note <= 51      band 1: 52..66    band 2: 67..81
    //   band 3: 82..96          band 4: >= 97
    //-------------------------------------------------------------------------
    function [2:0] band_of;
        input [6:0] n;
        begin
            if      (n <= 7'd51) band_of = 3'd0;
            else if (n <= 7'd66) band_of = 3'd1;
            else if (n <= 7'd81) band_of = 3'd2;
            else if (n <= 7'd96) band_of = 3'd3;
            else                 band_of = 3'd4;
        end
    endfunction

    wire [2:0] band = band_of(next_note);
    wire [4:0] ladder = (5'b00001 << band);      // one-hot, 1 = on

    //-------------------------------------------------------------------------
    // octave position pattern (manual mode), see spec table 6.2
    //-------------------------------------------------------------------------
    function [2:0] oct_pat;
        input [2:0] p;
        begin
            case (p)
                3'd0: oct_pat = 3'b001;
                3'd1: oct_pat = 3'b011;
                3'd2: oct_pat = 3'b010;
                3'd3: oct_pat = 3'b100;
                3'd4: oct_pat = 3'b110;
                default: oct_pat = 3'b001;
            endcase
        end
    endfunction

    //-------------------------------------------------------------------------
    // combine
    //-------------------------------------------------------------------------
    reg [5:0] led_on;                    // 1 = ON
    always @(*) begin
        if (score_mode) begin
            led_on = {beat_on, ladder};  // led[5] = beat, led[4:0] = ladder
        end else begin
            led_on = {hb, test_mode, seq_run, oct_pat(pos)};
        end
    end

    assign led = ACTIVE_LOW ? ~led_on : led_on;

endmodule
