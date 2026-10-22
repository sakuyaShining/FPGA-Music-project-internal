`timescale 1ns/1ps
module tb_control;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,sample_ce=0,touch_valid=0,restore_valid=0;
    reg [4:0] touch_active=0;reg [49:0] touch_x=0,touch_y=0;reg [19:0] touch_id=0;
    reg [47:0] part_to_control=0;
    reg [9:0] radius=100,slew_step=1;
    wire touch_ready,frame_done,gain_done,error;
    wire [79:0] fader_y;wire [159:0] current_gain;
    rh_performance_control dut(.*);
    integer i,n,samples=0,frames=0,settled=0;
    reg [159:0] old_gain;
    task tick;
    begin
        @(negedge clk);old_gain=current_gain;sample_ce=1;
        @(negedge clk);sample_ce=0;
        n=0;
        while(!gain_done)begin
            if(current_gain!==old_gain)$fatal(1,"ramp published partially");
            @(negedge clk);n=n+1;if(n>18)$fatal(1,"ramp stalled");
        end
        if(n!=17)$fatal(1,"ramp latency");
        samples=samples+1;
        @(negedge clk);
    end endtask
    task report;
    begin
        while(!touch_ready)@(negedge clk);
        touch_valid=1;@(negedge clk);touch_valid=0;
        n=0;
        while(!frame_done)begin @(negedge clk);n=n+1;if(n>110)$fatal(1,"touch pipeline stalled");end
        frames=frames+1;@(negedge clk);
    end endtask
    always @(negedge clk)if(rst_n&&error)$fatal(1,"control error");
    initial begin
        // Map every pair of partials to one fader only in this fixture.
        for(i=0;i<16;i=i+1)part_to_control[i*3+:3]=i/2;
        repeat(4)@(negedge clk);rst_n=1;
        if(current_gain!=={16{10'd256}})$fatal(1,"unity on reset");
        // Two-sided midpoint at G1: y52 and y420 ->236 -> gain384.
        touch_active=3;touch_x[9:0]=40;touch_x[19:10]=60;
        touch_y[9:0]=52;touch_y[19:10]=420;touch_id[3:0]=1;touch_id[7:4]=2;
        report;
        if(fader_y[9:0]!=236)$fatal(1,"fader midpoint did not reach mapper");
        for(i=1;i<=128;i=i+1)begin
            tick;
            if(current_gain[9:0]!=(256+i)||current_gain[19:10]!=(256+i))$fatal(1,"incorrect ramp sample %0d",i);
            if(current_gain[159:20]!=={14{10'd256}})$fatal(1,"unmapped fader changed");
        end
        touch_active=0;report;tick;
        if(current_gain[9:0]!=384)$fatal(1,"release lost held target");
        // Lower half of G1 outside influence radius must not rewrite held value.
        radius=2;touch_active=1;touch_x[9:0]=40;touch_y[9:0]=420;report;tick;
        if(current_gain[9:0]!=384)$fatal(1,"out-of-radius touch altered target");
        // Restore starts a ramp; it does not jump or accept stale mapper output.
        @(negedge clk);restore_valid=1;@(negedge clk);restore_valid=0;
        if(current_gain[9:0]!=384)$fatal(1,"restore jumped gain");
        for(i=1;i<=128;i=i+1)begin tick;if(current_gain[9:0]!=384-i)$fatal(1,"restore ramp");end
        if(current_gain!=={16{10'd256}})$fatal(1,"restore not exactly unity");
        // Replacement mapping plus zero step uses minimum1 and does not freeze.
        for(i=0;i<16;i=i+1)part_to_control[i*3+:3]=7;
        radius=50;slew_step=0;touch_active=1;touch_x[9:0]=750;touch_y[9:0]=52;report;tick;
        if(current_gain!=={16{10'd257}})$fatal(1,"mapping/step clamp");
        slew_step=1023;tick;
        if(current_gain!=={16{10'd512}})$fatal(1,"large step overshot target");
        // Abort a touch before it can reach the gain bank.
        touch_y[9:0]=420;while(!touch_ready)@(negedge clk);
        touch_valid=1;@(negedge clk);touch_valid=0;repeat(5)@(negedge clk);
        restore_valid=1;@(negedge clk);restore_valid=0;
        repeat(120)@(negedge clk);
        tick;if(current_gain!=={16{10'd256}})$fatal(1,"stale target after restore");
        $display("PASS control frames=%0d ramp_samples=%0d coherent_commit restore_hold mapping",frames,samples);$finish;
    end
    initial begin #5000000;$fatal(1,"control watchdog");end
endmodule
