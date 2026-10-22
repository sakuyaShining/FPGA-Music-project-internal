`timescale 1ns/1ps
// Legal worst-change renderer inputs. No production RTL is changed. Init wait
// is accelerated and static painting skipped ONLY to time dirty work cheaply.
module tb_render_budget;
    reg clk=0,rst_n=0;
    always #5 clk=~clk;
    reg [3:0] layers=1;
    reg spectrum_valid=0;
    reg [287:0] levels=0;
    wire wave_start;
    reg wave_valid=0,wave_complete=0;
    reg [6:0] wave_index=0;
    reg [15:0] wave_data=0;
    reg note_valid=0,note_on=0;
    reg [4:0] note_id=0;
    reg [6:0] note_number=60;
    wire update_done,transfer_done;
    wire [31:0] frames,late;
    wire [4:0] state;
    wire cs,sck,mosi,dc,reset_n;
    integer cycle=0,fd,byte_count=0,pixels=0,windows=0,capture=0,capture_index=-1;
    integer start_cycle=0,start_bytes=0,start_pixels=0,start_windows=0;
    reg [4:0] previous_state=0;
    mv_renderer dut(.clk(clk),.rst_n(rst_n),.layer_mask(layers),.base_note(7'd48),
        .spectrum_valid(spectrum_valid),.spectrum_levels(levels),.wave_start(wave_start),
        .wave_write_valid(wave_valid),.wave_complete(wave_complete),.wave_index(wave_index),.wave_data(wave_data),
        .note_valid(note_valid),.note_on(note_on),.note_id(note_id),.note_number(note_number),
        .pitch_valid(1'b0),.pitch_id(5'd0),.pitch_q8(16'sd0),
        .lcd_reset_n(reset_n),.lcd_cs_n(cs),.lcd_sck(sck),.lcd_mosi(mosi),.lcd_dc(dc),
        .update_done(update_done),.transfer_done(transfer_done),.rendered_frames(frames),.late_frames(late),.debug_state(state));
    defparam dut.u_panel.CLK_HZ=1000000;
    always @(posedge clk) begin
        cycle=cycle+1;
        if(dut.u_panel.tx_valid&&dut.u_panel.tx_ready) byte_count=byte_count+1;
        if(dut.pixel_valid&&dut.pixel_ready) pixels=pixels+1;
        if(dut.window_start&&!dut.driver_busy) windows=windows+1;
        if(state==5 && previous_state==4) begin
            start_cycle=cycle;start_bytes=byte_count;start_pixels=pixels;start_windows=windows;
            $fdisplay(fd,"START %0d %0d",cycle,frames+1);
        end
        if(state==17&&previous_state==16)
            $fdisplay(fd,"TRACE %0d %0d %h",cycle,frames+1,dut.trace_bits);
        if(transfer_done) begin
            $fdisplay(fd,"TRANSFER %0d %0d %0d %0d %0d %0d %0d",cycle,frames+1,cycle-start_cycle,
                byte_count-start_bytes,pixels-start_pixels,windows-start_windows,late);
            $display("RENDER frame=%0d cycles=%0d ms_at_27MHz=%f late=%0d",frames+1,cycle-start_cycle,(cycle-start_cycle)/27000.0,late);
        end
        if(update_done) begin
            $fdisplay(fd,"FRAME %0d %0d %0d",cycle,frames,late);
            if(frames==4) begin $fclose(fd);$display("COMPLETE render budget 4 legal input transitions");$finish;end
        end
        previous_state=state;
    end
    always @(negedge clk) if(rst_n) begin
        wave_valid=0;wave_complete=0;spectrum_valid=0;
        if(wave_start) begin capture=capture+1;capture_index=0;end
        if(capture_index>=0) begin
            wave_valid=1;wave_index=capture_index;
            // Different spans can total at most 63 pixels (32+31). Equal
            // full-height spans are skipped by the renderer's comparison.
            wave_data=(capture%2==1 ? 16'h807f : 16'h887f);
            if(capture_index==127) begin wave_complete=1;capture_index=-1;end
            else capture_index=capture_index+1;
        end
        if(transfer_done) begin
            spectrum_valid=1;
            if(frames==0) begin levels={48{6'd63}};layers=15;end
            else if(frames==1) begin levels=0;layers=1;end
            else begin levels={48{6'd63}};layers=15;end
        end
    end
    initial begin
        fd=$fopen("metrics/render-budget.log","w");
        repeat(5) @(negedge clk);rst_n=1;
        @(negedge clk);note_valid=1;note_on=1;note_id=0;note_number=60;
        @(negedge clk);note_valid=0;
        wait(dut.driver_ready);
        @(negedge clk);force dut.state=5'd3;
        @(negedge clk);release dut.state;
        // A short accepted note entirely between trace samples.
        wait(frames==1);
        repeat(54000) @(negedge clk);
        note_valid=1;note_on=1;note_id=1;note_number=67;
        $fdisplay(fd,"NOTE_ON %0d 67",cycle);
        @(negedge clk);note_valid=0;
        repeat(135000) @(negedge clk);
        note_valid=1;note_on=0;
        $fdisplay(fd,"NOTE_OFF %0d 67",cycle);
        @(negedge clk);note_valid=0;
    end
    initial begin #100000000;$fatal(1,"budget timeout");end
endmodule
