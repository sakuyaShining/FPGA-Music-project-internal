`timescale 1ns/1ps
module tb_faders;
    parameter NF=8, NT=5;
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0, frame_valid=0, restore_valid=0;
    reg [NT-1:0] touch_active=0;
    reg [NT*10-1:0] touch_x=0,touch_y=0;
    reg [NT*4-1:0] touch_id=0;
    reg [NF*10-1:0] fader_x=0,zone_lo=0,zone_hi=0,restore_y=0;
    reg [9:0] radius=0,y_min=0,y_max=479;
    wire frame_ready,frame_done,restore_done,config_error;
    wire [NF*10-1:0] target_y;
    wire [NF-1:0] driven,left_present,right_present;
    wire [NF*4-1:0] left_id,right_id;
    rh_fader_bank #(.NF(NF),.NT(NT)) dut(.*);
    integer fd,rc,cmd,n=0,cycles,j,control_checks=0;
    reg [NF*10-1:0] ey,old_y;
    reg [NF-1:0] el,er;
    reg [NF*4-1:0] eli,eri;
    reg [1023:0] vector_path;

    task defaults;
    begin
        y_min=0;y_max=479;radius=1023;
        for(j=0;j<NF;j=j+1)begin
            fader_x[j*10+:10]=(800/NF)*j+(800/NF)/2;
            zone_lo[j*10+:10]=(800/NF)*j;
            zone_hi[j*10+:10]=(800/NF)*(j+1);
            restore_y[j*10+:10]=123;
        end
    end endtask

    initial begin
        if(!$value$plusargs("vectors=%s",vector_path))$fatal(1,"No vectors file");
        fd=$fopen(vector_path,"r"); if(!fd)$fatal(1,"Cannot read vectors");
        repeat(3)@(negedge clk);rst_n=1;
        while(!$feof(fd))begin
            @(negedge clk);
            rc=$fscanf(fd,"%d %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                cmd,touch_active,touch_x,touch_y,touch_id,fader_x,zone_lo,zone_hi,
                radius,y_min,y_max,restore_y,ey,el,er,eli,eri);
            if(rc!=17)$fatal(1,"Bad vector %0d fields=%0d",n,rc);
            old_y=target_y;
            if(cmd==1)begin
                restore_valid=1;
                @(negedge clk);restore_valid=0;
                if(!restore_done||frame_done||config_error)$fatal(1,"Restore handshake vector%0d",n);
            end else begin
                if(!frame_ready)$fatal(1,"Not ready vector%0d",n);
                frame_valid=1;
                @(negedge clk);frame_valid=0;
                // Deliberately poison every live input after acceptance.
                touch_active=~touch_active;touch_x=~touch_x;touch_y=~touch_y;touch_id=~touch_id;
                fader_x=~fader_x;zone_lo=~zone_lo;zone_hi=~zone_hi;radius=~radius;y_min=1023;y_max=0;
                cycles=0;
                while(!frame_done)begin
                    if(target_y!==old_y)$fatal(1,"Non-atomic update vector%0d",n);
                    if(frame_ready||config_error||restore_done)$fatal(1,"Bad busy flags vector%0d",n);
                    @(negedge clk);cycles=cycles+1;
                    if(cycles>NF*(NT+1)+2)$fatal(1,"Frame stalled");
                end
                if(cycles!=NF*(NT+1)+1)$fatal(1,"Unexpected latency %0d",cycles);
            end
            if(target_y!==ey||left_present!==el||right_present!==er||driven!==(el|er)||left_id!==eli||right_id!==eri)
                $fatal(1,"Mismatch vector%0d actual_y=%h expected=%h left=%h/%h right=%h/%h",n,target_y,ey,left_present,el,right_present,er);
            n=n+1;
            @(negedge clk);
            if(frame_done||restore_done)$fatal(1,"Completion pulse stuck");
        end
        $fclose(fd);
        // Invalid vertical geometry must not publish or change held values.
        @(negedge clk);defaults;old_y=target_y;y_min=500;y_max=100;frame_valid=1;
        @(negedge clk);frame_valid=0;
        if(!config_error||!frame_ready||target_y!==old_y)$fatal(1,"Invalid Y geometry");
        control_checks=control_checks+1;
        // Axis outside its region, and overlapping zones, must be rejected.
        @(negedge clk);defaults;zone_hi[9:0]=fader_x[9:0];frame_valid=1;
        @(negedge clk);frame_valid=0;
        if(!config_error||target_y!==old_y)$fatal(1,"Invalid axis geometry");
        control_checks=control_checks+1;
        if(NF>1)begin
            @(negedge clk);defaults;zone_hi[9:0]=(800/NF)+1;frame_valid=1;
            @(negedge clk);frame_valid=0;
            if(!config_error||target_y!==old_y)$fatal(1,"Overlapping regions accepted");
            control_checks=control_checks+1;
        end
        // Restore wins over valid, cancels a pending frame, and cannot later undo itself.
        @(negedge clk);defaults;touch_active=1;touch_x[9:0]=fader_x[9:0];touch_y[9:0]=20;frame_valid=1;
        @(negedge clk);frame_valid=0;
        repeat(3)@(negedge clk);
        restore_valid=1;frame_valid=1;
        @(negedge clk);restore_valid=0;frame_valid=0;
        if(!restore_done||frame_done||target_y!=={NF{10'd123}})$fatal(1,"Restore priority");
        repeat(NF*(NT+1)+3)begin
            @(negedge clk);
            if(frame_done||target_y!=={NF{10'd123}})$fatal(1,"Stale commit after restore");
        end
        control_checks=control_checks+1;
        // Asynchronous reset also cancels a pending frame.
        @(negedge clk);defaults;frame_valid=1;
        @(negedge clk);frame_valid=0;
        repeat(2)@(negedge clk);rst_n=0;
        @(negedge clk);rst_n=1;
        repeat(NF*(NT+1)+3)begin
            @(negedge clk);
            if(frame_done||target_y!=={NF{10'd479}})$fatal(1,"Stale commit after reset");
        end
        control_checks=control_checks+1;
        $display("PASS faders=%0d touches=%0d vectors=%0d control_checks=%0d latency_cycles=%0d",NF,NT,n,control_checks,NF*(NT+1)+1);
        $finish;
    end
    initial begin #20000000;$fatal(1,"Watchdog");end
endmodule
