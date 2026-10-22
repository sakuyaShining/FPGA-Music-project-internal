// Read-only audio analysis. 1024-point radix-2 DIT, Hann window, 1/2 per stage.
// The input is never backpressured. Samples arriving during transform are counted
// as analysis gaps, not dropped from the audio engine. No audio path is driven.
module mv_fft1024(
    input wire clk, rst_n, sample_valid,
    input wire signed [15:0] sample,
    output reg frame_valid,
    output reg [287:0] levels,
    output reg [31:0] frame_sequence, analysis_gap_samples,
    output reg bin_valid,
    output reg [8:0] bin_index,
    output reg signed [15:0] bin_real, bin_imag
);
    localparam CAP=0,DRAIN=1,FA=2,LA=3,FB=4,LB=5,MUL=6,ROT=7,WA=8,WB=9,
               CLEAR=10,SF=11,SL=12,SU=13,PUBLISH=14;
    reg [3:0] state, stage;
    reg [9:0] capture_index, held_index, base;
    reg [8:0] j, scan_index;
    reg [5:0] clear_index, publish_index, measured_band, measured_height;
    reg pending;
    reg signed [15:0] held_sample, window_q;
    reg signed [15:0] real_mem[0:1023], imag_mem[0:1023];
    reg signed [15:0] window_rom[0:1023], cos_rom[0:511], sin_rom[0:511];
    reg [5:0] band_rom[0:511], peak[0:47];
    reg signed [15:0] qr,qi,wr,wi,ar,ai,br,bi;
    reg signed [31:0] prr,pii,pri,pir;
    reg signed [17:0] tr,ti;
    wire [9:0] half_size=(10'd1<<stage);
    wire [9:0] addr_a=base+{1'b0,j};
    wire [9:0] addr_b=addr_a+half_size;
    wire [8:0] twiddle_index=j<<(9-stage);
    wire [9:0] read_address=(state==SF || state==SL || state==SU) ? {1'b0,scan_index} :
                           ((state==FB || state==LB) ? addr_b : addr_a);
    wire signed [31:0] window_product=held_sample*window_q;
    wire signed [18:0] sum_r=$signed(ar)+$signed(tr), sum_i=$signed(ai)+$signed(ti);
    wire signed [18:0] dif_r=$signed(ar)-$signed(tr), dif_i=$signed(ai)-$signed(ti);
    wire signed [32:0] rotated_r=$signed(prr)-$signed(pii);
    wire signed [32:0] rotated_i=$signed(pri)+$signed(pir);
    wire [16:0] abs_r=qr[15] ? -$signed({qr[15],qr}) : {1'b0,qr};
    wire [16:0] abs_i=qi[15] ? -$signed({qi[15],qi}) : {1'b0,qi};
    wire [17:0] magnitude={1'b0,abs_r}+{1'b0,abs_i};
    function [9:0] reverse10;
        input [9:0] value;
        integer k;
        begin for(k=0;k<10;k=k+1) reverse10[k]=value[9-k]; end
    endfunction
    function signed [15:0] half_saturate;
        input signed [18:0] value;
        reg signed [18:0] v;
        begin
            v=value>>>1;
            if(v>32767) half_saturate=16'sh7fff;
            else if(v< -32768) half_saturate=16'sh8000;
            else half_saturate=v[15:0];
        end
    endfunction
    function [5:0] log_height;
        input [17:0] value;
        integer k, msb;
        reg [17:0] shifted;
        begin
            msb=0;
            for(k=0;k<18;k=k+1) if(value[k]) msb=k;
            shifted=(msb>=2) ? value>>(msb-2) : value<<(2-msb);
            if(value<16) log_height=0;
            else if(msb>=15) log_height=63;
            else log_height=((msb-4)*6)+shifted[1:0];
        end
    endfunction
    initial begin
        $readmemh("hann1024.hex",window_rom);
        $readmemh("cos1024.hex",cos_rom);
        $readmemh("sin1024.hex",sin_rom);
        $readmemh("bands1024.hex",band_rom);
    end
    // One synchronous read and one write per RAM per cycle; no array reset.
    always @(posedge clk) begin
        qr<=real_mem[read_address]; qi<=imag_mem[read_address];
        wr<=cos_rom[twiddle_index]; wi<=sin_rom[twiddle_index];
        window_q<=window_rom[capture_index];
        if(rst_n) begin
            if(pending) begin
                real_mem[reverse10(held_index)]<=window_product>>>15;
                imag_mem[reverse10(held_index)]<=0;
            end else if(state==WA) begin
                real_mem[addr_a]<=half_saturate(sum_r); imag_mem[addr_a]<=half_saturate(sum_i);
            end else if(state==WB) begin
                real_mem[addr_b]<=half_saturate(dif_r); imag_mem[addr_b]<=half_saturate(dif_i);
            end
        end
    end
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            state<=CAP; stage<=0; capture_index<=0; held_index<=0; held_sample<=0; pending<=0;
            base<=0; j<=0; scan_index<=0; clear_index<=0; publish_index<=0;
            frame_valid<=0; levels<=0; frame_sequence<=0; analysis_gap_samples<=0;
            bin_valid<=0; bin_index<=0; bin_real<=0; bin_imag<=0;
            ar<=0;ai<=0;br<=0;bi<=0;prr<=0;pii<=0;pri<=0;pir<=0;tr<=0;ti<=0;
            measured_band<=0; measured_height<=0;
        end else begin
            frame_valid<=0; bin_valid<=0; pending<=0;
            if(sample_valid && state!=CAP) analysis_gap_samples<=analysis_gap_samples+1;
            case(state)
                CAP: if(sample_valid) begin
                    pending<=1; held_sample<=sample; held_index<=capture_index;
                    capture_index<=capture_index+1;
                    if(capture_index==1023) begin state<=DRAIN; stage<=0; base<=0; j<=0; end
                end
                DRAIN: state<=FA;
                FA: state<=LA;
                LA: begin ar<=qr; ai<=qi; state<=FB; end
                FB: state<=LB;
                LB: begin br<=qr; bi<=qi; state<=MUL; end
                MUL: begin prr<=br*wr; pii<=bi*wi; pri<=br*wi; pir<=bi*wr; state<=ROT; end
                ROT: begin tr<=rotated_r>>>15; ti<=rotated_i>>>15; state<=WA; end
                WA: state<=WB;
                WB: begin
                    if({1'b0,j}+1==half_size) begin
                        j<=0;
                        if({1'b0,base}+({1'b0,half_size}<<1)>=1024) begin
                            base<=0;
                            if(stage==9) begin clear_index<=0; state<=CLEAR; end
                            else begin stage<=stage+1; state<=FA; end
                        end else begin base<=base+(half_size<<1); state<=FA; end
                    end else begin j<=j+1; state<=FA; end
                end
                CLEAR: begin
                    peak[clear_index]<=0;
                    if(clear_index==47) begin scan_index<=0; state<=SF; end
                    else clear_index<=clear_index+1;
                end
                SF: state<=SL;
                SL: begin
                    measured_height<=log_height(magnitude); measured_band<=band_rom[scan_index];
                    bin_valid<=1; bin_index<=scan_index; bin_real<=qr; bin_imag<=qi; state<=SU;
                end
                SU: begin
                    if(scan_index!=0 && measured_height>peak[measured_band]) peak[measured_band]<=measured_height;
                    if(scan_index==511) begin publish_index<=0; state<=PUBLISH; end
                    else begin scan_index<=scan_index+1; state<=SF; end
                end
                PUBLISH: begin
                    levels[publish_index*6+:6]<=peak[publish_index];
                    if(publish_index==47) begin frame_valid<=1; frame_sequence<=frame_sequence+1; state<=CAP; end
                    else publish_index<=publish_index+1;
                end
            endcase
        end
    end
endmodule
