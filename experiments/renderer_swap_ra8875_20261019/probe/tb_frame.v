// Frame-level check: run music_visualizer with the RA8875 renderer and count
// the SPI bytes emitted per frame.  The purpose is to prove the new frame state
// machine completes and to measure the byte traffic the swap actually produces.
`timescale 1ns/1ps
module tb_frame;
    reg clk = 1'b0, rst_n = 1'b0;
    always #18.519 clk = ~clk;

    reg        pcm_valid = 1'b0;
    reg [15:0] pcm_in = 0;
    reg [3:0]  layer_mask = 4'b0001;
    reg [6:0]  base_note = 7'd60;
    reg        note_valid = 1'b0, note_on = 1'b1;
    reg [4:0]  note_id = 0;
    reg [6:0]  note_number = 7'd60;
    reg        pitch_valid = 1'b0;
    reg [4:0]  pitch_id = 0;
    reg [15:0] pitch_q8 = 0;
    wire lcd_reset_n, lcd_cs_n, lcd_sck, lcd_mosi, lcd_dc;
    wire update_done, transfer_done;
    wire [31:0] rendered_frames, late_frames, analysis_gap, spectrum_sequence;
    wire [4:0] debug_state;

    music_visualizer #(.CLK_HZ(27000000), .FRAME_HZ(20)) dut (
        .clk(clk), .rst_n(rst_n), .pcm_valid(pcm_valid), .pcm(pcm_in),
        .layer_mask(layer_mask), .base_note(base_note),
        .note_valid(note_valid), .note_on(note_on), .note_id(note_id),
        .note_number(note_number), .pitch_valid(pitch_valid),
        .pitch_id(pitch_id), .pitch_q8(pitch_q8),
        .lcd_reset_n(lcd_reset_n), .lcd_cs_n(lcd_cs_n), .lcd_sck(lcd_sck),
        .lcd_mosi(lcd_mosi), .lcd_dc(lcd_dc),
        .update_done(update_done), .transfer_done(transfer_done),
        .rendered_frames(rendered_frames), .late_frames(late_frames),
        .analysis_gap_samples(analysis_gap), .spectrum_sequence(spectrum_sequence)
    );

    // byte capture
    integer   stream_len = 0;
    integer   frame_len [0:15];
    integer   frames_seen = 0;
    integer   last_mark = 0;
    reg [7:0] shift;
    integer   bit_cnt = 0;
    reg       prev_sck = 1'b0;

    always @(posedge clk) begin
        prev_sck <= lcd_sck;
        if (lcd_sck && !prev_sck && !lcd_cs_n) begin
            shift = {shift[6:0], lcd_mosi};
            bit_cnt = bit_cnt + 1;
            if (bit_cnt == 8) begin
                bit_cnt = 0;
                stream_len = stream_len + 1;
            end
        end
    end

    // PCM driver: 1024 samples per FFT frame at 52734.375 Hz -> one sample every
    // 512 system clocks.  Wave capture then needs 1024 frames of 128 samples.
    integer sample_count = 0;
    integer tick = 0;
    always @(posedge clk) begin
        if (rst_n) begin
            tick <= tick + 1;
            if (tick % 4 == 0) begin
                pcm_valid <= 1'b1;
                pcm_in <= $random & 16'h7fff;
                sample_count <= sample_count + 1;
            end else begin
                pcm_valid <= 1'b0;
            end
        end
    end

    integer f;
    integer dbg_tick = 0;
    always @(posedge clk) if (rst_n) dbg_tick <= dbg_tick + 1;
    always @(posedge clk) if (rst_n && (dbg_tick % 200000 == 0))
        $display("  [t=%0d] state=%0d panel_ready=%b panel_done=%b bytes=%0d frames=%0d wave_ready=%b",
                 dbg_tick, debug_state, dut.u_renderer.panel_ready, dut.u_renderer.panel_done,
                 stream_len, rendered_frames, dut.u_renderer.wave_ready);
    initial begin
        for (f = 0; f < 16; f = f + 1) frame_len[f] = 0;
        rst_n = 1'b0;
        repeat (40) @(posedge clk);
        rst_n = 1'b1;

        // let it run; sample the byte count at every frame boundary
        f = 0;
        while (f < 3) begin
            @(posedge clk);
            if (rendered_frames != f) begin
                frame_len[f] = stream_len - last_mark;
                last_mark = stream_len;
                f = f + 1;
                $display("frame %0d: bytes=%0d  state=%0d late=%0d",
                         f, frame_len[f-1], debug_state, late_frames);
            end
        end
        $display("total bytes over %0d frames = %0d, late_frames=%0d", f, stream_len, late_frames);
        $display("RESULT: %s", (late_frames == 0) ? "PASS no late frames" : "FAIL late frames");
        $finish;
    end
endmodule
