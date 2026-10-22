`timescale 1ns/1ps
module tb_allocator;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ev_valid=0,ev_on=0,ev_owned=0,refresh=0;
    reg [6:0] ev_note=0;
    reg [7:0] ev_vel=128;
    reg [12:0] instance_id=0;
    wire busy,ack,result_valid,result_owned,result_on,result_success;
    wire [12:0] result_instance;
    wire [1:0] result_group,voice_group;
    wire voice_valid,voice_on;wire [6:0] voice_note;
    wire [3:0] active;
    wire [5:0] slot[0:2];wire [23:0] inc[0:2];wire [7:0] amp[0:2],tag[0:2];wire [22:0] epar[0:2];
    wire [2:0] load,gate;wire signed [17:0] gq[0:2];
    note_map_owned #(.NG(4),.OWNED_EVENTS(1)) dut(.clk(clk),.rst_n(rst_n),.ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.ev_owned(ev_owned),.ev_instance(instance_id),
        .preset(2'd0),.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),.spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(refresh),.rf_lo(7'd0),.rf_hi(8'd4),
        .load_en(load[0]),.load_slot(slot[0]),.load_inc(inc[0]),.load_amp(amp[0]),.load_gate(gate[0]),.load_start_tag(tag[0]),.load_epar(epar[0]),.load_gq(gq[0]),.busy(busy),.ev_ack(ack),.active(active),
        .voice_valid(voice_valid),.voice_on(voice_on),.voice_note(voice_note),.voice_group(voice_group),.result_valid(result_valid),.result_owned(result_owned),.result_on(result_on),.result_success(result_success),.result_instance(result_instance),.result_group(result_group));
    note_map_owned #(.NG(4),.OWNED_EVENTS(0)) disabled(.clk(clk),.rst_n(rst_n),.ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.ev_owned(ev_owned),.ev_instance(instance_id),
        .preset(2'd0),.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),.spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(refresh),.rf_lo(7'd0),.rf_hi(8'd4),
        .load_en(load[1]),.load_slot(slot[1]),.load_inc(inc[1]),.load_amp(amp[1]),.load_gate(gate[1]),.load_start_tag(tag[1]),.load_epar(epar[1]),.load_gq(gq[1]));
    note_map #(.NG(4)) original(.clk(clk),.rst_n(rst_n),.ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),
        .preset(2'd0),.tilt_vbias(10'sd0),.tilt_vgain(8'd0),.vel_vscale(9'd256),.tilt(8'h70),.spec_commit(1'b0),.spec_we(1'b0),.spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.refresh_valid(refresh),.rf_lo(7'd0),.rf_hi(8'd4),
        .load_en(load[2]),.load_slot(slot[2]),.load_inc(inc[2]),.load_amp(amp[2]),.load_gate(gate[2]),.load_start_tag(tag[2]),.load_epar(epar[2]),.load_gq(gq[2]));
    integer legacy_phase=1,cycles=0,events=0,results=0,voices=0,i,j,g0,g1,g2,rgroup;
    reg rsuccess;reg [6:0] rnote;
    always @(negedge clk)if(rst_n)begin
        cycles=cycles+1;
        if(result_valid)results=results+1;if(voice_valid)voices=voices+1;
        if(legacy_phase&&cycles>5)
            for(j=0;j<2;j=j+1)begin
                if({load[j],slot[j],inc[j],amp[j],gate[j],tag[j],epar[j],gq[j]}!=={load[2],slot[2],inc[2],amp[2],gate[2],tag[2],epar[2],gq[2]})$fatal(1,"legacy load timing/value mismatch");
            end
    end
    task event_send;
        input owned,onoff;input [12:0] id;input [6:0] note;
        begin
            @(negedge clk);while(busy)@(negedge clk);
            ev_valid=1;ev_owned=owned;ev_on=onoff;instance_id=id;ev_note=note;
            @(negedge clk);ev_valid=0;
            while(!result_valid)@(negedge clk);
            if(result_owned!=owned||result_instance!=(owned?id:0)||result_on!=onoff)$fatal(1,"result identity");
            rgroup=result_group;rsuccess=result_success;rnote=voice_note;events=events+1;
            @(negedge clk);while(busy)@(negedge clk);repeat(2)@(negedge clk);
        end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;
        for(i=0;i<100;i=i+1)begin
            event_send(0,i%3!=0,0,(i%11==0)?127:(48+i%6));
            if(i%13==0)begin refresh=1;@(negedge clk);refresh=0;repeat(110)@(negedge clk);end
        end
        legacy_phase=0;rst_n=0;repeat(3)@(negedge clk);rst_n=1;
        event_send(1,1,32,60);g0=rgroup;
        event_send(1,1,33,60);g1=rgroup;if(g0==g1||active!=3)$fatal(1,"same-MIDI contacts merged");
        event_send(0,1,0,60);g2=rgroup;if(g2==g0||g2==g1)$fatal(1,"legacy merged owned voice");
        event_send(0,0,0,60);if(active!=3)$fatal(1,"legacy off released owned voices");
        event_send(1,0,999,60);if(rsuccess||active!=3)$fatal(1,"unknown off released voice");
        event_send(1,0,32,77);if(!rsuccess||active!=2||rnote!=60)$fatal(1,"owner off must use actual allocated pitch");
        event_send(1,1,64,60);if(rgroup!=g0)$fatal(1,"free group reuse");
        event_send(1,0,32,60);if(rsuccess||active!=3)$fatal(1,"old generation off released new note");
        refresh=1;@(negedge clk);refresh=0;repeat(110)@(negedge clk);
        if(dut.group_instance[g0]!=64||dut.group_instance[g1]!=33)$fatal(1,"refresh changed ownership");
        event_send(1,0,33,60);event_send(1,0,64,60);if(active)$fatal(1,"independent release");
        rst_n=0;repeat(3)@(negedge clk);rst_n=1;
        for(i=0;i<4;i=i+1)event_send(1,1,100+i,127);
        if(active!=15)$fatal(1,"MIDI127 owned allocation");
        event_send(0,1,0,127);if(rgroup!=0||dut.group_owned[0])$fatal(1,"full voice steal");
        event_send(1,0,100,127);if(rsuccess||active!=15)$fatal(1,"stolen owner off affected new voice");
        event_send(1,0,101,127);if(!rsuccess||active!=13)$fatal(1,"remaining owner off");
        $display("PASS allocator events=%0d legacy100_load_exact same_pitch_instances source_isolation stale_off refresh steal midi127 completion_identity",events);$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
