`timescale 1ns/1ps
//=============================================================================
// tb_rst_gen -- reset generator (engine/src/rst_gen.v) criteria, 11 checks
//
// Background: measured on the board, pin 87 idles LOW. Every old cst treated it
// as an active-low reset, so the core was held in reset forever and the product
// top never booted. rst_gen.v uses a power-on reset so the design always boots,
// and treats the button as an active-HIGH debounced extra reset.
//
// NOTE: all messages are ASCII on purpose. iverilog prints a bit-vector with
// %0s by trimming leading zero bytes, which slices UTF-8 multi-byte characters
// in half and turns the log into mojibake.
//
//   A1  rst_n is 0 during POR
//   A2  POR releases exactly on cycle 2^(POR_BITS-1)
//   A3  rst_n stays 1 after release (button idle)
//   A4  rst_n goes low while the button is held (after debounce)
//   A5  rst_n returns high after release
//   A6  debounce window is exactly 2^DB_BITS cycles (1 short = ignored)
//   A7  glitches shorter than the window are ignored entirely
//   A8  button held at power-up: still boots after release (no deadlock)
//   A9  long press (100k cycles) then release: rst_n recovers
//   A10 rst_n never glitches high while the button is held
//=============================================================================
module tb_rst_gen;

    // Small widths so the simulation finishes fast.
    // Product uses POR_BITS=16 (1.21 ms @27MHz) and DB_BITS=14 (0.61 ms).
    localparam integer PB = 6;      // release point = 2^5 = 32 cycles
    localparam integer DB = 4;      // debounce window = 2^4 = 16 cycles

    reg  clk = 0;
    reg  btn = 0;
    wire rst_n, por_done, btn_state;

    rst_gen #(.POR_BITS(PB), .DB_BITS(DB)) dut (
        .clk(clk), .btn(btn),
        .rst_n(rst_n), .por_done(por_done), .btn_state(btn_state)
    );

    always #5 clk = ~clk;   // 100 MHz sim clock, only to run fast

    integer errors = 0;
    integer cyc;

    task check;
        input cond;
        input [8*96-1:0] msg;
        begin
            if (!cond) begin
                $display("  [FAIL] %0s", msg);
                errors = errors + 1;
            end else begin
                $display("  [OK]   %0s", msg);
            end
        end
    endtask

    task tick;
        begin
            @(posedge clk);
            #1;
        end
    endtask

    initial begin
        $display("=== tb_rst_gen  POR_BITS=%0d (release @ %0d cyc)  DB_BITS=%0d (window %0d cyc)",
                 PB, (1<<(PB-1)), DB, (1<<DB));

        // ---------- A1 ----------
        tick;
        check(rst_n === 1'b0, "A1a POR cycle 1: rst_n = 0");
        for (cyc = 0; cyc < (1<<(PB-1)) - 2; cyc = cyc + 1) tick;
        check(rst_n === 1'b0, "A1b POR, 2 cycles before release: rst_n = 0");
        check(por_done === 1'b0, "A1c POR in progress: por_done = 0");

        // ---------- A2 ----------
        tick;
        check(por_done === 1'b1, "A2a cycle 2^(POR_BITS-1): por_done = 1");
        check(rst_n === 1'b1,    "A2b same cycle: rst_n released");

        // ---------- A3 ----------
        for (cyc = 0; cyc < 200; cyc = cyc + 1) tick;
        check(rst_n === 1'b1, "A3  button idle 200 cycles: rst_n stays 1");

        // ---------- A6: window boundary ----------
        btn = 1'b1;
        for (cyc = 0; cyc < (1<<DB) - 2; cyc = cyc + 1) tick;
        check(rst_n === 1'b1, "A6a pressed for 2^DB-1 cycles: not yet accepted");
        tick; tick;
        check(rst_n === 1'b0, "A6b one more cycle (full 2^DB window): rst_n low");
        check(btn_state === 1'b1, "A6c btn_state = 1");

        // ---------- A4 + A10 ----------
        for (cyc = 0; cyc < 500; cyc = cyc + 1) begin
            tick;
            if (rst_n !== 1'b0) begin
                $display("  [FAIL] A10 rst_n glitched high at cycle %0d while held", cyc);
                errors = errors + 1;
                cyc = 500;
            end
        end
        check(rst_n === 1'b0, "A4  held 500 cycles: rst_n stays 0");
        if (errors == 0) $display("  [OK]   A10 no glitch while held");

        // ---------- A5 ----------
        btn = 1'b0;
        for (cyc = 0; cyc < (1<<DB) + 2; cyc = cyc + 1) tick;
        check(rst_n === 1'b1,    "A5a release: rst_n back to 1");
        check(btn_state === 1'b0, "A5b btn_state back to 0");

        // ---------- A7 ----------
        for (cyc = 0; cyc < 20; cyc = cyc + 1) begin
            btn = 1'b1; repeat (8) tick;
            btn = 1'b0; repeat (8) tick;
        end
        check(rst_n === 1'b1, "A7  20 glitches of 8 cycles all ignored, rst_n = 1");

        // ---------- A9 ----------
        btn = 1'b1;
        for (cyc = 0; cyc < 100000; cyc = cyc + 1) tick;
        check(rst_n === 1'b0, "A9a long press 100k cycles: still in reset");
        btn = 1'b0;
        for (cyc = 0; cyc < (1<<DB) + 4; cyc = cyc + 1) tick;
        check(rst_n === 1'b1, "A9b after long press release: rst_n = 1 (no deadlock)");

        $display("RESULT(main): %0s", (errors == 0) ? "PASS" : "FAIL");
        $finish;
    end

    //-------------------------------------------------------------------------
    // A8: independent instance, button already held at power-up
    //-------------------------------------------------------------------------
    reg  clk2 = 0;
    reg  btn2 = 1'b1;
    wire rst_n2, por_done2, btn_state2;
    always #5 clk2 = ~clk2;

    rst_gen #(.POR_BITS(PB), .DB_BITS(DB)) dut2 (
        .clk(clk2), .btn(btn2),
        .rst_n(rst_n2), .por_done(por_done2), .btn_state(btn_state2)
    );

    integer e2 = 0;
    initial begin
        #1;
        if (rst_n2 !== 1'b0) begin $display("  [FAIL] A8a held at power-up: rst_n should be 0"); e2 = e2 + 1; end
        else $display("  [OK]   A8a held at power-up: rst_n = 0");

        repeat ((1<<(PB-1)) + (1<<DB) + 20) @(posedge clk2);
        #1;
        if (rst_n2 !== 1'b0) begin $display("  [FAIL] A8b POR done but still held: rst_n should be 0"); e2 = e2 + 1; end
        else $display("  [OK]   A8b POR done but still held: rst_n stays 0");
        if (por_done2 !== 1'b1) begin $display("  [FAIL] A8c por_done should be 1"); e2 = e2 + 1; end
        else $display("  [OK]   A8c por_done = 1");

        btn2 = 1'b0;
        repeat ((1<<DB) + 4) @(posedge clk2);
        #1;
        if (rst_n2 !== 1'b1) begin $display("  [FAIL] A8d after release: rst_n should be 1"); e2 = e2 + 1; end
        else $display("  [OK]   A8d after release: rst_n = 1 (power-up press does not deadlock)");

        $display("RESULT(A8): %0s", (e2 == 0) ? "PASS" : "FAIL");
    end

endmodule
