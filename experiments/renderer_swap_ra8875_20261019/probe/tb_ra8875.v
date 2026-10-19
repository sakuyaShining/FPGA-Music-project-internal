// Byte-level check of the RA8875 command layer.
// Captures the serial byte stream produced by mv_panel_ra8875 and compares it
// with the RA8875 register/data sequences taken from Adafruit_RA8875.
`timescale 1ns/1ps
module tb_ra8875;
    reg  clk = 1'b0, rst_n = 1'b0;
    wire lcd_reset_n, cs_n, sck, mosi, dc;

    always #18.519 clk = ~clk;   // 27 MHz

    reg        op_valid = 1'b0;
    reg [1:0]  op;
    reg [8:0]  x0, y0, x1, y1;
    reg [15:0] color;
    reg [7:0]  ascii;
    wire       op_ready;
    reg        op_done;

    // captured byte stream: bit8 = D/C, bits[7:0] = payload
    reg [8:0] stream [0:255];
    integer   stream_len = 0;
    reg [7:0] shift;
    integer   bit_cnt = 0;
    reg       prev_sck = 1'b0;

    integer errors = 0;
    integer i, tmo;

    mv_panel_ra8875 dut (
        .clk(clk), .rst_n(rst_n),
        .op_valid(op_valid), .op_ready(op_ready), .op(op),
        .x0(x0), .y0(y0), .x1(x1), .y1(y1),
        .color(color), .ascii(ascii), .op_done(op_done),
        .lcd_reset_n(lcd_reset_n), .lcd_cs_n(cs_n), .lcd_sck(sck),
        .lcd_mosi(mosi), .lcd_dc(dc)
    );

    // Sample MOSI on every rising edge of SCK while CS is low.
    always @(posedge clk) begin
        prev_sck <= sck;
        if (sck && !prev_sck && !cs_n) begin
            shift = {shift[6:0], mosi};
            bit_cnt = bit_cnt + 1;
            if (bit_cnt == 8) begin
                bit_cnt = 0;
                if (stream_len < 256) begin
                    stream[stream_len] = {dc, shift};
                    stream_len = stream_len + 1;
                end
            end
        end
    end

    task expect_byte;
        input [8:0] want;
        input [127:0] label;
        begin
            if (i >= stream_len) begin
                $display("FAIL %s: stream ended at %0d", label, i);
                errors = errors + 1;
            end else if (stream[i] !== want) begin
                $display("FAIL %s: byte %0d = %02x, want %02x",
                         label, i, stream[i], want);
                errors = errors + 1;
            end
            i = i + 1;
        end
    endtask

    task drive_op;
        input [1:0]  a_op;
        input [8:0]  ax0, ay0, ax1, ay1;
        input [15:0] acolor;
        input [7:0]  aascii;
        begin
            tmo = 0;
            while (!op_ready && tmo < 500000) begin @(posedge clk); tmo = tmo + 1; end
            if (tmo >= 500000) begin
                $display("FAIL: op_ready timeout"); errors = errors + 1;
            end
            op = a_op; x0 = ax0; y0 = ay0; x1 = ax1; y1 = ay1;
            color = acolor; ascii = aascii;
            @(posedge clk); op_valid = 1'b1;
            @(posedge clk); op_valid = 1'b0;
            tmo = 0;
            while (!op_done && tmo < 5000000) begin @(posedge clk); tmo = tmo + 1; end
            if (tmo >= 5000000) begin
                $display("FAIL: op_done timeout"); errors = errors + 1;
            end
            @(posedge clk);
        end
    endtask

    initial begin
        rst_n = 1'b0;
        repeat (20) @(posedge clk);
        rst_n = 1'b1;

        while (!op_ready) @(posedge clk);
        $display("init emitted %0d bytes", stream_len);
        if (stream_len != 48) begin
            $display("FAIL init length: %0d want 48", stream_len);
            errors = errors + 1;
        end

        // ---- op 1: fill rect, fresh colour -> 16 bytes --------------------
        i = stream_len;
        drive_op(2'd1, 9'd40, 9'd10, 9'd43, 9'd20, 16'hF800, 8'h20);
        if (stream_len - i != 16) begin
            $display("FAIL fillrect fresh length: %0d want 16", stream_len - i);
            errors = errors + 1;
        end
        i = stream_len - 16;
        expect_byte(9'h0_91, "fr X0 cmd");
        expect_byte(9'h1_28, "fr X0 data");   // 40
        expect_byte(9'h0_93, "fr Y0 cmd");
        expect_byte(9'h1_0A, "fr Y0 data");   // 10
        expect_byte(9'h0_95, "fr X1 cmd");
        expect_byte(9'h1_2B, "fr X1 data");   // 43
        expect_byte(9'h0_97, "fr Y1 cmd");
        expect_byte(9'h1_14, "fr Y1 data");   // 20
        expect_byte(9'h0_63, "fr R cmd");
        expect_byte(9'h1_1F, "fr R data");
        expect_byte(9'h0_64, "fr G cmd");
        expect_byte(9'h1_00, "fr G data");
        expect_byte(9'h0_65, "fr B cmd");
        expect_byte(9'h1_00, "fr B data");
        expect_byte(9'h0_90, "fr DCR cmd");
        expect_byte(9'h1_B0, "fr DCR data");

        // ---- op 2: same colour -> colour pairs skipped -> 10 bytes --------
        i = stream_len;
        drive_op(2'd1, 9'd48, 9'd10, 9'd51, 9'd30, 16'hF800, 8'h20);
        if (stream_len - i != 10) begin
            $display("FAIL fillrect cached length: %0d want 10", stream_len - i);
            errors = errors + 1;
        end
        i = stream_len - 10;
        expect_byte(9'h0_91, "frc X0 cmd");
        expect_byte(9'h1_30, "frc X0 data");  // 48
        expect_byte(9'h0_93, "frc Y0 cmd");
        expect_byte(9'h1_0A, "frc Y0 data");
        expect_byte(9'h0_95, "frc X1 cmd");
        expect_byte(9'h1_33, "frc X1 data");  // 51
        expect_byte(9'h0_97, "frc Y1 cmd");
        expect_byte(9'h1_1E, "frc Y1 data");  // 30
        expect_byte(9'h0_90, "frc DCR cmd");
        expect_byte(9'h1_B0, "frc DCR data");

        // ---- op 3: line, DCR payload 0x80 --------------------------------
        i = stream_len;
        drive_op(2'd2, 9'd32, 9'd64, 9'd32, 9'd190, 16'h07E0, 8'h20);
        if (stream_len - i != 16) begin
            $display("FAIL line length: %0d want 16", stream_len - i);
            errors = errors + 1;
        end
        i = stream_len - 16;
        expect_byte(9'h0_91, "ln X0 cmd");
        expect_byte(9'h1_20, "ln X0 data");
        expect_byte(9'h0_93, "ln Y0 cmd");
        expect_byte(9'h1_40, "ln Y0 data");
        expect_byte(9'h0_95, "ln X1 cmd");
        expect_byte(9'h1_20, "ln X1 data");
        expect_byte(9'h0_97, "ln Y1 cmd");
        expect_byte(9'h1_BE, "ln Y1 data");
        expect_byte(9'h0_63, "ln R cmd");
        expect_byte(9'h1_00, "ln R data");
        expect_byte(9'h0_64, "ln G cmd");
        expect_byte(9'h1_3F, "ln G data");
        expect_byte(9'h0_65, "ln B cmd");
        expect_byte(9'h1_00, "ln B data");
        expect_byte(9'h0_90, "ln DCR cmd");
        expect_byte(9'h1_80, "ln DCR data");

        // ---- op 4: one text glyph -> 18 bytes -----------------------------
        i = stream_len;
        drive_op(2'd3, 9'd16, 9'd4, 9'd0, 9'd0, 16'hE75C, 8'h41);
        if (stream_len - i != 18) begin
            $display("FAIL text length: %0d want 18", stream_len - i);
            errors = errors + 1;
        end
        i = stream_len - 18;
        expect_byte(9'h0_2A, "tx H0 cmd");
        expect_byte(9'h1_10, "tx H0 data");
        expect_byte(9'h0_2B, "tx H1 cmd");
        expect_byte(9'h1_00, "tx H1 data");
        expect_byte(9'h0_2C, "tx V0 cmd");
        expect_byte(9'h1_04, "tx V0 data");
        expect_byte(9'h0_2D, "tx V1 cmd");
        expect_byte(9'h1_00, "tx V1 data");
        expect_byte(9'h0_63, "tx R cmd");
        expect_byte(9'h1_1C, "tx R data");
        expect_byte(9'h0_64, "tx G cmd");
        expect_byte(9'h1_3A, "tx G data");
        expect_byte(9'h0_65, "tx B cmd");
        expect_byte(9'h1_1C, "tx B data");
        expect_byte(9'h0_40, "tx MWCR cmd");
        expect_byte(9'h1_80, "tx MWCR data");
        expect_byte(9'h0_02, "tx MRWC cmd");
        expect_byte(9'h1_41, "tx char data");

        $display("captured stream: %0d bytes total", stream_len);
        if (errors == 0) $display("PASS: RA8875 byte-level encoding matches the datasheet register map");
        else             $display("FAIL: %0d mismatches", errors);
        $finish;
    end
endmodule
