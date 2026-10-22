`timescale 1ns/1ps
module tb_music;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,ev_valid=0,ev_on=0;reg[6:0]ev_note=60;reg[3:0]ev_vel=8;
    reg touch_valid=0,restore_valid=0;reg[4:0]touch_active=0;reg[49:0]touch_x=0,touch_y=0;reg[19:0]touch_id=0;
    reg[9:0]radius=50,slew_step=16;reg[47:0]part_to_control=0;reg[31:0]voice_mask=32'hffffffff;
    tri[15:0]pad,pad_ref;
    genvar g;generate for(g=0;g<16;g=g+1)begin: idle_pad
        pulldown(pad[g]);pulldown(pad_ref[g]);
    end endgenerate
    wire touch_ready,touch_done,gain_done,control_error,pcm_valid;
    wire[79:0]fader_y;wire[159:0]gains;wire signed[23:0]pcm;
    wire uart_tx_pin,dac_din,dac_ws,dac_bck,pa_en,voice_valid,voice_on;
    wire[5:0]led;wire[4:0]voice_group;wire[6:0]voice_note;
    wire tx_ref,di_ref,ws_ref,bck_ref,pa_ref,vv_ref,vo_ref;wire[5:0]led_ref;wire[4:0]vg_ref;wire[6:0]vn_ref;
    compat_music_probe dut(.clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.uart_tx_pin(uart_tx_pin),
        .ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.preset(2'd0),
        .finger_valid(1'b0),.finger_cmd(2'd0),.finger_id(5'd0),.finger_group(5'd0),.finger_position(12'sd0),.pad(pad),
        .touch_valid(touch_valid),.touch_ready(touch_ready),.touch_active(touch_active),.touch_x(touch_x),.touch_y(touch_y),.touch_id(touch_id),
        .radius(radius),.slew_step(slew_step),.part_to_control(part_to_control),.restore_valid(restore_valid),.voice_mask(voice_mask),
        .fader_y(fader_y),.gains(gains),.touch_done(touch_done),.gain_done(gain_done),.control_error(control_error),
        .led(led),.dac_din(dac_din),.dac_ws(dac_ws),.dac_bck(dac_bck),.pa_en(pa_en),
        .voice_valid(voice_valid),.voice_on(voice_on),.voice_group(voice_group),.voice_note(voice_note),.pcm_valid(pcm_valid),.pcm(pcm));
    tdm_top #(.FINGER_EXPR(1),.BOARD_DIAG(0),.LIVE_MONITOR(0)) ref_top(
        .clk(clk),.rst_n(rst_n),.uart_rx_pin(1'b1),.uart_tx_pin(tx_ref),.test_mode(1'b0),.preset(2'd0),
        .ev_valid(ev_valid),.ev_on(ev_on),.ev_note(ev_note),.ev_vel(ev_vel),.pad(pad_ref),.led(led_ref),
        .finger_valid(1'b0),.finger_cmd(2'd0),.finger_id(5'd0),.finger_group(5'd0),.finger_position(12'sd0),
        .dac_din(di_ref),.dac_ws(ws_ref),.dac_bck(bck_ref),.pa_en(pa_ref),
        .voice_valid(vv_ref),.voice_on(vo_ref),.voice_group(vg_ref),.voice_note(vn_ref));
    integer cycles=0,samples=0,events=0,differences=0,tail_differences=0,i,n;
    reg exact=1,check_tail=0;
    always @(negedge clk)if(rst_n)begin
        cycles=cycles+1;
        if(cycles>2000)begin
            if(control_error)$fatal(1,"control fault in full music path");
            if(exact&&dac_din!==di_ref)$fatal(1,"bypass/restore I2S data identity");
            if({uart_tx_pin,dac_ws,dac_bck,pa_en,led,voice_valid,voice_on,voice_group,voice_note}!==
               {tx_ref,ws_ref,bck_ref,pa_ref,led_ref,vv_ref,vo_ref,vg_ref,vn_ref})$fatal(1,"clock/event identity changed");
            if({dut.core.u_tdm.ph1,dut.core.u_tdm.inc1,dut.core.u_tdm.env1,dut.core.u_tdm.stg1,dut.core.u_tdm.amp1,dut.core.u_tdm.epar1}!==
               {ref_top.u_tdm.ph1,ref_top.u_tdm.inc1,ref_top.u_tdm.env1,ref_top.u_tdm.stg1,ref_top.u_tdm.amp1,ref_top.u_tdm.epar1})$fatal(1,"timbre rewrote live note state");
            if(voice_valid)events=events+1;
            if(pcm_valid)begin
                samples=samples+1;
                if(pcm!==ref_top.audio)begin differences=differences+1;if(check_tail)tail_differences=tail_differences+1;end
                if(exact&&pcm!==ref_top.audio)$fatal(1,"bypass/restore PCM identity");
            end
        end
    end
    task note;
        input onoff;input[6:0]number;input[3:0]velocity;
        begin @(negedge clk);ev_valid=1;ev_on=onoff;ev_note=number;ev_vel=velocity;
            @(negedge clk);ev_valid=0;repeat(160)@(negedge clk);end
    endtask
    task report;
        begin
            @(negedge clk);while(!touch_ready)@(negedge clk);
            touch_valid=1;@(negedge clk);touch_valid=0;n=0;
            while(!touch_done)begin @(negedge clk);n=n+1;if(n>120)$fatal(1,"music touch stalled");end
            @(negedge clk);
        end
    endtask
    initial begin
        for(i=0;i<16;i=i+1)part_to_control[i*3+:3]=i/2;
        repeat(5)@(negedge clk);rst_n=1;repeat(4096)@(negedge clk);
        note(1,60,8);note(1,64,10);note(1,67,12);
        repeat(512*120)@(negedge clk);
        exact=0;touch_active=1;touch_x[9:0]=50;touch_y[9:0]=52;touch_id[3:0]=2;report;
        repeat(512*80)@(negedge clk);
        if(gains[9:0]!=512||gains[19:10]!=512)$fatal(1,"fader gain did not reach engine target");
        touch_active=0;report;repeat(512*10)@(negedge clk);
        if(gains[9:0]!=512)$fatal(1,"release did not latch audio modifier");
        // Old note_map marks groups inactive on release; read-side timbre still
        // processes the audible tail without a gact-based refresh operation.
        note(0,60,0);note(0,64,0);note(0,67,0);
        repeat(512*3)@(negedge clk);
        if(dut.core.nm_active!=0)$fatal(1,"chord not released");
        check_tail=1;repeat(512*40)@(negedge clk);check_tail=0;
        note(1,72,6);repeat(512*30)@(negedge clk);
        @(negedge clk);restore_valid=1;@(negedge clk);restore_valid=0;
        if(gains[9:0]!=512)$fatal(1,"restore jumped instead of slew");
        repeat(512*24)@(negedge clk);
        if(gains!=={16{10'd256}})$fatal(1,"restored gain not exactly unity");
        exact=1;repeat(512*30)@(negedge clk);note(0,72,0);
        repeat(512*30)@(negedge clk);
        if(events!=8||differences<100||tail_differences<10)$fatal(1,"insufficient real music activity events%0d diff%0d tail%0d",events,differences,tail_differences);
        $display("PASS music cycles=%0d samples=%0d events=%0d changed_pcm=%0d released_tail_pcm=%0d fader_to_sound restore_exact state_preserved",cycles,samples,events,differences,tail_differences);$finish;
    end
    initial begin #20000000;$fatal(1,"music watchdog");end

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
endmodule
