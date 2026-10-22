`timescale 1ns/1ps
module tb_sensor_layers;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,calibrate=0;
    reg [5:0] sense_n=6'b111111;
    reg [181:0] left_note_map=0;
    wire request,sck,mosi,latch,report_valid,report_ready,report_calibration;
    wire [25:0] contact,invalid,bound_contacts,blocked_contacts;
    wire [233:0] position;
    wire [31:0] seq;
    wire frame_error,link_error,sensor_error,watchdog_error,sensor_protocol_error,sensor_grant_error;
    wire voice_valid,voice_on,pcm_valid,finger_valid;
    wire [4:0] voice_group,finger_id,finger_group;
    wire [6:0] voice_note;
    wire [1:0] finger_cmd;
    wire signed [11:0] finger_position;
    wire signed [23:0] pcm;
    tri [15:0] pad;
    instrument_layer_probe dut(.layer_selection(4'b0011),.cfg_valid(1'b0),.cfg_commit(1'b0),.cfg_slot(2'd0),.cfg_part(4'd0),.cfg_word(48'd0),.clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.ev_valid(1'b0),.ev_on(1'b0),.ev_note(7'd0),.ev_vel(4'd0),.preset(2'd0),.pad(pad),
        .sense_n(sense_n),.calibrate(calibrate),.scan_bus_grant(1'b1),.sensor_report_ready(report_ready),.left_note_map(left_note_map),.left_velocity(4'd12),
        .threshold_on(14'd20),.threshold_off(14'd10),.scan_bus_request(request),.scan_bus_sck(sck),.scan_bus_mosi(mosi),.scan_latch(latch),
        .sensor_report_valid(report_valid),.sensor_report_calibration(report_calibration),.sensor_protocol_error(sensor_protocol_error),.sensor_grant_error(sensor_grant_error),.sensor_contact(contact),.sensor_invalid(invalid),.sensor_position(position),.sensor_sequence(seq),
        .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound_contacts),.blocked_contacts(blocked_contacts),
        .finger_valid(finger_valid),.finger_cmd(finger_cmd),.finger_id(finger_id),.finger_group(finger_group),.finger_position(finger_position),
        .touch_valid(1'b0),.touch_active(5'd0),.touch_x(50'd0),.touch_y(50'd0),.touch_id(20'd0),.radius(10'd50),.slew_step(10'd1),.part_to_control(48'd0),.restore_valid(1'b0),.voice_mask(32'hffffffff),
        .voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_note(voice_note),.pcm_valid(pcm_valid),.pcm(pcm));
    reg [7:0] shift=0,control=8'hff;
    reg prior_sck=0,prior_latch=0;
    integer cycle=0,charge_at=0,charge_frame=0,edges=0,node,delay,j,reports=0,ons=0,offs=0,moves=0,samples=0,nonzero=0,last_sample=-1,g0=-1,g12=-1,g13=-1;
    reg motion_checked=0;
    reg [31:0] pcm_hash=0;integer unknown_pcm=0;
    always @(negedge clk)begin
        cycle=cycle+1;
        if(sck&&!prior_sck)begin shift={shift[6:0],mosi};edges=edges+1;end
        if(latch&&!prior_latch)begin
            if(edges!=8)$fatal(1,"incomplete scan word");edges=0;control=shift;
            if(control[5]&&!control[4])begin charge_at=cycle;charge_frame=dut.sensor.scanner.scan_sequence;end
        end
        prior_sck=sck;prior_latch=latch;
        for(j=0;j<6;j=j+1)begin
            node=control[3:0]*6+j;delay=15+node;
            if(charge_frame>=1&&charge_frame<=3)begin
                if(node==2||node==36||node==39)delay=delay+40;
                if(charge_frame==3&&node==0)delay=delay+40;
            end
            sense_n[j]=!(!control[4]&&control[5]&&cycle-charge_at>=delay);
        end
        if(rst_n&&dut.music.bridge.last_sequence>=3&&dut.music.bridge.state==0&&!motion_checked)begin
            if(dut.music.core.finger_offsets[g0*18+:18]==0||dut.music.core.finger_offsets[g12*18+:18]!=0||dut.music.core.finger_offsets[g13*18+:18]!=0||ons!=6)$fatal(1,"physical position did not independently move pitch");
            if(dut.music.core.finger_offsets[dut.music.layers.groups1[0]*18+:18]!=dut.music.core.finger_offsets[g0*18+:18])$fatal(1,"sensor slide did not reach second layer");
            motion_checked=1;
        end
    end
    always @(posedge clk)if(rst_n)begin
        if(frame_error||link_error||sensor_error||watchdog_error||sensor_protocol_error||sensor_grant_error||dut.music.core.u_tdm.u_pmod.update_overrun)$fatal(1,"pipeline fault");
        if(report_valid&&report_ready)begin
            if(seq!=reports||invalid)$fatal(1,"coherent sensor frame");reports=reports+1;
        end
        if(voice_valid)begin if(voice_on)ons=ons+1;else offs=offs+1;end
        if(dut.music.result_valid&&dut.music.result_owned&&dut.music.result_on)begin
            case(dut.music.result_instance[4:0])0:g0=dut.music.layers.groups0[0];12:g12=dut.music.layers.groups0[12];13:g13=dut.music.layers.groups0[13];endcase
        end
        if(finger_valid&&finger_cmd==1)moves=moves+1;
        if(pcm_valid)begin
            if(last_sample>=0&&cycle-last_sample!=512)$fatal(1,"audio sampling interrupted");
            last_sample=cycle;samples=samples+1;if(pcm!=0)nonzero=nonzero+1;
            if((^pcm)===1'bx)begin unknown_pcm=unknown_pcm+1;if(cycle>4096)$fatal(1,"unknown PCM after warmup");end
            else pcm_hash={pcm_hash[26:0],pcm_hash[31:27]}^{8'd0,pcm};
        end
    end
    initial begin
        // Example only: two rows each include both octave endpoints. The two
        // middle C4 positions therefore deliberately share MIDI60.
        for(j=0;j<26;j=j+1)left_note_map[j*7+:7]=(j<13)?48+j:60+j-13;
        repeat(4)@(negedge clk);rst_n=1;calibrate=1;@(negedge clk);calibrate=0;
        wait(offs==6);repeat(16)@(negedge clk);
        if(g0<0||g12<0||g13<0||g12==g13||ons!=6||!motion_checked||bound_contacts||dut.music.core.nm_active)$fatal(1,"end-to-end ownership/release");
        repeat(512*40)@(negedge clk);
        if(nonzero<20||moves!=1)$fatal(1,"insufficient actual audio/slide");
        $display("PASS sensor_layers cycles=%0d samples=%0d nonzero_pcm=%0d reports=%0d ons=%0d offs=%0d moves=%0d pcm_hash=%08x startup_unknown_pcm=%0d physical_words_to_real_pcm same_midi_endpoints independent_pitch continuous512",cycle,samples,nonzero,reports,ons,offs,moves,pcm_hash,unknown_pcm);$finish;
    end
    initial begin #10000000;$fatal(1,"watchdog");end
endmodule
