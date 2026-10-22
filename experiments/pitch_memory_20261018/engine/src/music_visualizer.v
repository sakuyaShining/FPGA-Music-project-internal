// Public integration boundary. pcm_valid is a pulse for the actual output PCM16.
// Note/pitch inputs must be accepted device events, not unsent host intentions.
module music_visualizer #(parameter integer CLK_HZ=27000000,FRAME_HZ=20)(
    input wire clk,rst_n,pcm_valid,
    input wire signed [15:0] pcm,
    input wire [3:0] layer_mask,
    input wire [6:0] base_note,
    input wire note_valid,note_on,
    input wire [4:0] note_id,
    input wire [6:0] note_number,
    input wire pitch_valid,
    input wire [4:0] pitch_id,
    input wire signed [15:0] pitch_q8,
    output wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc,
    output wire update_done,transfer_done,
    output wire [31:0] rendered_frames,late_frames,analysis_gap_samples,
    output wire [31:0] spectrum_sequence
);
    wire spectrum_valid,wave_start,wave_write,wave_complete;
    wire [287:0] levels;
    wire [6:0] wave_index;
    wire [15:0] wave_data;
    mv_fft1024 u_fft(.clk(clk),.rst_n(rst_n),.sample_valid(pcm_valid),.sample(pcm),
        .frame_valid(spectrum_valid),.levels(levels),.frame_sequence(spectrum_sequence),
        .analysis_gap_samples(analysis_gap_samples),.bin_valid(),.bin_index(),.bin_real(),.bin_imag());
    mv_wave_capture u_wave(.clk(clk),.rst_n(rst_n),.start(wave_start),.sample_valid(pcm_valid),.sample(pcm),
        .busy(),.write_valid(wave_write),.complete(wave_complete),.write_index(wave_index),.write_data(wave_data));
    mv_renderer #(.CLK_HZ(CLK_HZ),.FRAME_HZ(FRAME_HZ)) u_renderer(
        .clk(clk),.rst_n(rst_n),.layer_mask(layer_mask),.base_note(base_note),
        .spectrum_valid(spectrum_valid),.spectrum_levels(levels),.wave_start(wave_start),
        .wave_write_valid(wave_write),.wave_complete(wave_complete),.wave_index(wave_index),.wave_data(wave_data),
        .note_valid(note_valid),.note_on(note_on),.note_id(note_id),.note_number(note_number),
        .pitch_valid(pitch_valid),.pitch_id(pitch_id),.pitch_q8(pitch_q8),
        .lcd_reset_n(lcd_reset_n),.lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),.lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc),
        .update_done(update_done),.transfer_done(transfer_done),.rendered_frames(rendered_frames),.late_frames(late_frames),.debug_state());
endmodule
