// RA8875 4-wire serial command layer for the music visualizer.
//
// Replaces mv_panel_driver plus the pixel-streaming path of mv_renderer.
// The host pushes high-level ops; this module expands them into RA8875
// register/data byte pairs and drives the existing mv_spi_byte master, so the
// per-frame cost becomes byte traffic instead of pixel count.
//
// Verified register map (values transcribed from the Adafruit_RA8875 driver,
// which mirrors the RA8875 datasheet register set):
//   PWRR   0x01   soft reset / display enable
//   PCSR   0x04   pixel clock setting
//   SYSR   0x10   colour depth (bit2 = 1 -> 16bpp RGB565)
//   HDWR..VPWR  0x14..0x1F   horizontal/vertical timing
//   FNCR   0x21   font select (bit5=1 external font, =0 internal CGROM)
//   TextCfg 0x22  bit6 = transparent background
//   TextH/TextV 0x2A..0x2D    text cursor
//   BgCol  0x60..0x62   FgCol 0x63..0x65
//   DCR    0x90   draw control: line 0x80, filled square 0xB0
//   MCLR   0x8E   memory clear: 0x80 = start, full window
//
// Interface facts:
//   - 4-wire serial is selected by hardware strap pins on the module; there is
//     no software register that chooses the interface width.
//   - Host framing is RA8875_CMDWRITE (0x80) for a register address and
//     RA8875_DATAWRITE (0x00) for a payload.
//
// KNOWN OPEN ITEMS (tracked in docs/02-技术方案/89-*):
//   - Draw-engine completion is NOT polled: without SDO/MISO on the module the
//     driver must time-estimate, so a host that is ahead of the real draw
//     engine can be over-run.  This is the main functional risk of the swap.
//   - Text uses the internal CGROM instead of mv_font.vh, so existing glyphs
//     are lost and must be re-drawn.
module mv_panel_ra8875 #(
    parameter integer CLK_HZ = 27000000,
    parameter integer HALF_CYCLES = 2,
    parameter integer WIDTH  = 320,
    parameter integer HEIGHT = 240,
    parameter integer CLEAR_WAIT_US = 500,
    parameter integer RESET_US = 20,
    parameter integer RESET_WAIT_MS = 120,
    parameter integer DRAW_MARGIN_US = 60
)(
    input  wire        clk, rst_n,
    input  wire        op_valid,
    output wire        op_ready,
    input  wire [1:0]  op,
    input  wire [8:0]  x0, y0, x1, y1,
    input  wire [15:0] color,
    input  wire [7:0]  ascii,
    output reg         op_done,
    output wire        lcd_reset_n, lcd_cs_n, lcd_sck, lcd_mosi, lcd_dc
);
    localparam OP_CLEAR = 2'd0, OP_FILLRECT = 2'd1, OP_LINE = 2'd2, OP_TEXT = 2'd3;

    localparam S_RSTLOW     = 0,   S_RSTHIGH  = 1,
               S_INIT       = 2,   S_INIT_ACK = 3,
               S_INIT_V     = 4,   S_INITVACK = 5,
               S_INIT_WAIT  = 6,   S_READY    = 7,
               S_CMD        = 8,   S_CMD_ACK  = 9,
               S_DATA       = 10,  S_DATA_ACK = 11,
               S_WAIT       = 12,  S_ERROR    = 13;

    localparam integer INIT_STEPS = 24;
    localparam integer INIT_WAIT  = (CLK_HZ/1000000)*CLEAR_WAIT_US;
    localparam integer ONE_MS     = (CLK_HZ/1000);

    // --------------------------------------------------------------- init ROM
    function [7:0] init_reg;
        input [4:0] index;
        begin
            case (index)
                0:  init_reg = 8'h01; // PWRR  soft reset
                1:  init_reg = 8'h01; // PWRR  display on
                2:  init_reg = 8'h88; // PLLC1
                3:  init_reg = 8'h89; // PLLC2
                4:  init_reg = 8'h10; // SYSR
                5:  init_reg = 8'h04; // PCSR
                6:  init_reg = 8'h14; // HDWR
                7:  init_reg = 8'h16; // HNDR
                8:  init_reg = 8'h17; // HSTR
                9:  init_reg = 8'h18; // HPWR
                10: init_reg = 8'h19; // VDHR0
                11: init_reg = 8'h1B; // VNDR0
                12: init_reg = 8'h1D; // VSTR0
                13: init_reg = 8'h1F; // VPWR
                14: init_reg = 8'h30; // HSAW0
                15: init_reg = 8'h32; // VSAW0
                16: init_reg = 8'h34; // HEAW0
                17: init_reg = 8'h36; // VEAW0
                18: init_reg = 8'h40; // MWCR0
                19: init_reg = 8'h21; // FNCR
                20: init_reg = 8'h22; // TextCfg
                21: init_reg = 8'h60; // background colour low byte
                22: init_reg = 8'h63; // foreground colour low byte
                23: init_reg = 8'h8E; // MCLR
                default: init_reg = 8'h00;
            endcase
        end
    endfunction

    function [7:0] init_val;
        input [4:0] index;
        begin
            case (index)
                0:  init_val = 8'h01;                       // soft reset
                1:  init_val = 8'h80;                       // display on
                2:  init_val = 8'h0A;                       // PLLDIV1 + 10
                3:  init_val = 8'h02;                       // PLL /4
                4:  init_val = 8'h08;                       // 16bpp RGB565
                5:  init_val = 8'h81;                       // pixel clock divider
                6:  init_val = (WIDTH/8) - 1;
                7:  init_val = 8'h01;                       // H non-display
                8:  init_val = 8'h00;                       // Hsync start
                9:  init_val = 8'h05;                       // Hsync pulse width
                10: init_val = (HEIGHT-1) & 8'hFF;
                11: init_val = 8'h02;                       // V non-display
                12: init_val = 8'h07;                       // Vsync start
                13: init_val = 8'h09;                       // Vsync pulse width
                14: init_val = 8'h00;                       // window X start
                15: init_val = 8'h00;                       // window Y start
                16: init_val = (WIDTH-1) & 8'hFF;           // window X end
                17: init_val = (HEIGHT-1) & 8'hFF;          // window Y end
                18: init_val = 8'h00;                       // text mode off, LRTD
                19: init_val = 8'h00;                       // internal CGROM font
                20: init_val = 8'h40;                       // transparent text bg
                21: init_val = 8'h00;                       // background black
                22: init_val = 8'hFF;                       // foreground white
                23: init_val = 8'h80;                       // memory clear, full
                default: init_val = 8'h00;
            endcase
        end
    endfunction

    // --------------------------------------------------- op -> byte pair plan
    // A byte pair is one RA8875 register write: (cmd byte, data byte).
    localparam P_CLEAR_PAIRS = 2;
    localparam P_RECT_PAIRS   = 8;
    localparam P_TEXT_PAIRS   = 9;

    function [3:0] pair_count;
        input [1:0] cur_op;
        input cached;
        begin
            case (cur_op)
                OP_CLEAR:             pair_count = P_CLEAR_PAIRS;
                OP_FILLRECT, OP_LINE: pair_count = cached ? 4'd5 : P_RECT_PAIRS;
                OP_TEXT:              pair_count = P_TEXT_PAIRS;
                default:              pair_count = 4'd0;
            endcase
        end
    endfunction

    // Step counter -> micro-ROM index.  For a cached colour the three colour
    // pairs (index 4..6) are skipped, so step 4 jumps straight to the DCR.
    function [3:0] pair_index;
        input [1:0] cur_op;
        input [3:0] step;
        input cached;
        begin
            pair_index = (cur_op != OP_CLEAR) && (cur_op != OP_TEXT) && cached && (step == 4'd4)
                        ? 4'd7 : step;
        end
    endfunction

    function [7:0] pair_cmd;
        input [3:0] index;
        input [1:0] cur_op;
        begin
            case (cur_op)
                OP_CLEAR: pair_cmd = 8'h8E;                                    // MCLR
                OP_TEXT:  case (index)
                             0: pair_cmd = 8'h2A;   // TextH0
                             1: pair_cmd = 8'h2B;   // TextH1
                             2: pair_cmd = 8'h2C;   // TextV0
                             3: pair_cmd = 8'h2D;   // TextV1
                             4: pair_cmd = 8'h63;   // FgCol R
                             5: pair_cmd = 8'h64;   // FgCol G
                             6: pair_cmd = 8'h65;   // FgCol B
                             7: pair_cmd = 8'h40;   // MWCR0 (text mode on)
                             default: pair_cmd = 8'h02; // MRWC
                         endcase
                default: case (index)            // OP_FILLRECT / OP_LINE
                             0: pair_cmd = 8'h91;   // X0 low
                             1: pair_cmd = 8'h93;   // Y0 low
                             2: pair_cmd = 8'h95;   // X1 low
                             3: pair_cmd = 8'h97;   // Y1 low
                             4: pair_cmd = 8'h63;   // FgCol R
                             5: pair_cmd = 8'h64;   // FgCol G
                             6: pair_cmd = 8'h65;   // FgCol B
                             default: pair_cmd = 8'h90; // DCR
                         endcase
            endcase
        end
    endfunction

    function [7:0] pair_data;
        input [3:0] index;
        input [1:0] cur_op;
        input [8:0] ax0, ay0, ax1, ay1;
        input [15:0] col;
        input [7:0] ch;
        begin
            case (cur_op)
                OP_CLEAR: pair_data = 8'h80;                                    // start
                OP_TEXT:  case (index)
                             0: pair_data = ax0[7:0];
                             1: pair_data = {7'd0, ax0[8]};
                             2: pair_data = ay0[7:0];
                             3: pair_data = {7'd0, ay0[8]};
                             4: pair_data = col[15:11];
                             5: pair_data = col[10:5];
                             6: pair_data = col[4:0];
                             7: pair_data = 8'h80;   // text mode on
                             default: pair_data = ch;  // MRWC character
                         endcase
                default: case (index)            // OP_FILLRECT / OP_LINE
                             0: pair_data = ax0[7:0];
                             1: pair_data = ay0[7:0];
                             2: pair_data = ax1[7:0];
                             3: pair_data = ay1[7:0];
                             4: pair_data = col[15:11];
                             5: pair_data = col[10:5];
                             6: pair_data = col[4:0];
                             default: pair_data = (cur_op == OP_FILLRECT) ? 8'hB0 : 8'h80;
                         endcase
            endcase
        end
    endfunction

    // ---------------------------------------------------------------- signals
    reg [6:0]   init_index;
    reg [31:0]  wait_count;
    reg [15:0]  last_color;
    reg         have_color;
    reg [3:0]   step;
    reg [3:0]   cur_pairs;
    reg [1:0]   cur_op;
    reg         cur_cached;
    reg [8:0]   r_x0, r_y0, r_x1, r_y1;
    reg [15:0]  r_color;
    reg [7:0]   r_char;
    wire        color_cached = have_color && (color == last_color);
    reg [3:0]   state;

    reg        tx_valid, tx_dc;
    reg [7:0]  tx_data;
    wire       tx_ready, tx_done;

    assign op_ready    = (state == S_READY);
    assign lcd_reset_n = (state != S_RSTLOW);

    mv_spi_byte #(.HALF_CYCLES(HALF_CYCLES)) u_spi (
        .clk(clk), .rst_n(rst_n), .valid(tx_valid), .dc_in(tx_dc),
        .data_in(tx_data), .ready(tx_ready), .done(tx_done),
        .cs_n(lcd_cs_n), .sck(lcd_sck), .mosi(lcd_mosi), .dc(lcd_dc)
    );

    // Time budget for the RA8875 draw engine (no status polling available).
    function [31:0] draw_wait;
        input [1:0]  op_kind;
        input [8:0]  a, b, c, d;
        reg [19:0] area;
        begin
            area = (a > c ? a - c : c - a) * (b > d ? b - d : d - b) + 1;
            draw_wait = (op_kind == OP_CLEAR) ? INIT_WAIT :
                        (op_kind == OP_TEXT)  ? ONE_MS*2 :
                        ((CLK_HZ/1000000)*DRAW_MARGIN_US) + (area >> 10);
        end
    endfunction

    always @* begin
        tx_valid = 1'b0; tx_dc = 1'b0; tx_data = 8'h00;
        case (state)
            S_INIT:  begin tx_valid = 1'b1; tx_dc = 1'b0; tx_data = init_reg(init_index); end
            S_INIT_V:begin tx_valid = 1'b1; tx_dc = 1'b1; tx_data = init_val(init_index); end
            S_CMD:   begin tx_valid = 1'b1; tx_dc = 1'b0;
                          tx_data = pair_cmd(pair_index(cur_op, step, cur_cached), cur_op); end
            S_DATA:  begin tx_valid = 1'b1; tx_dc = 1'b1;
                          tx_data = pair_data(pair_index(cur_op, step, cur_cached), cur_op,
                                              r_x0, r_y0, r_x1, r_y1, r_color, r_char); end
        endcase
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= S_RSTLOW;
            init_index  <= 0;
            wait_count  <= (CLK_HZ/1000000)*20;
            last_color  <= 16'h0000;
            have_color  <= 1'b0;
            step        <= 0;
            cur_pairs   <= 0;
            cur_op      <= OP_CLEAR;
            cur_cached  <= 1'b0;
            r_x0 <= 0; r_y0 <= 0; r_x1 <= 0; r_y1 <= 0;
            r_color <= 0; r_char <= 8'h20;
            op_done <= 0;
        end else begin
            op_done <= 1'b0;
            case (state)
                S_RSTLOW: if (wait_count != 0) wait_count <= wait_count - 1;
                    else begin wait_count <= ONE_MS*RESET_WAIT_MS; state <= S_RSTHIGH; end
                S_RSTHIGH: if (wait_count != 0) wait_count <= wait_count - 1;
                    else begin init_index <= 0; state <= S_INIT; end
                S_INIT: if (tx_ready) state <= S_INIT_ACK;
                S_INIT_ACK: if (tx_done) state <= S_INIT_V;
                S_INIT_V: if (tx_ready) state <= S_INITVACK;
                S_INITVACK: if (tx_done) begin
                    if (init_index == 0 || init_index == 2 || init_index == 3 ||
                        init_index == 23) begin
                        wait_count <= (init_index == 23) ? INIT_WAIT : ONE_MS;
                        state <= S_INIT_WAIT;
                    end else if (init_index == INIT_STEPS-1) begin
                        init_index <= 0; have_color <= 1'b0; state <= S_READY;
                    end else begin
                        init_index <= init_index + 1; state <= S_INIT;
                    end
                end
                S_INIT_WAIT: if (wait_count != 0) wait_count <= wait_count - 1;
                    else begin
                        if (init_index == INIT_STEPS-1) begin
                            init_index <= 0; have_color <= 1'b0; state <= S_READY;
                        end else begin
                            init_index <= init_index + 1; state <= S_INIT;
                        end
                    end
                S_READY: if (op_valid) begin
                    cur_op     <= op;
                    cur_cached <= color_cached;
                    cur_pairs  <= pair_count(op, color_cached);
                    r_x0 <= x0; r_y0 <= y0; r_x1 <= x1; r_y1 <= y1;
                    r_color <= color; r_char <= ascii;
                    step <= 0;
                    state <= S_CMD;
                end
                S_CMD: if (tx_ready) state <= S_CMD_ACK;
                S_CMD_ACK: if (tx_done) state <= S_DATA;
                S_DATA: if (tx_ready) state <= S_DATA_ACK;
                S_DATA_ACK: if (tx_done) begin
                    if (step == cur_pairs-1) begin
                        last_color <= r_color;
                        have_color <= 1'b1;
                        wait_count <= draw_wait(cur_op, r_x0, r_y0, r_x1, r_y1);
                        state <= S_WAIT;
                    end else begin
                        step <= step + 1;
                        state <= S_CMD;
                    end
                end
                S_WAIT: if (wait_count != 0) wait_count <= wait_count - 1;
                    else begin op_done <= 1'b1; state <= S_READY; end
                default: state <= S_RSTLOW;
            endcase
        end
    end
endmodule
