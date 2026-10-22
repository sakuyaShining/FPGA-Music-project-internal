`timescale 1ns/1ps
module tb_visualizer;
    reg clk=0,rst_n=0,pcm_valid=0;
    always #18.519 clk=~clk;
    reg signed [15:0] pcm=0;
    reg [15:0] tone[0:1023];
    integer sample_div=0,sample_index=0;
    reg [3:0] layers=1;
    reg note_valid=0,note_on=0,pitch_valid=0;
    reg [4:0] note_id=0,pitch_id=0;
    reg [6:0] note_number=60;
    reg signed [15:0] pitch_q8=0;
    wire reset_n,cs_n,sck,mosi,dc,update_done,transfer_done;
    wire [31:0] frames,late,gaps,spectra;
    integer fd,bit_count=0,received_bytes=0,updated=0;
    reg [7:0] received;
    reg saved_dc;
    realtime last_rise=-1,last_fall=-1,last_data=-1000,cs_start;
    realtime previous_update=0,interval;
    music_visualizer dut(.clk(clk),.rst_n(rst_n),.pcm_valid(pcm_valid),.pcm(pcm),
        .layer_mask(layers),.base_note(7'd48),.note_valid(note_valid),.note_on(note_on),
        .note_id(note_id),.note_number(note_number),.pitch_valid(pitch_valid),.pitch_id(pitch_id),.pitch_q8(pitch_q8),
        .lcd_reset_n(reset_n),.lcd_cs_n(cs_n),.lcd_sck(sck),.lcd_mosi(mosi),.lcd_dc(dc),
        .update_done(update_done),.transfer_done(transfer_done),.rendered_frames(frames),.late_frames(late),.analysis_gap_samples(gaps),.spectrum_sequence(spectra));
    always @(negedge clk) if(rst_n) begin
        pcm_valid=0;
        if(sample_div==511) begin
            sample_div=0;pcm_valid=1;pcm=tone[sample_index];sample_index=(sample_index+1)%1024;
        end else sample_div=sample_div+1;
    end
    always @(mosi) begin
        if(reset_n&&!cs_n&&last_rise>=0&&$realtime-last_rise<29.999) $fatal(1,"MOSI hold");
        last_data=$realtime;
    end
    always @(negedge reset_n) begin bit_count=0;$fdisplay(fd,"RESET %.3f",$realtime);end
    always @(posedge reset_n) $fdisplay(fd,"RELEASE %.3f",$realtime);
    always @(negedge cs_n) if(reset_n) begin cs_start=$realtime;bit_count=0;end
    always @(posedge sck) if(reset_n&&!cs_n) begin
        if($realtime-cs_start<39.999 || $realtime-last_data<29.999) $fatal(1,"SPI setup");
        if(last_rise>=0&&$realtime-last_rise<99.999) $fatal(1,"SPI cycle");
        if(last_fall>=0&&$realtime-last_fall<39.999) $fatal(1,"SPI low");
        if(bit_count==0) saved_dc=dc;else if(saved_dc!=dc) $fatal(1,"DC within byte");
        received={received[6:0],mosi};bit_count=bit_count+1;last_rise=$realtime;
        if(bit_count==8) begin $fdisplay(fd,"BYTE %.3f %0d %02x",$realtime,saved_dc,received);bit_count=0;received_bytes=received_bytes+1;end
    end
    always @(negedge sck) if(reset_n&&!cs_n&&last_rise>=0) begin
        if($realtime-last_rise<39.999) $fatal(1,"SPI high");last_fall=$realtime;
    end
    always @(posedge cs_n) if(reset_n&&bit_count!=0) $fatal(1,"partial byte");
    always @(posedge clk) if(transfer_done) $fdisplay(fd,"TRANSFER %.3f %0d",$realtime,frames+1);
    always @(posedge clk) if(update_done) begin
        updated=updated+1;
        interval=($realtime-previous_update)/1e6;
        $fdisplay(fd,"FRAME %.3f %0d %0d %0d %0d %0d",$realtime,frames,late,gaps,spectra,layers);
        $display("FRAME %0d interval_ms=%.3f late=%0d fft=%0d",frames,interval,late,spectra);
        if(updated>1 && interval>51.0) $fatal(1,"display update interval >51ms");
        previous_update=$realtime;
        if(updated==8) begin
            if(late!=0 || spectra==0) $fatal(1,"late or missing FFT");
            $fclose(fd);$display("PASS visualizer 8 updates, bytes=%0d",received_bytes);$finish;
        end
    end
    initial begin
        fd=$fopen("visualizer-spi.log","w");$readmemh("test-dual.hex",tone);
        repeat(8) @(negedge clk);rst_n=1;
        @(negedge clk);note_valid=1;note_on=1;note_id=0;note_number=60;
        @(negedge clk);note_valid=0;
        wait(frames>=2);
        @(negedge clk);layers=3;note_valid=1;note_on=1;note_id=1;note_number=67;
        @(negedge clk);note_valid=0;
        wait(frames>=4);
        @(negedge clk);pitch_valid=1;pitch_id=0;pitch_q8=62*256;
        @(negedge clk);pitch_valid=0;
        wait(frames>=6);
        @(negedge clk);note_valid=1;note_on=0;note_id=1;
        @(negedge clk);note_valid=0;
    end
    initial begin #2000000000;$fatal(1,"visualizer timeout");end
endmodule
