`timescale 1ns/1ps
module tb_panel;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,frame_valid=0,restore_valid=0;
    reg [4:0] touch_active=0;
    reg [49:0] touch_x=0,touch_y=0;
    reg [19:0] touch_id=0;
    reg [9:0] radius=0;
    wire frame_ready,frame_done,restore_done,config_error;
    wire [79:0] target_y;wire [7:0] driven;
    rh_fader_panel dut(.*);
    reg [79:0] fx,zlo,zhi,seed,expected,old_y;
    reg [9:0] lo,hi;reg [7:0] el,er;reg [31:0] eli,eri;
    integer fd,cmd,rc,n=0,cycles;
    initial begin
        fd=$fopen("evidence/vectors-panel.txt","r");if(!fd)$fatal(1,"No panel vectors");
        repeat(3)@(negedge clk);rst_n=1;
        if(target_y!=={8{10'd420}})$fatal(1,"Panel reset target");
        while(!$feof(fd))begin
            @(negedge clk);
            rc=$fscanf(fd,"%d %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                cmd,touch_active,touch_x,touch_y,touch_id,fx,zlo,zhi,radius,lo,hi,seed,expected,el,er,eli,eri);
            if(rc!=17)$fatal(1,"Bad panel vector");
            old_y=target_y;
            if(cmd==1)begin
                restore_valid=1;@(negedge clk);restore_valid=0;
                if(!restore_done||frame_done)$fatal(1,"Panel restore");
            end else begin
                if(!frame_ready)$fatal(1,"Panel not ready");
                frame_valid=1;@(negedge clk);frame_valid=0;
                touch_x=~touch_x;touch_y=~touch_y;touch_active=~touch_active;radius=~radius;
                cycles=0;
                while(!frame_done)begin
                    if(target_y!==old_y)$fatal(1,"Panel non-atomic update");
                    @(negedge clk);cycles=cycles+1;
                    if(cycles>50)$fatal(1,"Panel stalled");
                end
                if(cycles!=49)$fatal(1,"Panel latency");
            end
            if(config_error||target_y!==expected||driven!==(el|er))$fatal(1,"Panel mismatch %0d",n);
            n=n+1;@(negedge clk);
        end
        $display("PASS panel wrapper vectors=%0d latency_cycles=49",n);$finish;
    end
    initial begin #20000000;$fatal(1,"Panel watchdog");end
endmodule
