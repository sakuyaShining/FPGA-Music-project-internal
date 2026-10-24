`timescale 1ns/1ps
module tb_layers;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,left_valid=0;
    reg [3:0] selection=3,contact=0;
    reg [35:0] position={4{9'd128}};
    reg [31:0] seq=0;
    reg cfg_valid=0,cfg_commit=0;
    reg [1:0] cfg_slot=0;
    reg [3:0] cfg_part=0;
    reg [47:0] cfg_word=0;
    wire cfg_ready,cfg_applied,cfg_error,left_ready;
    wire frame_error,link_error,sensor_error,watchdog_error,layer_protocol_error,layer_selection_error;
    wire [3:0] bound,blocked;
    wire pcm_valid;wire signed [23:0] pcm;
    reg ev_valid=0,ev_on=0;reg [6:0] ev_note=0;
    tri [15:0] pad;
    reg [47:0] example_sustain[0:15],example_strike[0:15];
    initial begin $readmemh("../../sustain.hex",example_sustain);$readmemh("../../strike.hex",example_strike);end
    left_layer_music_probe #(.NF(4)) dut(.clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.pad(pad),
        .ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(4'd12),.preset(2'd3),
        .layer_selection(selection),.cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),
        .layer_protocol_error(layer_protocol_error),.layer_selection_error(layer_selection_error),
        .left_valid(left_valid),.left_ready(left_ready),.left_contact(contact),.left_invalid(4'd0),.left_position(position),.left_sequence(seq),.left_calibration(1'b0),.left_note_map({7'd67,7'd64,7'd60,7'd60}),.left_velocity(4'd12),
        .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound),.blocked_contacts(blocked),
        .touch_valid(1'b0),.touch_active(5'd0),.touch_x(50'd0),.touch_y(50'd0),.touch_id(20'd0),.radius(10'd50),.slew_step(10'd16),.part_to_control(48'd0),.restore_valid(1'b0),.voice_mask(32'hffffffff),.pcm_valid(pcm_valid),.pcm(pcm));
    integer cycles=0,samples=0,nonzero=0,last_sample=-1,ons=0,offs=0,applies=0,errors=0,i,a,b,c,d,oldamp,oldtag;
    reg [31:0] pcm_hash=0,i2s_hash=0;
    integer unknown_pcm=0,unknown_i2s=0;
    always @(posedge clk)if(rst_n)begin
        cycles=cycles+1;
        if((^{dut.dac_din,dut.dac_ws,dut.dac_bck})===1'bx)begin
            unknown_i2s=unknown_i2s+1;
            if(cycles>4096)$fatal(1,"unknown I2S after warmup at %0d",cycles);
        end else i2s_hash={i2s_hash[26:0],i2s_hash[31:27]}^{29'd0,dut.dac_din,dut.dac_ws,dut.dac_bck};
        if(pcm_valid)begin
            if(last_sample>=0&&cycles-last_sample!=512)$fatal(1,"PCM cadence");
            last_sample=cycles;samples=samples+1;if(pcm!=0)nonzero=nonzero+1;
            if((^pcm)===1'bx)begin unknown_pcm=unknown_pcm+1;if(cycles>4096)$fatal(1,"unknown PCM after warmup at %0d",cycles);end
            else pcm_hash={pcm_hash[26:0],pcm_hash[31:27]}^{8'd0,pcm};
        end
        if(dut.child_valid&&dut.child_ready)begin if(dut.child_on)ons=ons+1;else offs=offs+1;end
        if(cfg_applied)applies=applies+1;
        if(cfg_error)errors=errors+1;
        if(frame_error||link_error||sensor_error||watchdog_error||layer_protocol_error)$fatal(1,"unexpected control fault");
    end
    task config_op;
        input commit;input [1:0] slot;input [3:0] part;input [47:0] word;
        begin
            @(negedge clk);while(!cfg_ready)@(negedge clk);
            cfg_valid=1;cfg_commit=commit;cfg_slot=slot;cfg_part=part;cfg_word=word;
            @(negedge clk);cfg_valid=0;@(negedge clk);
        end
    endtask
    task load_slot;
        input [1:0] slot;input [7:0] amplitude;input [15:0] sustain;
        reg [15:0] ratio;reg [7:0] amp;
        begin
            for(i=0;i<16;i=i+1)begin
                ratio=(i+1)*256;amp=i==0?amplitude:i*3;
                config_op(0,slot,i[3:0],{ratio,amp,1'b0,sustain,2'd3,5'd0});
            end
            config_op(1,slot,0,0);
        end
    endtask
    task report;
        input [3:0] ct;
        begin
            @(negedge clk);while(!left_ready)@(negedge clk);left_valid=1;contact=ct;
            @(negedge clk);left_valid=0;seq=seq+1;
            while(!left_ready)@(negedge clk);
            repeat(4)@(negedge clk);
        end
    endtask
    task legacy;
        input onoff;input [6:0] note;
        begin @(negedge clk);ev_valid=1;ev_on=onoff;ev_note=note;@(negedge clk);ev_valid=0;repeat(100)@(negedge clk);end
    endtask
    initial begin
        repeat(4)@(negedge clk);rst_n=1;repeat(4096)@(negedge clk);
        config_op(1,0,0,0); // incomplete must reject
        config_op(0,0,0,48'h000000800000); // reserved bit must reject
        if(errors!=2||dut.core.u_nm.cfg_enabled!=0)$fatal(1,"invalid commit published");
        for(i=0;i<16;i=i+1)config_op(0,0,i[3:0],example_sustain[i]);config_op(1,0,0,0);
        for(i=0;i<16;i=i+1)config_op(0,1,i[3:0],example_strike[i]);config_op(1,1,0,0);
        if(applies!=2||dut.core.u_nm.cfg_enabled!=3)$fatal(1,"slot commit");
        report(3);
        a=dut.layers.groups0[0];b=dut.layers.groups1[0];c=dut.layers.groups0[1];d=dut.layers.groups1[1];
        if(a==b||a==c||b==d||bound!=3||ons!=4)$fatal(1,"independent dual layer same MIDI");
        repeat(512*320)@(negedge clk);
        if(dut.core.u_tdm.env_mem[a*16]!=24576||dut.core.u_tdm.env_mem[b*16]!=0||!dut.core.nm_active[b])$fatal(1,"sustain / strike decay while held");
        if(dut.core.u_tdm.amp_mem[a*16]!=135||dut.core.u_tdm.amp_mem[b*16]!=67)$fatal(1,"independent custom spectrum");
        for(i=1;i<16;i=i+1)begin
            if(dut.core.u_tdm.amp_mem[a*16+i]!=(i*3*192)/256||dut.core.u_tdm.inc_mem[a*16+i]!=(i+1)*dut.core.u_nm.note_rom[60])$fatal(1,"custom table read pipeline partial %0d",i);
        end
        if(dut.core.finger_active[a]!=1||dut.core.finger_active[b]!=1)$fatal(1,"multibind missing");
        oldtag=dut.core.u_nm.group_start_tag[a];position[8:0]=192;report(3);
        if(dut.core.finger_offsets[a*18+:18]==0||dut.core.finger_offsets[a*18+:18]!=dut.core.finger_offsets[b*18+:18]||dut.core.finger_offsets[c*18+:18]!=0||ons!=4||dut.core.u_nm.group_start_tag[a]!=oldtag)$fatal(1,"layer slide retrigger / other finger");
        load_slot(0,80,16000);load_slot(0,40,10000);repeat(1024)@(negedge clk);
        if(dut.core.u_tdm.amp_mem[a*16]!=135||dut.core.u_tdm.epar_mem[a*16][22:7]!=24576)$fatal(1,"commit changed held voice");
        // Release uses the original selection, even after selection changes.
        selection=4'b1000;report(2);repeat(1024)@(negedge clk);
        if(dut.core.nm_active[a]||dut.core.nm_active[b]||!dut.core.nm_active[c]||!dut.core.nm_active[d]||offs!=2)$fatal(1,"captured selection release");
        if(dut.core.u_tdm.epar_mem[a*16][22:7]!=24576||dut.core.u_tdm.amp_mem[a*16]!=135)$fatal(1,"release replaced old timbre");
        selection=1;position[8:0]=128;report(3);a=dut.layers.groups0[0];repeat(1024)@(negedge clk);
        if(dut.core.u_tdm.amp_mem[a*16]!=30||dut.core.u_tdm.epar_mem[a*16][22:7]!=10000||ons!=5)$fatal(1,"next note ignored commit");
        report(0);
        // Fill 32 groups then steal one child with legacy traffic.
        selection=3;report(1);a=dut.layers.groups0[0];b=dut.layers.groups1[0];
        for(i=40;i<70;i=i+1)legacy(1,i[6:0]);
        if(dut.core.nm_active!=32'hffffffff)$fatal(1,"32 voice fill");
        legacy(1,90);position[8:0]=220;report(1);
        if(dut.core.u_nm.gtab[a]!=90||dut.core.finger_active[a]||dut.core.finger_offsets[b*18+:18]==0)$fatal(1,"stolen layer movement escaped identity");
        report(0);repeat(1024)@(negedge clk);
        if(!dut.core.nm_active[a]||dut.core.nm_active[b]||dut.core.u_nm.gtab[a]!=90)$fatal(1,"stale child release killed replacement");
        for(i=40;i<70;i=i+1)legacy(0,i[6:0]);legacy(0,90);
        if(dut.core.nm_active||bound)$fatal(1,"hanging notes");
        load_slot(2,120,18000);load_slot(3,60,12000);selection=12;report(4);
        a=dut.layers.groups0[2];b=dut.layers.groups1[2];repeat(1024)@(negedge clk);
        if(dut.layers.slots0[2]!=2||dut.layers.slots1[2]!=3||dut.core.u_tdm.amp_mem[a*16]!=90||dut.core.u_tdm.amp_mem[b*16]!=45)$fatal(1,"upper slots did not remain independent");
        report(0);
        // Invalid masks must reject without allocating or silently truncating.
        selection=15;oldamp=ons;report(1);if(ons!=oldamp||!blocked[0]||!layer_selection_error)$fatal(1,"unsupported mask accepted");report(0);
        if(nonzero<200||dut.core.pinq_ovf||dut.core.ev_q_ovf)$fatal(1,"audio/event evidence");
        $display("PASS layers cycles=%0d samples=%0d nonzero=%0d child_on=%0d child_off=%0d commits=%0d rejected_cfg=%0d pcm_hash=%08x i2s_hash=%08x startup_unknown_pcm=%0d startup_unknown_i2s_clocks=%0d independent_timbre sustain_strike slide snapshot release steal invalid_mask four_slots",cycles,samples,nonzero,ons,offs,applies,errors,pcm_hash,i2s_hash,unknown_pcm,unknown_i2s);$finish;
    end
    initial begin #40000000;$fatal(1,"watchdog");end

    integer trace_fd,trace_cycle=0;
    reg [2047:0] trace_path;
    initial begin
        if(!$value$plusargs("trace=%s",trace_path))$fatal(1,"trace path missing");
        trace_fd=$fopen(trace_path,"w");if(!trace_fd)$fatal(1,"trace open");
    end
    always @(posedge clk)begin
        trace_cycle=trace_cycle+1;
        $fdisplay(trace_fd,"%0d %b %b %b %b %h %b %b %h %h %b %b %h %b %h %h",trace_cycle,
            dut.core.dac_din,dut.core.dac_ws,dut.core.dac_bck,dut.core.monitor_valid,
            dut.core.monitor_valid?dut.core.monitor_pcm:24'd0,dut.core.voice_valid,dut.core.voice_on,
            dut.core.voice_group,dut.core.voice_note,dut.core.own_ready,dut.core.result_valid,
            dut.core.result_valid?dut.core.result_instance:15'd0,dut.core.finger_valid,
            dut.core.finger_active,dut.core.finger_offsets);
    end
initial begin
repeat(4000) @(negedge clk);
if(dut.core.r_vel_sens !== 8'h80 || dut.core.vel_vscale !== 9'd256) $fatal(1,"PROFILE native defaults");
$display("PROFILE historical native_defaults_checked");
force dut.core.vel_vscale = 9'd0;
end
endmodule
