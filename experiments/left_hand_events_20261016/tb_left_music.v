`timescale 1ns/1ps
module tb_left_music;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,left_valid=0,left_calibration=0,ev_valid=0,ev_on=0;
    reg [6:0] ev_note=0;
    reg [3:0] left_contact=0,left_invalid=0;
    reg [35:0] left_position={4{9'd128}};
    reg [31:0] left_sequence=0;
    reg touch_valid=0,restore_valid=0;
    reg [4:0] touch_active=0;
    wire touch_ready,touch_done;
    wire [159:0] gains;
    wire left_ready,voice_valid,voice_on,pcm_valid;
    wire [4:0] voice_group;wire [6:0] voice_note;
    wire signed [23:0] pcm;
    wire [3:0] bound_contacts,blocked_contacts;
    wire frame_error,link_error,sensor_error,watchdog_error;
    wire finger_valid;wire [1:0] finger_cmd;wire [4:0] finger_id,finger_group;wire signed [11:0] finger_position;
    tri [15:0] pad;
    left_music_probe #(.NF(4)) dut(.clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(4'd12),.preset(2'd0),.pad(pad),
        .left_valid(left_valid),.left_ready(left_ready),.left_contact(left_contact),.left_invalid(left_invalid),.left_position(left_position),.left_sequence(left_sequence),.left_calibration(left_calibration),.left_note_map({7'd67,7'd64,7'd60,7'd60}),.left_velocity(4'd12),
        .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound_contacts),.blocked_contacts(blocked_contacts),
        .finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),.finger_group(finger_group),.finger_position(finger_position),
        .touch_valid(touch_valid),.touch_ready(touch_ready),.touch_done(touch_done),.touch_active(touch_active),.touch_x(50'd50),.touch_y(50'd52),.touch_id(20'd1),.radius(10'd50),.slew_step(10'd16),.part_to_control(48'd0),.restore_valid(restore_valid),.voice_mask(32'hffffffff),.gains(gains),
        .voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_note(voice_note),.pcm_valid(pcm_valid),.pcm(pcm));
    integer cycles=0,samples=0,nonzero=0,events=0,owned_ons=0,owned_offs=0,moves=0,binds=0,g0,g1,ons_before,i;
    reg [7:0] tag0,tag1;
    always @(posedge clk)if(rst_n)begin
        cycles=cycles+1;
        if(pcm_valid)begin samples=samples+1;if(pcm!=0)nonzero=nonzero+1;end
        if(voice_valid)events=events+1;
        if(dut.own_valid&&dut.own_ready)begin if(dut.own_on)owned_ons=owned_ons+1;else owned_offs=owned_offs+1;end
        if(finger_valid)begin if(finger_cmd==0)binds=binds+1;if(finger_cmd==1)moves=moves+1;end
        if(frame_error||link_error||sensor_error||watchdog_error)$fatal(1,"unexpected bridge error");
    end
    task report;
        input [3:0] ct;
        begin
            @(negedge clk);while(!left_ready)@(negedge clk);left_contact=ct;left_valid=1;
            @(negedge clk);left_valid=0;left_sequence=left_sequence+1;
            while(!left_ready)@(negedge clk);
        end
    endtask
    task legacy_note;
        input onoff;input [6:0] note;
        begin @(negedge clk);ev_valid=1;ev_on=onoff;ev_note=note;@(negedge clk);ev_valid=0;repeat(100)@(negedge clk);end
    endtask
    task right_report;
        begin
            @(negedge clk);while(!touch_ready)@(negedge clk);touch_valid=1;
            @(negedge clk);touch_valid=0;while(!touch_done)@(negedge clk);
            @(negedge clk);
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;repeat(4096)@(negedge clk);
        fork
            report(3);
            begin repeat(5)@(negedge clk);legacy_note(1,50);legacy_note(1,51);legacy_note(1,52);end
        join
        g0=dut.bridge.group[0];g1=dut.bridge.group[1];
        if(g0==g1||bound_contacts!=3||!dut.core.finger_active[g0]||!dut.core.finger_active[g1])$fatal(1,"same pitch bind failed");
        tag0=dut.core.u_nm.group_start_tag[g0];tag1=dut.core.u_nm.group_start_tag[g1];
        legacy_note(0,50);legacy_note(0,51);legacy_note(0,52);
        repeat(512*20)@(negedge clk);
        touch_active=1;right_report;repeat(512*24)@(negedge clk);
        if(gains!={16{10'd512}})$fatal(1,"right hand did not affect owned voices");
        left_position[8:0]=192;report(3);
        if(dut.core.finger_offsets[g0*18+:18]==0||dut.core.finger_offsets[g1*18+:18]!=0||owned_ons!=2||dut.core.u_nm.group_start_tag[g0]!=tag0||dut.core.u_nm.group_start_tag[g1]!=tag1)$fatal(1,"move retrigger/ownership");
        touch_active=0;right_report;repeat(512*4)@(negedge clk);
        if(gains!={16{10'd512}})$fatal(1,"right hand hold lost");
        @(negedge clk);restore_valid=1;@(negedge clk);restore_valid=0;repeat(512*24)@(negedge clk);
        if(gains!={16{10'd256}}||dut.core.u_nm.group_start_tag[g0]!=tag0||owned_ons!=2)$fatal(1,"right restore retriggered owned notes");
        legacy_note(1,60);legacy_note(0,60);
        if(!dut.core.nm_active[g0]||!dut.core.nm_active[g1])$fatal(1,"legacy off touched physical contacts");
        report(2);if(dut.core.nm_active[g0]||!dut.core.nm_active[g1])$fatal(1,"independent release");
        left_position[8:0]=128;report(3);
        if(dut.core.finger_offsets[g0*18+:18]!=0||owned_ons!=3)$fatal(1,"rebind kept old pitch offset");
        for(i=40;i<70;i=i+1)legacy_note(1,i);
        if(dut.core.nm_active!=32'hffffffff)$fatal(1,"full32 allocation");
        legacy_note(1,90);
        if(bound_contacts[0]||dut.core.u_nm.gtab[g0]!=90)$fatal(1,"steal notification");
        ons_before=owned_ons;left_position[8:0]=220;left_position[17:9]=150;report(3);
        if(owned_ons!=ons_before||dut.core.finger_active[g0]||dut.core.finger_offsets[g1*18+:18]==0)$fatal(1,"stolen contact changed new note");
        report(2);if(!dut.core.nm_active[g0]||dut.core.u_nm.gtab[g0]!=90)$fatal(1,"stolen off killed replacement");
        report(0);for(i=40;i<70;i=i+1)legacy_note(0,i);legacy_note(0,90);
        if(dut.core.nm_active||bound_contacts)$fatal(1,"cleanup hung notes");
        repeat(512*40)@(negedge clk);
        if(nonzero<20||owned_ons!=3||owned_offs!=2||binds!=3||moves<2)$fatal(1,"insufficient audio/gesture activity");
        if(dut.core.pinq_ovf||dut.core.ev_q_ovf)$fatal(1,"event loss");
        $display("PASS left_music cycles=%0d samples=%0d nonzero_pcm=%0d events=%0d owned_ons=%0d owned_offs=%0d moves=%0d real_engine same_pitch independent_slide release full32_steal both_hands_hold_restore",cycles,samples,nonzero,events,owned_ons,owned_offs,moves);$finish;
    end
    initial begin #20000000;$fatal(1,"watchdog");end
endmodule
