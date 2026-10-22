//=============================================================================
// tb_led_ind.v -- LED indication criteria (spec v2.0 section 6)
//
//   P10  octave patterns pairwise distinct (5 positions)
//   P16  score mode vs manual mode are distinguishable
//   P17  pitch ladder maps the next note to the right band (table driven)
//   P18  beat indication is stretched (single-cycle pulse stays visible)
//   P19  polarity: with ACTIVE_LOW=1 the output is the inverse
//
// Prints PASS / FAIL per check (ASCII names) and a summary at the end.
//=============================================================================
`timescale 1ns/1ps

module tb_led_ind;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #10 clk = ~clk;                    // 50 MHz

    integer errors = 0;
    integer i;

    //------------------------------------------------------------ DUT (active high)
    reg        score_mode = 1'b0;
    reg        beat       = 1'b0;
    reg [6:0]  next_note  = 7'd60;
    reg [2:0]  pos        = 3'd1;
    reg        seq_run    = 1'b0;
    reg        test_mode  = 1'b0;
    wire [5:0] led;

    led_ind #(.CLK_HZ(50000000), .ACTIVE_LOW(0), .BEAT_MS(80)) dut (
        .clk(clk), .rst_n(rst_n), .score_mode(score_mode), .beat(beat),
        .next_note(next_note), .pos(pos), .seq_run(seq_run),
        .test_mode(test_mode), .led(led)
    );

    //------------------------------------------------------------ DUT (active low)
    wire [5:0] led_lo;
    led_ind #(.CLK_HZ(50000000), .ACTIVE_LOW(1), .BEAT_MS(80)) dut_lo (
        .clk(clk), .rst_n(rst_n), .score_mode(score_mode), .beat(beat),
        .next_note(next_note), .pos(pos), .seq_run(seq_run),
        .test_mode(test_mode), .led(led_lo)
    );

    //------------------------------------------------------------ helpers
    task wait_cycles;
        input integer n;
        integer k;
        begin for (k = 0; k < n; k = k + 1) @(posedge clk); end
    endtask

    task check;
        input [255:0] name;
        input integer got;
        input integer exp;
        begin
            if (got === exp) $display("  PASS  %0s", name);
            else begin
                $display("  FAIL  %0s  got %0d expected %0d", name, got, exp);
                errors = errors + 1;
            end
        end
    endtask

    // 需要的音高范围 -> band（与 RTL 的 band_of 一致）
    function [2:0] band_ref;
        input [6:0] n;
        begin
            if      (n <= 7'd51) band_ref = 3'd0;
            else if (n <= 7'd66) band_ref = 3'd1;
            else if (n <= 7'd81) band_ref = 3'd2;
            else if (n <= 7'd96) band_ref = 3'd3;
            else                 band_ref = 3'd4;
        end
    endfunction

    reg [2:0] pats [0:4];
    integer   ones, band_got, manual_low, score_low;

    initial begin
        $display("==============================================================");
        $display(" LED indication criteria");
        $display("==============================================================");

        rst_n = 1'b0;
        wait_cycles(10);
        rst_n = 1'b1;
        wait_cycles(10);

        //========================================================== P10 档位图案
        $display(" P10 octave patterns (must be pairwise distinct)");
        score_mode = 1'b0; seq_run = 1'b0; test_mode = 1'b0;
        for (i = 0; i < 5; i = i + 1) begin
            pos = i;
            wait_cycles(2);
            pats[i] = led[2:0];
        end
        // 与规格表一致
        check("P10 pos0 pattern", pats[0], 3'b001);
        check("P10 pos1 pattern", pats[1], 3'b011);
        check("P10 pos2 pattern", pats[2], 3'b010);
        check("P10 pos3 pattern", pats[3], 3'b100);
        check("P10 pos4 pattern", pats[4], 3'b110);
        // 两两不同
        for (i = 0; i < 5; i = i + 1) begin
            if (i > 0) begin
                if (pats[i] === pats[i-1]) begin
                    $display("  FAIL  P10 pattern %0d equals %0d", i, i-1);
                    errors = errors + 1;
                end
            end
        end

        //========================================================== P17 音高台阶
        $display(" P17 pitch ladder (table driven)");
        score_mode = 1'b1;
        beat = 1'b0;
        wait_cycles(4);                      // 让拍点指示熄灭
        for (i = 0; i < 7; i = i + 1) begin
            case (i)
                0: next_note = 7'd36;
                1: next_note = 7'd60;
                2: next_note = 7'd66;
                3: next_note = 7'd72;
                4: next_note = 7'd84;
                5: next_note = 7'd100;
                6: next_note = 7'd51;
            endcase
            wait_cycles(2);
            ones = led[0] + led[1] + led[2] + led[3] + led[4];
            check("P17 exactly one ladder bit", ones, 1);
            // 找出亮的是第几位
            band_got = 0;
            if (led[1]) band_got = 1;
            if (led[2]) band_got = 2;
            if (led[3]) band_got = 3;
            if (led[4]) band_got = 4;
            check("P17 band matches reference", band_got, band_ref(next_note));
        end

        //========================================================== P16 模式可辨
        $display(" P16 score mode vs manual mode");
        score_mode = 1'b1; next_note = 7'd72; wait_cycles(2);   // band 2 -> ladder bit2
        score_low = led[4:0];
        score_mode = 1'b0; pos = 3'd2;      wait_cycles(2);     // pattern 2 -> bit1
        manual_low = led[4:0];
        if (score_low === manual_low) begin
            $display("  FAIL  P16 modes look identical (0x%02h)", score_low);
            errors = errors + 1;
        end else begin
            $display("  PASS  P16 modes differ (score 0x%02h vs manual 0x%02h)", score_low, manual_low);
        end

        //========================================================== P18 拍点保持
        $display(" P18 beat indication is stretched");
        score_mode = 1'b1;
        beat = 1'b1; @(posedge clk); beat = 1'b0;
        wait_cycles(1000);                   // 20 us，远小于 80 ms
        check("P18 beat still visible after 1000 cycles", led[5], 1);
        wait_cycles(5000000);                // 100 ms，应已熄灭
        check("P18 beat cleared after 100 ms", led[5], 0);
        score_mode = 1'b0;

        //========================================================== P19 极性
        $display(" P19 polarity");
        wait_cycles(2);
        check("P19 active-low output is inverted", led_lo, (~led) & 6'h3F);

        $display("==============================================================");
        if (errors == 0) $display(" ALL LED CRITERIA PASS");
        else             $display(" FAILED %0d check(s)", errors);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #20_000_000_000;
        $display(" [watchdog] timeout");
        $display(" FAILED %0d check(s) (including timeout)", errors + 1);
        $finish;
    end

endmodule
