`timescale 1ns/1ps
// The reference is copied from the preserved core source. Only the candidate
// copy exposes two read-only wires. This is functional isolation, not PnR proof.
module tb_engine_isolation;
    reg clk=0,rst_n=0,test_mode=1,ev_valid=0,ev_on=0;
    reg [6:0] ev_note=60;
    always #5 clk=~clk;
    tri [15:0] pad_ref,pad_candidate;
    genvar j;
    generate for(j=0;j<16;j=j+1) begin: pulldowns
        pulldown(pad_ref[j]);pulldown(pad_candidate[j]);
    end endgenerate
    wire ref_din,ref_ws,ref_bck,ref_pa,ref_tx;
    wire cand_din,cand_ws,cand_bck,cand_pa,cand_tx;
    wire [5:0] ref_led,cand_led;
    wire ref_vv,ref_vo,cand_vv,cand_vo;
    wire [4:0] ref_group,cand_group;
    wire [6:0] ref_note,cand_note;
    wire monitor_valid;
    wire signed [15:0] monitor_pcm;
    wire lcd_reset_n,lcd_cs_n,lcd_sck,lcd_mosi,lcd_dc;
    wire [31:0] frames,late,gaps,spectra;
    integer checked=0,samples=0,nonzero=0,lcd_edges=0,note_events=0;
    tdm_top_reference #(.FINGER_EXPR(1),.BOARD_DIAG(0),.LIVE_MONITOR(0)) reference_engine(
        .clk(clk),.rst_n(rst_n),.test_mode(test_mode),.preset(2'd0),
        .ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(4'd12),
        .uart_rx_pin(1'b1),.uart_tx_pin(ref_tx),.led(ref_led),
        .dac_din(ref_din),.dac_ws(ref_ws),.dac_bck(ref_bck),.pa_en(ref_pa),.pad(pad_ref),
        .finger_valid(1'b0),.finger_cmd(2'd0),.finger_id(5'd0),.finger_group(5'd0),.finger_position(12'sd0),
        .voice_valid(ref_vv),.voice_on(ref_vo),.voice_group(ref_group),.voice_note(ref_note));
    tdm_top #(.FINGER_EXPR(1),.BOARD_DIAG(0),.LIVE_MONITOR(0)) candidate_engine(
        .clk(clk),.rst_n(rst_n),.test_mode(test_mode),.preset(2'd0),
        .ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(4'd12),
        .uart_rx_pin(1'b1),.uart_tx_pin(cand_tx),.led(cand_led),
        .dac_din(cand_din),.dac_ws(cand_ws),.dac_bck(cand_bck),.pa_en(cand_pa),.pad(pad_candidate),
        .finger_valid(1'b0),.finger_cmd(2'd0),.finger_id(5'd0),.finger_group(5'd0),.finger_position(12'sd0),
        .voice_valid(cand_vv),.voice_on(cand_vo),.voice_group(cand_group),.voice_note(cand_note),
        .monitor_valid(monitor_valid),.monitor_pcm(monitor_pcm));
    music_visualizer vis(.clk(clk),.rst_n(rst_n),.pcm_valid(monitor_valid),.pcm(monitor_pcm),
        .layer_mask(4'b0001),.base_note(7'd48),.note_valid(cand_vv),.note_on(cand_vo),
        .note_id(cand_group),.note_number(cand_note),.pitch_valid(1'b0),.pitch_id(5'd0),.pitch_q8(16'sd0),
        .lcd_reset_n(lcd_reset_n),.lcd_cs_n(lcd_cs_n),.lcd_sck(lcd_sck),.lcd_mosi(lcd_mosi),.lcd_dc(lcd_dc),
        .rendered_frames(frames),.late_frames(late),.analysis_gap_samples(gaps),.spectrum_sequence(spectra));
    // Only this isolation test accelerates initialization delays. The separate
    // pin-stream test uses 27MHz and real controller waits. SCK divider unchanged.
    defparam vis.u_renderer.u_panel.CLK_HZ=1000000;
    always @(posedge lcd_sck) if(!lcd_cs_n) lcd_edges=lcd_edges+1;
    always @(negedge clk) if(rst_n) begin
        checked=checked+1;
        if({ref_din,ref_ws,ref_bck,ref_pa,ref_tx,ref_led,ref_vv,ref_vo,ref_group,ref_note} !==
           {cand_din,cand_ws,cand_bck,cand_pa,cand_tx,cand_led,cand_vv,cand_vo,cand_group,cand_note})
            $fatal(1,"engine output mismatch at cycle %0d",checked);
        if(reference_engine.audio !== candidate_engine.audio) $fatal(1,"PCM24 mismatch");
        if(monitor_valid) begin
            samples=samples+1;
            if(samples>20 && (^monitor_pcm)===1'bx) $fatal(1,"unknown PCM16");
            if(monitor_pcm!=0) nonzero=nonzero+1;
        end
        if(cand_vv) note_events=note_events+1;
    end
    task note;
        input onoff;
        input [6:0] number;
        begin
            @(negedge clk);ev_valid=1;ev_on=onoff;ev_note=number;
            @(negedge clk);ev_valid=0;
            repeat(500) @(negedge clk);
        end
    endtask
    initial begin
        repeat(10) @(negedge clk);rst_n=1;
        repeat(1100000) @(negedge clk); // Boot and sustain the 512 oscillator grid.
        test_mode=0;
        repeat(2000) @(negedge clk);
        note(1,60);note(1,64);note(1,67);
        repeat(200000) @(negedge clk);
        note(0,64);note(0,60);note(0,67);
        repeat(200000) @(negedge clk);
        if(samples<2000 || nonzero<100 || lcd_edges<1000 || spectra<1 || note_events<6)
            $fatal(1,"insufficient activity: samples=%0d nonzero=%0d edges=%0d spectra=%0d notes=%0d",samples,nonzero,lcd_edges,spectra,note_events);
        $display("PASS engine isolation cycles=%0d samples=%0d nonzero=%0d lcd_edges=%0d spectra=%0d note_events=%0d",
                  checked,samples,nonzero,lcd_edges,spectra,note_events);
        $finish;
    end
endmodule
