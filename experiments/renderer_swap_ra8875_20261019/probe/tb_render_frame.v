// Frame-level check of the RA8875 renderer in isolation.
// Drives mv_renderer directly with a stand-in for the FFT and the wave capture
// so that one full frame can be simulated quickly, and counts the SPI bytes the
// new frame actually costs.
`timescale 1ns/1ps
module tb_render_frame;
    reg clk = 1'b0, rst_n = 1'b0;
    always #18.519 clk = ~clk;

    reg [3:0]  layer_mask = 4'b0001;
    reg [6:0]  base_note  = 7'd60;
    reg        spectrum_valid = 1'b0;
    reg [287:0] spectrum_levels = 288'h0;
    reg        wave_write_valid = 1'b0;
    reg        wave_complete = 1'b0;
    reg [6:0]  wave_index = 0;
    reg [15:0] wave_data = 0;
    reg        note_valid = 1'b0, note_on = 1'b1;
    reg [4:0]  note_id = 0;
    reg [6:0]  note_number = 7'd60;
    reg        pitch_valid = 1'b0;
    reg [4:0]  pitch_id = 0;
    reg [15:0] pitch_q8 = 0;
    wire lcd_reset_n, lcd_cs_n, lcd_sck, lcd_mosi, lcd_dc;
    wire update_done, transfer_done, wave_start;
    wire [31:0] rendered_frames, late_frames;
    wire [4:0] debug_state;

    mv_renderer #(.CLK_HZ(27000000), .FRAME_HZ(20),
                      .PANEL_RESET_US(1), .PANEL_RESET_WAIT_MS(1),
                      .PANEL_CLEAR_WAIT_US(5)) dut (
        .clk(clk), .rst_n(rst_n),
        .layer_mask(layer_mask), .base_note(base_note),
        .spectrum_valid(spectrum_valid), .spectrum_levels(spectrum_levels),
        .wave_write_valid(wave_write_valid), .wave_complete(wave_complete),
        .wave_index(wave_index), .wave_data(wave_data),
        .note_valid(note_valid), .note_on(note_on), .note_id(note_id),
        .note_number(note_number), .pitch_valid(pitch_valid),
        .pitch_id(pitch_id), .pitch_q8(pitch_q8),
        .lcd_reset_n(lcd_reset_n), .lcd_cs_n(lcd_cs_n), .lcd_sck(lcd_sck),
        .lcd_mosi(lcd_mosi), .lcd_dc(lcd_dc), .wave_start(wave_start),
        .update_done(update_done), .transfer_done(transfer_done),
        .rendered_frames(rendered_frames), .late_frames(late_frames),
        .debug_state(debug_state)
    );

    integer stream_len = 0;
    integer frame_len [0:7];
    integer last_mark = 0;
    reg [7:0] shift;
    integer bit_cnt = 0;
    reg prev_sck = 1'b0;

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

    // Stand-in for mv_wave_capture: on wave_start, emit 1024 samples then pulse
    // wave_complete.
    integer cap_count = 0;
    reg cap_running = 1'b0;
    always @(posedge clk) begin
        if (!rst_n) begin
            cap_running <= 1'b0;
            cap_count <= 0;
            wave_write_valid <= 1'b0;
            wave_complete <= 1'b0;
        end else begin
            wave_complete <= 1'b0;
            wave_write_valid <= 1'b0;
            if (wave_start && !cap_running) begin
                cap_running <= 1'b1;
                cap_count <= 0;
            end else if (cap_running) begin
                if (cap_count == 1023) begin
                    cap_running <= 1'b0;
                    wave_complete <= 1'b1;
                end else begin
                    cap_count <= cap_count + 1;
                    wave_index <= cap_count[6:0];
                    wave_write_valid <= 1'b1;
                    wave_data <= cap_count[15:0] + ($random & 16'h00ff);
                end
            end
        end
    end

    // Stand-in for mv_fft1024: one frame_valid heartbeat with rising levels.
    reg fft_running = 0;
    integer fft_wait = 0;
    always @(posedge clk) begin
        if (!rst_n) begin
            fft_running <= 0;
            spectrum_valid <= 1'b0;
        end else begin
            spectrum_valid <= 1'b0;
            if (wave_complete) fft_running <= 1'b1;
            if (fft_running) begin
                if (fft_wait == 0) begin
                    spectrum_valid <= 1'b1;
                    spectrum_levels <= ~spectrum_levels;
                    fft_wait <= 40;
                    fft_running <= 1'b0;
                end else fft_wait <= fft_wait - 1;
            end
        end
    end

    integer f, dbg_tick = 0;
    always @(posedge clk) if (rst_n && (dbg_tick % 50000 == 0))
        $display("  [t=%0d] rstate=%0d pstate=%0d bytes=%0d frames=%0d cap=%b wave_ready=%b",
                 dbg_tick, dut.state, dut.u_panel.state, stream_len, rendered_frames,
                 cap_running, dut.wave_ready);
    always @(posedge clk) if (rst_n) dbg_tick = dbg_tick + 1;
    initial begin
        for (f = 0; f < 8; f = f + 1) frame_len[f] = 0;
        rst_n = 0;
        repeat (40) @(posedge clk);
        rst_n = 1;

        f = 0;
        while (f < 4) begin
            @(posedge clk);
            if (rendered_frames != f) begin
                frame_len[f] = stream_len - last_mark;
                last_mark = stream_len;
                f = f + 1;
                $display("frame %0d: bytes=%0d state=%0d late=%0d", f, frame_len[f-1], debug_state, late_frames);
            end
        end
        $display("total bytes over %0d frames = %0d, late_frames=%0d", f, stream_len, late_frames);
        $display("RESULT: %s", (late_frames == 0) ? "PASS no late frames" : "FAIL late frames");
        $finish;
    end
endmodule
