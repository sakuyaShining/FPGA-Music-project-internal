// 320x240 landscape, static background once, bounded dirty rectangles thereafter.
// Two wave banks have explicit producer/consumer ownership. The panel retains
// history pixels; there is no full-frame RGB buffer in the FPGA.
module mv_renderer #(parameter integer CLK_HZ=27000000, FRAME_HZ=20)(
    input wire clk,rst_n,
    input wire [3:0] layer_mask,
    input wire [6:0] base_note,
    input wire spectrum_valid,
    input wire [287:0] spectrum_levels,
    output reg wave_start,
    input wire wave_write_valid,wave_complete,
    input wire [6:0] wave_index,
    input wire [15:0] wave_data,
    input wire note_valid,note_on,
    input wire [4:0] note_id,
    input wire [6:0] note_number,
    input wire pitch_valid,
    input wire [4:0] pitch_id,
    input wire signed [15:0] pitch_q8,
    output wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc,
    output reg update_done,transfer_done,
    output reg [31:0] rendered_frames,late_frames,
    output wire [4:0] debug_state
);
    localparam INIT=0,STATIC=1,DRAW=2,CLEAR=3,WAIT=4,WR=5,WL=6,WE=7,WD=8,WN=9,
               BR=10,BL=11,BD=12,BN=13,TP=14,TF=15,TL=16,TD=17,HEAD=18,FINISH=19,PRESENT=20;
    localparam FRAME_CYCLES=CLK_HZ/FRAME_HZ;
    reg [4:0] state,return_state;
    reg [31:0] timer;
    reg [7:0] clear_index;
    reg [6:0] wave_column;
    reg [5:0] bar_index;
    reg [8:0] trail_column;
    reg capture_bank,front_bank,wave_ready;
    reg [15:0] wave_mem[0:255],previous_wave[0:127];
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
    reg window_start;
    reg [8:0] x0,y0,x1,y1,px,py;
    reg [2:0] paint_mode;
    wire driver_ready,driver_busy,driver_done,driver_error,pixel_ready;
    wire pixel_valid=(state==DRAW);
    reg [15:0] pixel_color;
    assign debug_state=state;
    `include "mv_font.vh"
    function [15:0] background;
        input [8:0] x,y;
        reg [15:0] color;
        reg [8:0] address;
        reg [13:0] glyph;
        integer char_id,column,row;
        begin
            color=16'h0863;char_id=-1;column=0;row=0;
            if(x>=8 && x<=311 && ((y>=24&&y<=86)||(y>=90&&y<=157)||(y>=162&&y<=235))) color=16'h10a4;
            if(x>=32&&x<=287&&y==64) color=16'h2967;
            if(x>=39&&x<=280&&y==148) color=16'h39e9;
            if(x>=16&&x<=303&&(y==192||y==210||y==228)) color=16'h2967;
            if(y>=4&&y<18&&x>=12&&x<82) begin char_id=(x-12)/14;column=(x-12)%14;row=y-4; end
            if(y>=28&&y<42&&x>=16&&x<44) begin char_id=5+(x-16)/14;column=(x-16)%14;row=y-28; end
            if(y>=94&&y<108&&x>=16&&x<44) begin char_id=7+(x-16)/14;column=(x-16)%14;row=y-94; end
            if(y>=166&&y<180&&x>=16&&x<44) begin char_id=9+(x-16)/14;column=(x-16)%14;row=y-166; end
            if(y>=4&&y<18&&x>=214&&x<294) begin
                if((x-214)%20<14) begin
                    char_id=11+(x-214)/20;column=(x-214)%20;row=y-4;
                    if(frame_layers[(x-214)/20]) color=16'h2453; else color=16'h10a4;
                end
            end
            if(char_id>=0) begin
                address=char_id*14+row;glyph=glyph_row(address);
                if(glyph[13-column]) color=16'he75c;
            end
            if(x>=301&&x<=306&&y>=7&&y<=12) color=frame_seen ? 16'h47e9 : 16'hfd20;
            background=color;
        end
    endfunction
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
    task window;
        input [8:0] l,t,r,b;
        input [2:0] mode;
        input [4:0] next_state;
        begin
            x0<=l;y0<=t;x1<=r;y1<=b;px<=l;py<=t;
            paint_mode<=mode;return_state<=next_state;window_start<=1;state<=DRAW;
        end
    endtask
    always @* begin
        pixel_color=background(px,py);
        if(paint_mode==1) pixel_color=16'h47f8;
        if(paint_mode==2) pixel_color=(bar_index<16 ? 16'h3dff : (bar_index<32 ? 16'h5eaf : 16'hfdc8));
        if(paint_mode==3 && py>=190&&py<=228 && trace_bits[228-py]) pixel_color=16'hfdc8;
    end
    mv_panel_driver #(.CLK_HZ(CLK_HZ)) u_panel(.clk(clk),.rst_n(rst_n),
        .lcd_reset_n(lcd_reset_n),.lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),.lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc),
        .init_done(driver_ready),.start(window_start),.x0(x0),.y0(y0),.x1(x1),.y1(y1),
        .pixel_valid(pixel_valid),.pixel(pixel_color),.pixel_ready(pixel_ready),
        .busy(driver_busy),.frame_done(driver_done),.window_error(driver_error));
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
            state<=INIT;return_state<=INIT;timer<=0;clear_index<=0;wave_column<=0;bar_index<=0;trail_column<=0;
            capture_bank<=0;front_bank<=0;wave_ready<=0;wave_start<=0;
            latest_levels<=0;frame_levels<=0;spectrum_seen<=0;frame_seen<=0;previous_seen<=0;
            frame_layers<=0;previous_layers<=0;active_notes<=0;trace_index<=0;trace_bits<=0;
            window_start<=0;x0<=0;y0<=0;x1<=0;y1<=0;px<=0;py<=0;paint_mode<=0;
            current_wave<=0;old_wave<=0;old_bar<=0;new_bar<=0;
            rendered_frames<=0;late_frames<=0;update_done<=0;transfer_done<=0;
        end else begin
            window_start<=0;wave_start<=0;update_done<=0;transfer_done<=0;
            if(timer<FRAME_CYCLES) timer<=timer+1;
            if(spectrum_valid) begin latest_levels<=spectrum_levels;spectrum_seen<=1;end
            if(wave_complete) wave_ready<=1;
            if(note_valid) active_notes[note_id]<=note_on;
            case(state)
                INIT: if(driver_ready) begin frame_layers<=layer_mask;frame_seen<=spectrum_seen;state<=STATIC;end
                STATIC: window(0,0,319,239,0,CLEAR);
                DRAW: begin
                    if(pixel_valid&&pixel_ready) begin
                        if(px==x1) begin px<=x0;py<=py+1;end else px<=px+1;
                    end
                    if(driver_done) state<=return_state;
                end
                CLEAR: begin
                    if(clear_index==127) begin wave_start<=1;capture_bank<=0;state<=WAIT;end
                    else clear_index<=clear_index+1;
                end
                WAIT: if(wave_ready && timer>=FRAME_CYCLES) begin
                    front_bank<=capture_bank;capture_bank<=~capture_bank;wave_ready<=0;wave_start<=1;
                    frame_levels<=latest_levels;frame_layers<=layer_mask;frame_seen<=spectrum_seen;
                    wave_column<=0;timer<=0;state<=WR;
                end
                WR: state<=WL;
                WL: begin
                    current_wave<=wave_q;old_wave<=old_q;
                    if(wave_top(wave_q)==wave_top(old_q) && wave_bottom(wave_q)==wave_bottom(old_q)) state<=WN;else state<=WE;
                end
                WE: window(32+wave_column*2,wave_top(old_wave),32+wave_column*2,wave_bottom(old_wave),0,WD);
                WD: window(32+wave_column*2,wave_top(current_wave),32+wave_column*2,wave_bottom(current_wave),1,WN);
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
                BD: if(new_bar>old_bar) window(40+bar_index*5,148-new_bar,43+bar_index*5,147-old_bar,2,BN);
                    else if(new_bar<old_bar) window(40+bar_index*5,148-old_bar,43+bar_index*5,147-new_bar,0,BN);
                    else state<=BN;
                BN: if(bar_index==47) state<=TP;
                    else begin bar_index<=bar_index+1;state<=BR;end
                TP: begin trace_bits<=0;trace_index<=0;state<=TF;end
                TF: state<=TL;
                TL: begin
                    if(trace_active_q && relative_pitch>=0 && relative_pitch<=6144) trace_bits[trace_y]<=1;
                    if(trace_index==31) state<=TD;
                    else begin trace_index<=trace_index+1;state<=TF;end
                end
                TD: window(16+trail_column,190,16+trail_column,228,3,HEAD);
                HEAD: if(frame_layers!=previous_layers || frame_seen!=previous_seen) begin
                    previous_layers<=frame_layers;previous_seen<=frame_seen;window(212,3,307,19,0,FINISH);
                end else state<=FINISH;
                FINISH: begin
                    transfer_done<=1;
                    if(timer>=FRAME_CYCLES) late_frames<=late_frames+1;
                    state<=PRESENT;
                end
                PRESENT: if(timer>=FRAME_CYCLES) begin
                    rendered_frames<=rendered_frames+1;update_done<=1;
                    if(trail_column==287) trail_column<=0;else trail_column<=trail_column+1;
                    state<=WAIT;
                end
            endcase
        end
    end
endmodule
