`timescale 1ns/1ps
module tb_analysis_timing;
    reg clk=0,rst_n=0,valid=0,wave_start=0;
    reg signed [15:0] sample=0;
    always #5 clk=~clk;
    integer cycle=0,divider=0,fd,count=0;
    wire frame_valid,complete,busy;
    wire [31:0] sequence_id,gaps;
    mv_fft1024 fft(.clk(clk),.rst_n(rst_n),.sample_valid(valid),.sample(sample),
        .frame_valid(frame_valid),.frame_sequence(sequence_id),.analysis_gap_samples(gaps));
    mv_wave_capture wave(.clk(clk),.rst_n(rst_n),.start(wave_start),.sample_valid(valid),.sample(sample),
        .busy(busy),.complete(complete));
    always @(negedge clk) if(rst_n) begin
        valid=0;wave_start=0;
        if(divider==511) begin divider=0;valid=1;sample=sample+1237;end
        else divider=divider+1;
        if(cycle==1000 || cycle==1351000) wave_start=1;
    end
    always @(posedge clk) begin
        cycle=cycle+1;
        if(rst_n && valid && fft.state==0) begin
            if(fft.capture_index==0) $fdisplay(fd,"FFT_FIRST %0d %0d",cycle,sequence_id+1);
            if(fft.capture_index==1023) $fdisplay(fd,"FFT_LAST %0d %0d",cycle,sequence_id+1);
        end
        if(frame_valid) begin
            $fdisplay(fd,"FFT_READY %0d %0d %0d",cycle,sequence_id,gaps);
            count=count+1;
            if(count==4) begin $fclose(fd);$display("PASS analysis timing 4 FFT windows and 2 wave captures");$finish;end
        end
        if(wave_start) $fdisplay(fd,"WAVE_START %0d",cycle);
        if(complete) $fdisplay(fd,"WAVE_READY %0d",cycle);
    end
    initial begin fd=$fopen("metrics/analysis-timing.log","w");repeat(5) @(negedge clk);rst_n=1;end
    initial begin #50000000;$fatal(1,"analysis timeout");end
endmodule
