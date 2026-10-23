`timescale 1ns/1ps
//=============================================================================
// tb_beacon -- uart_beacon criteria (9 checks)
//
// Why this testbench exists: the ORIGINAL uart_beacon had two bugs that the
// previous version of this file could NOT catch.
//
//   BUG 1  The stop bit was never driven. The old tb used 0x96, whose MSB is 1,
//          so the line happened to already be high during the stop-bit slot and
//          the check passed by accident. Any byte with MSB=0 (e.g. 0x0F) went
//          out with NO stop bit. -> B1 uses 0x0F on purpose.
//
//   BUG 2  GAP was documented as "idle BIT TIMES" but was decremented once per
//          CLOCK, so frames were packed ~23x tighter than intended. On the board
//          this produced ~12.7 kB/s, above the 11.52 kB/s ceiling of 115200 8N1,
//          which is physically impossible for legal frames -- that is how it was
//          found. -> B3 measures the frame period; B7 checks throughput.
//
// TIMING MODEL (important for reading this file):
//   The beacon latches byte_i into the shift register at the END of the stop
//   bit. So setting byte_i and receiving ONE frame can still yield the previous
//   value. Every check therefore sets byte_i and looks at the SECOND frame.
//
//   B1  0x0F round-trips and its stop bit is 1      (catches BUG 1)
//   B2  0xA5 round-trips                            (catches bit-order reversal)
//   B3  frame period == (10+GAP) bit times, +-2%    (catches BUG 2)
//   B4  idle line stays high throughout the gap
//   B5  GAP=0: 4 back-to-back MSB=0 bytes all decode correctly
//   B6  byte_i changing mid-frame does not corrupt the frame in flight
//   B7  throughput stays below the 115200 8N1 ceiling
//   B8  stop bit present on every back-to-back frame
//   B9  consecutive frames are byte-exact with no drift over 8 frames
//=============================================================================
module tb_beacon;

    localparam integer CLK_HZ = 27000000;
    localparam integer BAUD   = 115200;
    localparam integer GAP    = 200;
    localparam integer BIT    = CLK_HZ / BAUD;          // 234 clocks
    localparam real    BIT_NS = 1.0e9 * BIT / CLK_HZ;   // 8666.7 ns
    localparam real    HALF   = BIT_NS / 2.0;

    reg        clk = 0;
    reg  [7:0] byte_i = 8'h5A;
    wire       tx;

    uart_beacon #(.CLK_HZ(CLK_HZ), .BAUD(BAUD), .GAP(GAP))
        dut (.clk(clk), .byte_i(byte_i), .tx(tx));

    always #(18.5185) clk = ~clk;   // 27 MHz

    integer errors = 0;
    integer i;

    task check;
        input cond;
        input [8*80-1:0] msg;
        begin
            if (!cond) begin $display("  [FAIL] %0s", msg); errors = errors + 1; end
            else $display("  [OK]   %0s", msg);
        end
    endtask

    //---- 8N1 receiver: wait for a start edge, sample at each bit centre ----
    task rx_byte;
        output [7:0] b;
        output       stop_ok;
        integer      j;
        begin
            @(negedge tx);
            #(HALF);
            if (tx !== 1'b0) begin
                b = 8'hXX; stop_ok = 1'b0;
            end else begin
                #(BIT_NS);
                for (j = 0; j < 8; j = j + 1) begin
                    b[j] = tx;
                    #(BIT_NS);
                end
                stop_ok = (tx === 1'b1);   // now at the stop-bit centre
            end
        end
    endtask

    //---- set byte_i, then take the frame that is guaranteed to carry it ----
    task set_and_get;
        input  [7:0] want;
        output [7:0] b;
        output       stop_ok;
        reg    [7:0] tmp;
        reg          tok;
        begin
            byte_i = want;
            rx_byte(tmp, tok);    // may still be the previously latched byte
            rx_byte(b, stop_ok);  // latched after `want` was in place
        end
    endtask

    reg [7:0] got;
    reg       ok;
    real      t0, t1, period, expect;

    initial begin
        $display("=== tb_beacon  CLK=%0d BAUD=%0d GAP=%0d (BIT=%0d clk, %.1f ns)",
                 CLK_HZ, BAUD, GAP, BIT, BIT_NS);

        // Drain the frames sent with the power-up shifter contents
        rx_byte(got, ok);
        rx_byte(got, ok);

        //---------- B1: MSB=0 byte, stop bit must be 1 ----------
        set_and_get(8'h0F, got, ok);
        check(got === 8'h0F, "B1a byte 0x0F round-trips");
        check(ok  === 1'b1,  "B1b stop bit is 1 for 0x0F (old code failed here)");

        //---------- B2: non-palindrome, checks bit order ----------
        set_and_get(8'hA5, got, ok);
        check(got === 8'hA5, "B2  byte 0xA5 round-trips (bit order LSB-first)");

        //---------- B3: frame period ----------
        // Measure start-edge to start-edge. Skip 10.3 bit times first so we are
        // past the stop bit and the next negedge really is the next start bit.
        byte_i = 8'h3C;
        rx_byte(got, ok);                 // settle
        rx_byte(got, ok);                 // now 0x3C is in flight
        #(BIT_NS);                        // step past the stop-bit centre
        @(negedge tx); t0 = $realtime;    // frame A start edge
        #(10.3 * BIT_NS);                 // past the stop bit, into the gap
        @(negedge tx); t1 = $realtime;    // frame B start edge
        period = t1 - t0;
        expect = (10 + GAP) * BIT_NS;
        $display("   measured frame period = %.0f ns, expected (10+%0d)*%.1f = %.0f ns",
                 period, GAP, BIT_NS, expect);
        check((period > expect * 0.98) && (period < expect * 1.02),
              "B3  frame period == (10+GAP) bit times (catches GAP-as-clocks bug)");

        //---------- B4: idle line high throughout the gap ----------
        // B3 left us at frame B's start edge, i.e. INSIDE a frame. Consume that
        // frame first (rx_byte returns at the stop-bit centre), then step 2 bit
        // times to land well inside the 200-bit-time gap.
        rx_byte(got, ok);
        #(2 * BIT_NS);
        begin : idle_check
            integer dropped;
            dropped = 0;
            repeat (50) begin
                @(posedge clk);
                if (tx !== 1'b1) dropped = dropped + 1;
            end
            check(dropped == 0, "B4  idle line stays high inside the gap");
        end

        //---------- B6: mid-frame change must not corrupt the frame ----------
        byte_i = 8'h96;
        rx_byte(got, ok);            // settle
        rx_byte(got, ok);            // 0x96 in flight, and now at its stop centre
        fork
            rx_byte(got, ok);        // frame already loaded with 0x96
            begin
                #(3 * BIT_NS);       // change the byte mid-frame
                byte_i = 8'h71;
            end
        join
        check(got === 8'h96, "B6  mid-frame byte_i change does not corrupt the frame");

        //---------- B7: throughput ----------
        $display("   computed throughput = %.0f bytes/s", 1.0e9 / expect);
        check((1.0e9 / expect) < 11520.0,
              "B7  throughput below the 115200 8N1 ceiling (11520 B/s)");

        //---------- B9: 8 consecutive frames, byte exact ----------
        begin : drift_check
            integer bad;
            bad = 0;
            for (i = 0; i < 8; i = i + 1) begin
                set_and_get(8'h40 + i, got, ok);
                if (got !== (8'h40 + i) || ok !== 1'b1) bad = bad + 1;
            end
            if (bad != 0) $display("   %0d of 8 frames wrong", bad);
            check(bad == 0, "B9  8 consecutive frames byte-exact, no drift");
        end

        $display("RESULT(gap200): %0s", (errors == 0) ? "PASS" : "FAIL");
        $finish;
    end

    //-------------------------------------------------------------------------
    // B5 / B8: GAP=0 back-to-back instance
    //-------------------------------------------------------------------------
    reg        clk2  = 0;
    reg  [7:0] byte2 = 8'h00;
    wire       tx2;
    always #(18.5185) clk2 = ~clk2;

    uart_beacon #(.CLK_HZ(CLK_HZ), .BAUD(BAUD), .GAP(0))
        dut2 (.clk(clk2), .byte_i(byte2), .tx(tx2));

    integer e2 = 0;
    reg [7:0] g2, g2b;
    reg       o2, o2b;
    integer   k;

    task rx2;
        output [7:0] b;
        output       stop_ok;
        integer      j;
        begin
            @(negedge tx2);
            #(HALF);
            if (tx2 !== 1'b0) begin b = 8'hXX; stop_ok = 1'b0; end
            else begin
                #(BIT_NS);
                for (j = 0; j < 8; j = j + 1) begin b[j] = tx2; #(BIT_NS); end
                stop_ok = (tx2 === 1'b1);
            end
        end
    endtask

    initial begin
        rx2(g2, o2);                      // drain power-up frames
        rx2(g2, o2);
        for (k = 0; k < 4; k = k + 1) begin
            byte2 = 8'h11 + k;            // 0x11..0x14: MSB is 0 in all of them
            rx2(g2b, o2b);                // settle frame
            rx2(g2,  o2);                 // frame carrying 0x11+k
            if (g2 !== (8'h11 + k)) begin
                $display("  [FAIL] B5 frame %0d: got 0x%02X want 0x%02X",
                         k, g2, 8'h11 + k);
                e2 = e2 + 1;
            end else if (o2 !== 1'b1) begin
                $display("  [FAIL] B8 frame %0d (0x%02X): stop bit not driven", k, g2);
                e2 = e2 + 1;
            end else begin
                $display("  [OK]   B5/B8 back-to-back frame %0d: 0x%02X with stop bit", k, g2);
            end
        end
        $display("RESULT(gap0): %0s", (e2 == 0) ? "PASS" : "FAIL");
    end

endmodule
