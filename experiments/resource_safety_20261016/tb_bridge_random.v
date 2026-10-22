`timescale 1ns/1ps
module tb_bridge_random;
    localparam NF=26;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,frame_valid=0,frame_calibration=0;
    reg [NF-1:0] contact=0,invalid=0;
    reg [NF*9-1:0] position=0;
    reg [NF*7-1:0] note_map=0;
    reg [31:0] frame_sequence=0;
    reg [3:0] velocity=0;
    reg result_valid=0,result_on=0,result_success=0;
    reg [12:0] result_instance=0;
    reg [4:0] result_group=0;
    reg steal=0;reg [4:0] stolen_group=0;
    wire own_ready;
    wire voice_valid=result_valid||steal;
    wire voice_on=steal||result_on;
    wire [4:0] voice_group=steal?stolen_group:result_group;
    wire ready_a,ready_b,valid_a,valid_b,on_a,on_b,fv_a,fv_b,fe_a,fe_b,le_a,le_b,se_a,se_b,we_a,we_b;
    wire [6:0] note_a,note_b;
    wire [3:0] vel_a,vel_b;
    wire [12:0] inst_a,inst_b;
    wire [1:0] fc_a,fc_b;
    wire [4:0] fi_a,fi_b,fg_a,fg_b;
    wire signed [11:0] fp_a,fp_b;
    wire [NF-1:0] bound_a,bound_b,block_a,block_b;
`define BPORT(S) .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(ready_``S),.contact(contact),.invalid(invalid),.position(position),.frame_sequence(frame_sequence),.frame_calibration(frame_calibration),.note_map(note_map),.velocity(velocity),.own_valid(valid_``S),.own_ready(own_ready),.own_on(on_``S),.own_note(note_``S),.own_vel(vel_``S),.own_instance(inst_``S),.result_valid(result_valid),.result_owned(1'b1),.result_on(result_on),.result_success(result_success),.result_instance(result_instance),.result_group(result_group),.voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.finger_valid(fv_``S),.finger_cmd(fc_``S),.finger_id(fi_``S),.finger_group(fg_``S),.finger_position(fp_``S),.frame_error(fe_``S),.link_error(le_``S),.sensor_error(se_``S),.watchdog_error(we_``S),.bound_contacts(bound_``S),.blocked_contacts(block_``S)
    left_contact_bridge #(.NF(NF),.BAD_FRAMES(8),.FRAME_TIMEOUT(5000),.LINK_TIMEOUT(128)) dut(`BPORT(a));
    left_contact_bridge_reference #(.NF(NF),.BAD_FRAMES(8),.FRAME_TIMEOUT(5000),.LINK_TIMEOUT(128)) ref_impl(`BPORT(b));
    integer cycles=0,frames=0,events=0,moves=0,row_checks=0,waits,j,k,delay=0;
    reg pending=0,pending_on=0;
    reg [12:0] pending_instance=0;
    reg [31:0] rng=32'h71dace65;
    task random_step;begin rng=rng^(rng<<13);rng=rng^(rng>>17);rng=rng^(rng<<5);end endtask
    assign own_ready=!pending&&cycles%8!=0;
    always @(posedge clk)begin
        cycles=cycles+1;
        if(!rst_n)begin pending<=0;result_valid<=0;delay<=0;end
        else begin
            result_valid<=0;
            if(valid_a&&own_ready)begin
                pending<=1;pending_on<=on_a;pending_instance<=inst_a;delay<=(events%79==0)?160:cycles%23;events=events+1;
            end else if(pending)begin
                if(delay==0)begin pending<=0;result_valid<=1;result_on<=pending_on;result_instance<=pending_instance;result_group<=pending_instance[4:0];result_success<=cycles%7!=0;end
                else delay<=delay-1;
            end
            if(fv_a&&fc_a==1)moves=moves+1;
        end
        #2;
        if({ready_a,valid_a,on_a,note_a,vel_a,inst_a,fv_a,fc_a,fi_a,fg_a,fp_a,fe_a,le_a,se_a,we_a,bound_a,block_a}!=={ready_b,valid_b,on_b,note_b,vel_b,inst_b,fv_b,fc_b,fi_b,fg_b,fp_b,fe_b,le_b,se_b,we_b,bound_b,block_b})$fatal(1,"random bridge output divergence cycle=%0d",cycles);
        for(j=0;j<NF;j=j+1)begin
            if({dut.generation[j],dut.sounding_note[j],dut.last_position[j],dut.bad_count[j],dut.group[j]}!=={ref_impl.generation[j],ref_impl.sounding_note[j],ref_impl.last_position[j],ref_impl.bad_count[j],ref_impl.group[j]})$fatal(1,"random row %0d mismatch",j);
            row_checks=row_checks+1;
        end
        if(dut.state!=0&&dut.metadata_cur!=={ref_impl.generation[dut.index],ref_impl.sounding_note[dut.index],ref_impl.last_position[dut.index],ref_impl.bad_count[dut.index]})$fatal(1,"cached row not coherent at %0d state=%0d",cycles,dut.state);
    end
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        for(k=0;k<600;k=k+1)begin
            waits=0;while(!ready_a)begin @(negedge clk);waits=waits+1;if(waits>10000)$fatal(1,"request stuck");end
            @(negedge clk);random_step;contact=rng[25:0];random_step;invalid=(k%17<8)?rng[25:0]:0;
            frame_calibration=(k%43==0);velocity=rng[3:0];
            for(j=0;j<NF;j=j+1)begin random_step;position[j*9+:9]=rng%257;note_map[j*7+:7]=rng[6:0];end
            if(k%29==0)frame_sequence=frame_sequence+3;
            frame_valid=1;@(negedge clk);frame_valid=0;frame_sequence=frame_sequence+1;frames=frames+1;
            repeat(3)@(negedge clk);
            steal=k%3==0;stolen_group=k%26;@(negedge clk);steal=0;
            if(k%101==0)repeat(6000)@(negedge clk);
            if(k==200||k==400)begin rst_n=0;repeat(3)@(negedge clk);rst_n=1;end
        end
        while(!ready_a)@(negedge clk);
        if(events<500||moves<100)$fatal(1,"insufficient random activity");
        $display("PASS bridge_random frames=%0d clocks=%0d row_checks=%0d events=%0d moves=%0d NF26 reset gaps calibration invalid backpressure late_reply steal forwarded_rows",frames,cycles,row_checks,events,moves);$finish;
    end
    initial begin #30000000;$fatal(1,"watchdog");end
endmodule
