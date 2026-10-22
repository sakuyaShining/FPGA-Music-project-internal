`timescale 1ns/1ps
module tb_fft;
    reg clk=0,rst_n=0,sample_valid=0;
    reg signed [15:0] sample=0;
    always #5 clk=~clk;
    wire frame_valid,bin_valid;
    wire [287:0] levels;
    wire [31:0] sequence_id,gaps;
    wire [8:0] bin_index;
    wire signed [15:0] bin_real,bin_imag;
    reg [15:0] samples[0:1023];
    integer fd,i,case_id=0,seen=0;
    mv_fft1024 dut(.clk(clk),.rst_n(rst_n),.sample_valid(sample_valid),.sample(sample),
        .frame_valid(frame_valid),.levels(levels),.frame_sequence(sequence_id),.analysis_gap_samples(gaps),
        .bin_valid(bin_valid),.bin_index(bin_index),.bin_real(bin_real),.bin_imag(bin_imag));
    always @(posedge clk) if(bin_valid) begin
        $fdisplay(fd,"%0d %0d %0d %0d",case_id,bin_index,$signed(bin_real),$signed(bin_imag));
        seen=seen+1;
    end
    task run_case;
        input [255:0] filename;
        begin
            $readmemh(filename,samples);
            for(i=0;i<1024;i=i+1) begin
                @(negedge clk); sample_valid=1; sample=samples[i];
                // The single-tone case also tests consecutive valid samples.
                if(case_id!=2) begin @(negedge clk); sample_valid=0; end
            end
            @(negedge clk); sample_valid=0;
            // Busy samples must never stall the source; they are counted separately.
            repeat(4) begin @(negedge clk); sample_valid=1; @(negedge clk); sample_valid=0; end
            wait(frame_valid);
            if(seen!=512) $fatal(1,"wrong bin count");
            $display("FFT_CASE %0d bins=%0d gaps=%0d levels=%h",case_id,seen,gaps,levels);
            @(negedge clk); case_id=case_id+1; seen=0;
        end
    endtask
    initial begin
        fd=$fopen("fft-bins.txt","w");
        repeat(4) @(negedge clk); rst_n=1;
        run_case("test-silence.hex"); run_case("test-dc.hex"); run_case("test-single.hex");
        run_case("test-dual.hex"); run_case("test-negative_full.hex");
        $fclose(fd); $display("PASS fft interface 5 cases"); $finish;
    end
    initial begin #10000000; $fatal(1,"FFT timeout"); end
endmodule
