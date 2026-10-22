`timescale 1ns/1ps
module tb_live_audio_monitor;
    reg clk=0,rst_n=0,sample_en=0,wr_en=0,event_valid=0,event_on=0;
    reg [7:0] wr_addr=0,wr_data=0;
    reg [6:0] event_note=69;
    reg [3:0] velocity=12;
    reg signed [23:0] sample=0;
    reg tx_done=0;
    wire enabled,owns,start;
    wire [7:0] data;
    integer slow=0;
    integer cycle=0, sample_number=0, timer=0, fd, emitted=0;
    always #5 clk=~clk;
    live_audio_monitor dut(.clk(clk),.rst_n(rst_n),.sample_en(sample_en),.sample_valid(sample_en),.sample(sample),
        .wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),
        .event_valid(event_valid),.event_on(event_on),.event_note(event_note),.event_velocity(velocity),
        .tx_available(1'b1),.tx_done(tx_done),.enabled(enabled),.owns_tx(owns),.tx_start(start),.tx_data(data));
    always @(negedge clk) begin
        cycle=cycle+1;sample_en=0;event_valid=0;
        if(cycle%512==0) begin
            sample_en=1;sample=sample_number*256;sample_number=sample_number+1;
            if(sample_number==20 || sample_number==600) begin event_valid=1;event_on=1;end
            if(sample_number==400 || sample_number==900) begin event_valid=1;event_on=0;end
        end
        tx_done=0;
        if(start) begin
            $fdisplay(fd,"%02x",data);emitted=emitted+1;timer=slow ? 600 : 180;
        end else if(timer>0) begin
            timer=timer-1;
            if(timer==0) tx_done=1;
        end
    end
    initial begin
        slow=$test$plusargs("SLOW");
        fd=$fopen("live-bytes.hex","w");
        repeat(10) @(negedge clk);rst_n=1;
        @(negedge clk);wr_en=1;wr_addr=8'hB5;wr_data=1;
        @(negedge clk);wr_en=0;
        repeat(512*3800) @(negedge clk);
        @(negedge clk);wr_en=1;wr_data=0;
        @(negedge clk);wr_en=0;
        repeat(700000) @(negedge clk);
        if((!slow && dut.losses!==0) || (slow && dut.losses==0) || dut.enabled!==0 || owns!==0) $fatal(1,"overflow or stop failure");
        $fclose(fd);$display("RESULT live_audio=PASS bytes=%0d",emitted);$finish;
    end
endmodule
