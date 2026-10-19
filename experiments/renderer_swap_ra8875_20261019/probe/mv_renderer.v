// Music visualizer renderer, RA8875 command-draw variant.
//
// Same image semantics as the ILI9341 pixel-push variant, but a frame is now
// composed of RA8875 hardware draw commands instead of a 320x240 pixel stream:
//   - spectrum bars        -> 48 filled rectangles
//   - waveform trace       -> 128 erase lines + 128 draw lines
//   - pitch trail column   -> up to 39 single-column lines (one per trace bit)
//   - layer label band     -> 4 glyphs, only when the layer mask changes
// The per-frame cost becomes SPI byte traffic instead of pixel count.
//
// The colour palette, the wave mapping and the vertical-level mapping are kept
// from the pixel-push variant (docs/02-技术方案/53..55) so a side-by-side
// screen capture is a fair comparison.  Semantic differences are listed in
// docs/02-技术方案/89-*.
module mv_renderer #(parameter integer CLK_HZ=27000000, FRAME_HZ=20,
                         integer PANEL_RESET_US=20,
                         integer PANEL_RESET_WAIT_MS=120,
                         integer PANEL_CLEAR_WAIT_US=500)(
    input wire clk,rst_n,
    input wire [3:0] layer_mask,
    input wire [6:0] base_note,
    input wire spectrum_valid,
    input wire [287:0] spectrum_levels,
    input wire wave_write_valid,
    input wire wave_complete,
    input wire [6:0] wave_index,
    input wire [15:0] wave_data,
    input wire note_valid,note_on,
    input wire [4:0] note_id,
    input wire [6:0] note_number,
    input wire pitch_valid,
    input wire [4:0] pitch_id,
    input wire signed [15:0] pitch_q8,
    output wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc,
    output wire wave_start,
    output wire update_done,transfer_done,
    output wire [31:0] rendered_frames,late_frames,
    output wire [4:0] debug_state
);
    reg [31:0] rendered_frames_r,late_frames_r;
    reg update_done_r,transfer_done_r;
    assign rendered_frames = rendered_frames_r;
    assign late_frames = late_frames_r;
    assign update_done = update_done_r;
    assign transfer_done = transfer_done_r;

    localparam OP_CLEAR=2'd0, OP_FILLRECT=2'd1, OP_LINE=2'd2, OP_TEXT=2'd3;

    localparam FRAME_CYCLES=CLK_HZ/FRAME_HZ;
    localparam INIT=0,STATIC=1,CLEAR=2,WAIT=3,WR=4,WL=5,WE=6,WD=7,WN=8,
               BR=9,BL=10,BD=11,BN=12,TP=13,TF=14,TL=15,TD=16,TRI=17,
               HEAD=18,HTX=19,FINISH=20,PRESENT=21;

    // RGB565 values kept from the pixel-push variant.
    localparam [15:0] C_BG      = 16'h0863;  // window background
    localparam [15:0] C_PLOT    = 16'h10a4;  // plot area background
    localparam [15:0] C_WAVE    = 16'h47f8;
    localparam [15:0] C_FADER0  = 16'h3dff;
    localparam [15:0] C_FADER1  = 16'h5eaf;
    localparam [15:0] C_FADER2  = 16'hfdc8;
    localparam [15:0] C_TRAIL   = 16'hfdc8;
    localparam [15:0] C_LABEL   = 16'he75c;

    reg [4:0] state;
    reg [31:0] timer;
    reg [6:0] clear_index;
    reg [6:0] wave_column;
    reg [5:0] bar_index;
    reg [8:0] trail_column;
    reg [5:0] trace_bit;
    reg [1:0] text_index;
    reg capture_bank,front_bank,wave_ready,wave_start_r;
    assign wave_start = wave_start_r;
    reg [15:0] wave_mem[0:255];
    reg [15:0] previous_wave[0:127];
    reg [15:0] wave_q,old_q,current_wave,old_wave;
    reg [5:0] previous_bar[0:47],old_bar_q,old_bar,new_bar;
    reg [287:0] latest_levels,frame_levels;
    reg spectrum_seen,frame_seen,previous_seen;
    reg [3:0] frame_layers,previous_layers;
    reg [31:0] active_notes;
    reg signed [15:0] pitches[0:31],trace_pitch_q;
    reg trace_active_q;
    reg [4:0] trace_index;
    reg [38:0] trace_bits;

    wire signed [16:0] relative_pitch=$signed(trace_pitch_q)-$signed({1'b0,base_note,8'd0});
    wire [16:0] trace_y=(relative_pitch*3)>>9;

    function [8:0] wave_top;
        input [15:0] value;
        reg signed [7:0] v;
        begin v=value[7:0];wave_top=64-($signed(v)>>>3);end
    endfunction
    function [8:0] wave_bottom;
        input [15:0] value;
        reg signed [7:0] v;
        begin v=value[15:8];wave_bottom=64-($signed(v)>>>3);end
    endfunction
    // Layer label band: 12 slots on a 320 px panel only leave 4 inside x<320,
    // matching the pixel-push variant, which shows char_id 11..14 there.
    function [7:0] layer_char;
        input [3:0] mask;
        input [1:0] slot;
        begin layer_char = mask[slot] ? 8'h31 : 8'h30; end
    endfunction

    // ---- geometry of the primitive the current state wants ----------------
    reg [8:0] g_x0, g_y0, g_x1, g_y1;
    reg [15:0] g_color;
    always @* begin
        g_x0 = 9'd0; g_y0 = 9'd0; g_x1 = 9'd319; g_y1 = 9'd239; g_color = C_BG;
        case (state)
            WE, WD: begin
                g_x0 = 9'd32 + {2'd0,wave_column}*9'd2;
                g_x1 = 9'd32 + {2'd0,wave_column}*9'd2;
                g_y0 = (state==WE) ? wave_top(old_wave)     : wave_top(current_wave);
                g_y1 = (state==WE) ? wave_bottom(old_wave)   : wave_bottom(current_wave);
                g_color = (state==WE) ? C_PLOT : C_WAVE;
            end
            BD: begin
                g_x0 = 9'd40 + {3'd0,bar_index}*9'd5;
                g_x1 = 9'd43 + {3'd0,bar_index}*9'd5;
                if (new_bar>old_bar) begin
                    g_y0 = 9'd148 - {3'd0,new_bar};
                    g_y1 = 9'd147 - {3'd0,old_bar};
                    g_color = (bar_index<16) ? C_FADER0 : ((bar_index<32) ? C_FADER1 : C_FADER2);
                end else begin
                    g_y0 = 9'd148 - {3'd0,old_bar};
                    g_y1 = 9'd147 - {3'd0,new_bar};
                    g_color = C_PLOT;
                end
            end
            TRI: begin
                g_x0 = 9'd16 + trail_column;
                g_x1 = 9'd16 + trail_column;
                g_y0 = 9'd190 + {3'd0,trace_bit};
                g_y1 = 9'd190 + {3'd0,trace_bit};
                g_color = C_TRAIL;
            end
            HTX: begin
                g_x0 = 9'd212 + {7'd0,text_index}*9'd20;
                g_x1 = 9'd212 + {7'd0,text_index}*9'd20;
                g_y0 = 9'd3;
                g_y1 = 9'd18;
                g_color = C_LABEL;
            end
        endcase
    end

    // ---- RA8875 command layer -------------------------------------------
    reg        panel_valid;
    reg [1:0]  panel_op;
    wire       panel_ready,panel_done;

    always @* begin
        panel_valid = panel_ready &&
            ((state==STATIC) || (state==WE) || (state==WD) || (state==BD) ||
             (state==TRI)    || (state==HTX));
        panel_op = (state==STATIC) ? OP_CLEAR :
                   ((state==WE)||(state==WD)) ? OP_LINE :
                   (state==BD) ? OP_FILLRECT : OP_TEXT;
    end

    mv_panel_ra8875 #(.CLK_HZ(CLK_HZ),.RESET_US(PANEL_RESET_US),
                       .RESET_WAIT_MS(PANEL_RESET_WAIT_MS),
                       .CLEAR_WAIT_US(PANEL_CLEAR_WAIT_US)) u_panel(
        .clk(clk),.rst_n(rst_n),
        .op_valid(panel_valid),.op_ready(panel_ready),.op(panel_op),
        .x0(g_x0),.y0(g_y0),.x1(g_x1),.y1(g_y1),
        .color(g_color),.ascii(layer_char(frame_layers,text_index)),.op_done(panel_done),
        .lcd_reset_n(lcd_reset_n),.lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),
        .lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc)
    );

    assign debug_state = state;

    always @(posedge clk) begin
        wave_q<=wave_mem[{front_bank,wave_column}];old_q<=previous_wave[wave_column];
        old_bar_q<=previous_bar[bar_index];trace_pitch_q<=pitches[trace_index];trace_active_q<=active_notes[trace_index];
        if(rst_n) begin
            if(wave_write_valid) wave_mem[{capture_bank,wave_index}]<=wave_data;
            if(state==CLEAR && clear_index<128) previous_wave[clear_index[6:0]]<=0;
            else if(state==WN) previous_wave[wave_column]<=current_wave;
            if(state==CLEAR && clear_index<48) previous_bar[clear_index[5:0]]<=0;
            else if(state==BN) previous_bar[bar_index]<=new_bar;
            if(note_valid&&note_on) pitches[note_id]<={1'b0,note_number,8'd0};
            else if(pitch_valid) pitches[pitch_id]<=pitch_q8;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=INIT;timer<=0;wave_start_r<=0;
            wave_column<=0;bar_index<=0;trail_column<=0;trace_bit<=0;text_index<=0;
            capture_bank<=0;front_bank<=0;wave_ready<=0;
            latest_levels<=0;frame_levels<=0;spectrum_seen<=0;frame_seen<=0;previous_seen<=0;
            frame_layers<=0;previous_layers<=0;active_notes<=0;trace_index<=0;trace_bits<=0;
            current_wave<=0;old_wave<=0;old_bar<=0;new_bar<=0;
            rendered_frames_r<=0;late_frames_r<=0;update_done_r<=0;transfer_done_r<=0;clear_index<=0;
        end else begin
            wave_start_r<=0;update_done_r<=0;transfer_done_r<=0;
            if(timer<FRAME_CYCLES) timer<=timer+1;
            if(spectrum_valid) begin latest_levels<=spectrum_levels;spectrum_seen<=1;end
            if(wave_complete) wave_ready<=1;
            if(note_valid) active_notes[note_id]<=note_on;
            case(state)
                INIT: if(panel_ready) begin frame_layers<=layer_mask;frame_seen<=spectrum_seen;state<=STATIC;end
                STATIC: if(panel_done) begin clear_index<=0;wave_start_r<=1;capture_bank<=0;state<=CLEAR;end
                CLEAR: begin
                    if(clear_index==127) state<=WAIT;
                    else clear_index<=clear_index+1;
                end
                WAIT: if(wave_ready && timer>=FRAME_CYCLES) begin
                    front_bank<=capture_bank;capture_bank<=~capture_bank;wave_ready<=0;wave_start_r<=1;
                    frame_levels<=latest_levels;frame_layers<=layer_mask;frame_seen<=spectrum_seen;
                    wave_column<=0;timer<=0;state<=WR;
                end
                WR: state<=WL;
                WL: begin
                    current_wave<=wave_q;old_wave<=old_q;
                    if(wave_top(wave_q)==wave_top(old_q) && wave_bottom(wave_q)==wave_bottom(old_q)) state<=WN;
                    else state<=WE;
                end
                WE: if(panel_done) state<=WD;
                WD: if(panel_done) state<=WN;
                WN: if(wave_column==127) begin bar_index<=0;state<=BR;end
                    else begin wave_column<=wave_column+1;state<=WR;end
                BR: state<=BL;
                BL: begin
                    old_bar<=old_bar_q;
                    if((frame_levels[bar_index*6+:6]*36>>6)>=old_bar_q) new_bar<=frame_levels[bar_index*6+:6]*36>>6;
                    else if(old_bar_q>2 && (frame_levels[bar_index*6+:6]*36>>6)<old_bar_q-2) new_bar<=old_bar_q-2;
                    else new_bar<=frame_levels[bar_index*6+:6]*36>>6;
                    state<=BD;
                end
                BD: if(panel_done) state<=BN;
                BN: if(bar_index==47) state<=TP;
                    else begin bar_index<=bar_index+1;state<=BR;end
                TP: begin trace_bits<=0;trace_index<=0;state<=TF;end
                TF: state<=TL;
                TL: begin
                    if(trace_active_q && relative_pitch>=0 && relative_pitch<=6144) trace_bits[trace_y]<=1;
                    if(trace_index==31) begin trace_bit<=0;state<=TD;end
                    else begin trace_index<=trace_index+1;state<=TF;end
                end
                TD: begin
                    if(trace_bit==38) state<=HEAD;
                    else if(trace_bits[trace_bit[5:0]]) state<=TRI;
                    else begin trace_bit<=trace_bit+1;state<=TD;end
                end
                TRI: if(panel_done) begin trace_bit<=trace_bit+1;state<=TD;end
                HEAD: if(frame_layers!=previous_layers || frame_seen!=previous_seen) begin
                    previous_layers<=frame_layers;previous_seen<=frame_seen;text_index<=0;state<=HTX;
                end else state<=FINISH;
                HTX: if(panel_done) begin
                    if(text_index==3) state<=FINISH;
                    else begin text_index<=text_index+1;state<=HTX;end
                end
                FINISH: begin
                    transfer_done_r<=1;
                    if(timer>=FRAME_CYCLES) late_frames_r<=late_frames_r+1;
                    state<=PRESENT;
                end
                PRESENT: if(timer>=FRAME_CYCLES) begin
                    rendered_frames_r<=rendered_frames_r+1;update_done_r<=1;
                    if(trail_column==287) trail_column<=0;else trail_column<=trail_column+1;
                    state<=WAIT;
                end
            endcase
        end
    end
endmodule
