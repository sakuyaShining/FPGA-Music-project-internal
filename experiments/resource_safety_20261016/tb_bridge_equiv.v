`timescale 1ns/1ps
module tb_bridge;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,frame_valid=0,frame_calibration=0;
    reg [1:0] contact=0,invalid=0;
    reg [17:0] position={9'd90,9'd60};
    reg [31:0] frame_sequence=0;
    wire frame_ready,own_valid;
    wire own_ready;
    wire own_on;wire [6:0] own_note;wire [3:0] own_vel;wire [12:0] own_instance;
    reg result_valid=0,result_on=0,result_success=1;
    reg [12:0] result_instance=0;reg [4:0] result_group=0;
    reg steal=0;reg [4:0] stolen_group=0;
    wire voice_valid=result_valid||steal;
    wire voice_on=steal?1'b1:result_on;
    wire [4:0] voice_group=steal?stolen_group:result_group;
    wire finger_valid;wire [1:0] finger_cmd;wire [4:0] finger_id,finger_group;wire signed [11:0] finger_position;
    wire frame_error,link_error,sensor_error,watchdog_error;
    wire [1:0] bound_contacts,blocked_contacts;
    left_contact_bridge #(.NF(2),.BAD_FRAMES(3),.FRAME_TIMEOUT(2000),.LINK_TIMEOUT(128)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.contact(contact),.invalid(invalid),.position(position),.frame_sequence(frame_sequence),.frame_calibration(frame_calibration),.note_map({7'd60,7'd60}),.velocity(4'd12),
        .own_valid(own_valid),.own_ready(own_ready),.own_on(own_on),.own_note(own_note),.own_vel(own_vel),.own_instance(own_instance),
        .result_valid(result_valid),.result_owned(1'b1),.result_on(result_on),.result_success(result_success),.result_instance(result_instance),.result_group(result_group),.voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),
        .finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),.finger_group(finger_group),.finger_position(finger_position),.frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound_contacts),.blocked_contacts(blocked_contacts));
    wire ref_frame_ready;
    wire ref_own_valid;
    wire ref_own_on;
    wire [6:0] ref_own_note;
    wire [3:0] ref_own_vel;
    wire [12:0] ref_own_instance;
    wire ref_finger_valid;
    wire [1:0] ref_finger_cmd;
    wire [4:0] ref_finger_id;
    wire [4:0] ref_finger_group;
    wire [11:0] ref_finger_position;
    wire ref_frame_error;
    wire ref_link_error;
    wire ref_sensor_error;
    wire ref_watchdog_error;
    wire [1:0] ref_bound_contacts;
    wire [1:0] ref_blocked_contacts;
    left_contact_bridge_reference #(.NF(2),.BAD_FRAMES(3),.FRAME_TIMEOUT(2000),.LINK_TIMEOUT(128)) ref_impl(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(ref_frame_ready),.contact(contact),.invalid(invalid),.position(position),.frame_sequence(frame_sequence),.frame_calibration(frame_calibration),.note_map({7'd60,7'd60}),.velocity(4'd12),
        .own_valid(ref_own_valid),.own_ready(own_ready),.own_on(ref_own_on),.own_note(ref_own_note),.own_vel(ref_own_vel),.own_instance(ref_own_instance),
        .result_valid(result_valid),.result_owned(1'b1),.result_on(result_on),.result_success(result_success),.result_instance(result_instance),.result_group(result_group),.voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),
        .finger_valid(ref_finger_valid),.finger_cmd(ref_finger_cmd),.finger_id(ref_finger_id),.finger_group(ref_finger_group),.finger_position(ref_finger_position),.frame_error(ref_frame_error),.link_error(ref_link_error),.sensor_error(ref_sensor_error),.watchdog_error(ref_watchdog_error),.bound_contacts(ref_bound_contacts),.blocked_contacts(ref_blocked_contacts));
    integer equality_clocks=0,qq;
    always @(posedge clk)begin
        #2;
        if({frame_ready,own_valid,own_on,own_note,own_vel,own_instance,finger_valid,finger_cmd,finger_id,finger_group,finger_position,frame_error,link_error,sensor_error,watchdog_error,bound_contacts,blocked_contacts}!=={ref_frame_ready,ref_own_valid,ref_own_on,ref_own_note,ref_own_vel,ref_own_instance,ref_finger_valid,ref_finger_cmd,ref_finger_id,ref_finger_group,ref_finger_position,ref_frame_error,ref_link_error,ref_sensor_error,ref_watchdog_error,ref_bound_contacts,ref_blocked_contacts})$fatal(1,"bridge cycle mismatch at %0d",equality_clocks);
        for(qq=0;qq<2;qq=qq+1)
            if({dut.generation[qq],dut.sounding_note[qq],dut.last_position[qq],dut.bad_count[qq]}!=={ref_impl.generation[qq],ref_impl.sounding_note[qq],ref_impl.last_position[qq],ref_impl.bad_count[qq]})$fatal(1,"bridge row mismatch");
        equality_clocks=equality_clocks+1;
    end

    reg pending=0,pause_reply=0,queued_on=0;
    reg [12:0] queued_instance=0;
    integer cycle=0,remaining=0,ons=0,offs=0,binds=0,moves=0,frames=0,last_reply_cycle=-100,old_ons,old_offs,k,start_generation;
    assign own_ready=!pending&&(cycle%5!=0);
    reg [24:0] held;
    reg stalled=0;
    always @(posedge clk)begin
        cycle=cycle+1;
        if(rst_n)begin
            result_valid<=0;
            if(own_valid&&own_ready)begin
                pending<=1;remaining<=7;queued_on<=own_on;queued_instance<=own_instance;
                if(own_on)ons=ons+1;else offs=offs+1;
            end else if(pending&&!pause_reply)begin
                if(remaining==0)begin pending<=0;result_valid<=1;result_on<=queued_on;result_instance<=queued_instance;result_group<={4'd0,queued_instance[0]};end
                else remaining<=remaining-1;
            end
            if(result_valid)last_reply_cycle=cycle;
            if(finger_valid)begin
                if(finger_cmd==0)begin if(cycle-last_reply_cycle<2)$fatal(1,"bind before allocator state settles");binds=binds+1;end
                if(finger_cmd==1)moves=moves+1;
            end
        end
    end
    always @(negedge clk)begin
        if(stalled&&{own_on,own_note,own_vel,own_instance}!==held)$fatal(1,"request payload changed under backpressure");
        stalled=own_valid&&!own_ready;held={own_on,own_note,own_vel,own_instance};
    end
    task report;
        input [1:0] ct,bad;
        input cal;
        begin
            @(negedge clk);while(!frame_ready)@(negedge clk);
            contact=ct;invalid=bad;frame_calibration=cal;frame_valid=1;
            @(negedge clk);frame_valid=0;frame_sequence=frame_sequence+1;
            while(!frame_ready)@(negedge clk);frames=frames+1;
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        report(3,0,0);if(ons!=2||binds!=2||bound_contacts!=3)$fatal(1,"two contacts bind");
        position={9'd100,9'd70};report(3,0,0);if(ons!=2||moves!=2)$fatal(1,"movement retriggered");
        report(3,1,0);report(3,1,0);if(offs)$fatal(1,"brief invalid input released too early");
        report(3,1,0);if(offs!=1||!sensor_error||bound_contacts!=2||blocked_contacts!=1)$fatal(1,"bounded bad-node release");
        report(3,0,0);if(ons!=2)$fatal(1,"fault retrigger while still held");
        report(2,0,0);report(3,0,0);if(ons!=3||dut.generation[0]!=2)$fatal(1,"new generation after release");
        report(3,0,1);if(offs!=3||bound_contacts)$fatal(1,"calibration release");
        report(0,0,0);report(3,0,0);if(ons!=5)$fatal(1,"fresh contact after calibration");
        frame_sequence=frame_sequence+1;report(3,0,0);if(!frame_error||bound_contacts||offs!=5)$fatal(1,"frame gap handling");
        report(3,0,0);if(ons!=5)$fatal(1,"gap auto-retrigger");
        report(0,0,0);report(1,0,0);old_offs=offs;
        repeat(2200)@(negedge clk);if(!watchdog_error||bound_contacts||offs!=old_offs+1)$fatal(1,"missing-frame watchdog release");
        old_ons=ons;report(1,0,0);if(ons!=old_ons)$fatal(1,"watchdog auto-retrigger");
        report(0,0,0);report(3,0,0);old_ons=ons;old_offs=offs;
        @(negedge clk);steal=1;stolen_group=0;@(negedge clk);steal=0;
        position={9'd110,9'd80};report(1,0,0);
        if(bound_contacts||ons!=old_ons||offs!=old_offs+1)$fatal(1,"stolen contact controlled new owner");
        report(0,0,0);
        // Completion stall is diagnosed, but no guessed binding or token reuse.
        pause_reply=1;
        @(negedge clk);contact=1;frame_valid=1;@(negedge clk);frame_valid=0;frame_sequence=frame_sequence+1;
        repeat(200)@(negedge clk);if(!link_error||bound_contacts||frame_ready||own_valid)$fatal(1,"late completion safety");
        pause_reply=0;while(!frame_ready)@(negedge clk);report(0,0,0);
        start_generation=dut.generation[0];
        for(k=0;k<260;k=k+1)begin report(1,0,0);report(0,0,0);end
        if(dut.generation[0]!=((start_generation+260)%256)||bound_contacts)$fatal(1,"generation wrap");
        $display("PASS bridge_reference_equiv frames=%0d ons=%0d offs=%0d binds=%0d moves=%0d backpressure bind_delay fault_watchdog gap calibration steal late_completion generation_wrap260",frames,ons,offs,binds,moves);$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
