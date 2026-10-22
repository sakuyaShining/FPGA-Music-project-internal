`timescale 1ns/1ps
module tb_right_fader_follow;
    reg clk = 0;
    always #5 clk = ~clk;
    reg rst_n = 0, tick = 0;
    reg [7:0] valid = 0, load_mask = 0;
    reg [95:0] target = 0, load_data = 0;
    reg [11:0] step = 0;
    wire [95:0] current;
    integer fails = 0, i;
    right_fader_follow dut(clk, rst_n, tick, valid, target, step, load_mask, load_data, current);
    task cycle;
        begin @(posedge clk); #1; @(negedge clk); end
    endtask
    task expect_value;
        input integer lane;
        input [11:0] expected;
        begin
            if (current[lane*12 +: 12] !== expected) begin
                $display("FAIL lane=%0d expected=%0d actual=%0d", lane, expected, current[lane*12 +: 12]);
                fails = fails + 1;
            end
        end
    endtask
    initial begin
        cycle; rst_n = 1;
        // Independent up/down lanes; no tick means no movement.
        load_mask = 8'h02; load_data[23:12] = 12'd4000; cycle; load_mask = 0;
        valid = 8'h03; target[11:0] = 12'd1000; target[23:12] = 12'd3000; step = 12'd64;
        cycle; expect_value(0, 0); expect_value(1, 4000);
        tick = 1; cycle; expect_value(0, 64); expect_value(1, 3936);
        valid[0] = 0;
        repeat (3) cycle;
        expect_value(0, 64); expect_value(1, 3744);
        // Release freezes current; renewed touch continues from held value.
        valid = 8'h01; target[11:0] = 12'd70; cycle;
        expect_value(0, 70); expect_value(1, 3744);
        target[11:0] = 12'd2; step = 12'd4095; cycle; expect_value(0, 2);
        target[11:0] = 12'd4095; cycle; expect_value(0, 4095);
        // Two-finger mapper can supply midpoint; target changes do not jump current.
        step = 12'd10; target[11:0] = 12'd2048; cycle; expect_value(0, 4085);
        step = 0; repeat (2) cycle; expect_value(0, 4085);
        // Load has priority, then chase resumes; all eight lanes work independently.
        load_mask = 8'hff;
        for (i=0; i<8; i=i+1) load_data[i*12 +: 12] = i * 100;
        step = 12'd10; valid = 8'hff; cycle;
        for (i=0; i<8; i=i+1) expect_value(i, i * 100);
        load_mask = 0;
        for (i=0; i<8; i=i+1) target[i*12 +: 12] = i * 100 + 5;
        cycle;
        for (i=0; i<8; i=i+1) expect_value(i, i * 100 + 5);
        valid = 0; repeat (2) cycle;
        for (i=0; i<8; i=i+1) expect_value(i, i * 100 + 5);
        $display("RESULT right_fader_follow %s fails=%0d", fails == 0 ? "PASS" : "FAIL", fails);
        if (fails != 0) $fatal(1, "right_fader_follow failed");
        $finish;
    end
endmodule
