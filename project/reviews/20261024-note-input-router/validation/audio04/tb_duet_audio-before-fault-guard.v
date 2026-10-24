`timescale 1ns/1ps
module tb_duet_audio;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0;
    reg [8:0] frame_clock=0;
    wire sample_en=frame_clock==511;
    always @(posedge clk)if(!rst_n)frame_clock<=0;else frame_clock<=frame_clock+1'b1;
    reg req_valid=0,cancel_valid=0,rsp_ready=1;
    reg [1:0] req_kind=0;
    reg [31:0] req_token=0,cancel_token=0;
    reg [3:0] req_layers=0;
    wire req_ready,rsp_valid,boot_ready,protocol_error;
    wire [2:0] rsp_code;
    wire [31:0] rsp_token,rsp_groups,active_groups,reserved_groups;
    wire [3:0] rsp_layers;
    wire [19:0] rsp_map;
    wire [5:0] active_count;
    wire signed [23:0] pcm;
    wire part_valid,part_rsp_ready;
    wire [7:0] part_ticket;
    wire [31:0] part_token;
    wire [1:0] part_layer;
    wire [3:0] part_index;
    integer clocks=0,frames=0,pcm_nonzero=0,max_latency=0,requests=0,trace_fd;
    reg [2047:0] trace_path;

    reg slow_release=0;
    reg cfg_valid=0,cfg_commit=0;
    reg [1:0] cfg_slot=0;
    reg [3:0] cfg_part=0;
    reg [87:0] cfg_word=0;
    wire cfg_ready,cfg_applied,cfg_error;
    wire [3:0] cfg_enabled_status;
    reg [47:0] definitions[0:63];
    wire [6:0] ev_note=7'd60+{4'd0,req_token[2:0]};
    wire [7:0] ev_velocity=8'd200;
    wire [57:0] pmod_cfg=0;
    wire [159:0] timbre_gain_q8={16{10'd256}};
    wire [31:0] timbre_voice_mask=0,finger_active=0;
    wire [575:0] finger_offsets=0;
    wire [15:0] d2_lvl=0;
    wire [4:0] d2_k=0;
    wire context_active;
    always @(posedge clk)clocks<=clocks+1;
    wire live_ready,score_ready,live_response_valid,score_response_valid;
    assign req_ready=req_token[31]?score_ready:live_ready;
    assign rsp_valid=live_response_valid||score_response_valid;
    note_duet_probe dut(
        .live_valid(req_valid&&!req_token[31]),.live_on(req_kind==0),.live_ready(live_ready),.live_serial(req_token[30:0]),.live_note(ev_note),.live_velocity(ev_velocity),.live_glide(18'sd0),.live_layers(req_layers),.live_response_valid(live_response_valid),.live_response_ready(rsp_ready),.score_valid(req_valid&&req_token[31]),.score_on(req_kind==0),.score_ready(score_ready),.score_serial(req_token[30:0]),.score_note(ev_note),.score_velocity(ev_velocity),.score_glide(18'sd0),.score_layers(req_layers),.score_response_valid(score_response_valid),.score_response_ready(rsp_ready),.routed_token(rsp_token),.routed_groups(rsp_groups),.routed_code(rsp_code),.routed_layers(rsp_layers),.routed_map(rsp_map),
        .clk(clk),.rst_n(rst_n),.sample_en(sample_en),
        
        .cancel_valid(cancel_valid),.cancel_token(cancel_token),
        
        .cfg_valid(cfg_valid),.cfg_commit(cfg_commit),
        .cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),
        .cfg_error(cfg_error),.cfg_enabled_status(cfg_enabled_status),.spec_we(1'b0),.spec_commit(1'b0),
        .spec_addr(4'd0),.spec_wdata(8'd0),.spec_replace(1'b0),.pad_mask(16'd0),.tilt(8'h70),
        .tilt_vbias(10'sd0),.tilt_vgain(8'd128),.vel_vscale(9'd256),.artic_enable(1'b0),.artic_mask(16'd0),
        .strike_d_m(2'd3),.strike_d_k_base(5'd12),.strike_d_k_curve(4'd0),.strike_s_lvl(4'd0),
        .pmod_cfg(pmod_cfg),.timbre_gain_q8(timbre_gain_q8),.timbre_voice_mask(timbre_voice_mask),
        .finger_active(finger_active),.finger_offsets(finger_offsets),.d2_lvl(d2_lvl),.d2_k(d2_k),
        .pcm(pcm),.active_groups(active_groups),.reserved_groups(reserved_groups),.active_count(active_count),
        .boot_ready(boot_ready),.protocol_error(protocol_error),.context_active(context_active));
    task configure_slots;
        input slow;
        integer layer_number,partial_number;
        reg [39:0] envelope;
        begin
            envelope={4'd0,1'b1,4'd0,16'd4096,4'd0,4'd0,2'd3,(slow?5'd13:5'd3)};
            for(layer_number=0;layer_number<4;layer_number=layer_number+1)begin
                for(partial_number=0;partial_number<16;partial_number=partial_number+1)begin
                    @(negedge clk);cfg_slot=layer_number;cfg_part=partial_number;cfg_commit=0;cfg_valid=1;
                    cfg_word={envelope,definitions[layer_number*16+partial_number][47:24],1'b0,16'd20000,2'd3,5'd12};
                    #1;if(!cfg_ready)$fatal(1,"renderer cfg blocked while idle");
                    @(negedge clk);cfg_valid=0;if(cfg_error)$fatal(1,"renderer config rejected");
                end
                @(negedge clk);cfg_commit=1;cfg_valid=1;
                @(negedge clk);cfg_valid=0;cfg_commit=0;if(!cfg_applied)$fatal(1,"renderer config not applied");
            end
        end
    endtask
    always @(posedge clk)begin
        if(rst_n&&req_valid&&req_ready&&req_kind==0)
            $fdisplay(trace_fd,"N %08h %0d %0d %0d",req_token,ev_note,ev_velocity,slow_release);
        if(rst_n&&dut.core.core.backend.response_fire)
            $fdisplay(trace_fd,"L %08h %01h %01h %06h %02h %06h %010h %05h",dut.core.core.part_rsp_token,
                dut.core.core.part_rsp_layer,dut.core.core.part_rsp_index,dut.core.core.part_inc,dut.core.core.part_amp,
                dut.core.core.part_epar,dut.core.core.part_env,dut.core.core.part_gq);
    end
    integer check_slot,transaction_parts=0,transaction_frame=-1,audio_frame=0,publish_count=0,retire_count=0;
    reg [31:0] transaction_groups=0;
    reg transaction_open=0;
    reg [511:0] consumed_slots=0;
    always @(posedge clk)begin
        if(!rst_n)begin transaction_open=0;consumed_slots=0;transaction_parts=0;transaction_frame=-1;end
        else begin
            if(dut.core.core.engine.sc==1)audio_frame=audio_frame+1;
            if(dut.core.core.publish_valid&&dut.core.core.publish_ready)begin
                if(transaction_open)$fatal(1,"overlapping publication");
                transaction_open=1;transaction_groups=dut.core.core.publish_groups;
                consumed_slots=0;transaction_parts=0;transaction_frame=-1;
            end
            if(dut.core.core.engine.consume)begin
                if(!transaction_open||!transaction_groups[dut.core.core.engine.sl1/16])$fatal(1,"unpublished partial consumed");
                if(transaction_frame<0)transaction_frame=audio_frame;
                if(transaction_frame!=audio_frame)$fatal(1,"non-atomic publish");
                if(consumed_slots[dut.core.core.engine.sl1])$fatal(1,"partial consumed twice");
                consumed_slots[dut.core.core.engine.sl1]=1;transaction_parts=transaction_parts+1;
            end
            if(dut.core.core.backend.response_fire&&dut.core.core.backend.part_rsp_token!=dut.core.core.backend.token_hold)
                $fatal(1,"stale partial response consumed");
            if(dut.core.core.finish_valid&&dut.core.core.finish_ready)begin
                for(check_slot=0;check_slot<512;check_slot=check_slot+1)
                    if(dut.core.core.finish_groups[check_slot/16]&&
                       (dut.core.core.engine.env_mem[check_slot]!==0||dut.core.core.engine.stg_mem[check_slot]!==0||
                        dut.core.core.engine.gcur_mem[check_slot]!==0||dut.core.core.engine.pv_mem[check_slot]!==0))
                        $fatal(1,"false natural completion");
            end
            if(dut.core.core.publish_done)begin
                if(!transaction_open)$fatal(1,"publication completion without transaction");
                for(check_slot=0;check_slot<512;check_slot=check_slot+1)
                    if(consumed_slots[check_slot]!==transaction_groups[check_slot/16])$fatal(1,"publication missing layer/partial");
                transaction_open=0;publish_count=publish_count+1;
            end
            if(dut.core.core.done_valid&&dut.core.core.done_ready&&dut.core.core.backend.kind_hold==1)begin
                retire_count=retire_count+1;
                for(check_slot=0;check_slot<512;check_slot=check_slot+1)
                    if(dut.core.core.backend.groups_hold[check_slot/16]&&
                       (dut.core.core.engine.env_mem[check_slot]!==0||dut.core.core.engine.stg_mem[check_slot]!==0||
                        dut.core.core.engine.gcur_mem[check_slot]!==0||dut.core.core.engine.amp_mem[check_slot]!==0||dut.core.core.engine.pv_mem[check_slot]!==0))
                        $fatal(1,"retirement acknowledged before silence");
            end
        end
    end
    always @(negedge clk)begin
        if(!boot_ready&&pcm!==0)$fatal(1,"reset/boot unmuted");
        if(rst_n&&boot_ready&&dut.core.core.engine.sc==5)begin
            if(^pcm===1'bx)$fatal(1,"unknown PCM");
            frames=frames+1;if(pcm!=0)pcm_nonzero=pcm_nonzero+1;
            $fdisplay(trace_fd,"P %0d %0d %08h %08h %0d",frames,$signed(pcm),active_groups,reserved_groups,active_count);
        end
    end
    integer cancel_mode=0;
    always @(negedge clk)begin
        cancel_valid=0;
        if(cancel_mode==1&&dut.core.core.backend.state==6)begin
            cancel_valid=1;cancel_token=req_token;cancel_mode=0;
        end else if(cancel_mode==2&&dut.core.core.backend.state==9&&dut.core.core.backend.kind_hold==3)begin
            cancel_valid=1;cancel_token=req_token;cancel_mode=0;
        end else if(cancel_mode==3&&rsp_valid&&rsp_code==0)begin
            cancel_valid=1;cancel_token=req_token;cancel_mode=0;
        end else if(cancel_mode==4&&dut.router.event_valid&&!dut.router.event_ready)begin
            cancel_valid=1;cancel_token=req_token;cancel_mode=0;
        end
    end
    reg [31:0] last_groups;
    task request;
        input [1:0] kind;
        input [31:0] token;
        input [3:0] layers;
        input [2:0] expected;
        integer started,timeout_count;
        begin
            @(negedge clk);req_valid=1;req_kind=kind;req_token=token;req_layers=layers;
            #1;
            timeout_count=0;
            while(!req_ready)begin @(negedge clk);timeout_count=timeout_count+1;if(timeout_count>20000)$fatal(1,"request ready timeout");end
            @(posedge clk);started=clocks;
            @(negedge clk);req_valid=0;timeout_count=0;
            while(!rsp_valid||(expected==6&&rsp_code!=6))begin @(negedge clk);timeout_count=timeout_count+1;if(timeout_count>20000)$fatal(1,"response timeout");end
            if(rsp_token!==token||rsp_code!==expected)$fatal(1,"unexpected response token=%h code=%d expected=%d",rsp_token,rsp_code,expected);
            last_groups=rsp_groups;requests=requests+1;
            if(clocks-started>max_latency)max_latency=clocks-started;
            $fdisplay(trace_fd,"R %0d %08h %0d %08h %0d",kind,token,rsp_code,rsp_groups,clocks-started);
            @(negedge clk);
        end
    endtask
    task wait_frames;
        input integer count;
        integer target;
        begin target=frames+count;while(frames<target)@(negedge clk);end
    endtask
    task wait_count;
        input integer count;
        integer timeout_count;
        begin
            timeout_count=0;
            while(active_count!=count||reserved_groups!=0)begin
                @(negedge clk);timeout_count=timeout_count+1;if(timeout_count>180000)$fatal(1,"natural completion timeout");
            end
        end
    endtask
    integer note_number,baseline_nonzero,anchor_group;
    reg [31:0] token_number,young_groups;
    initial begin
        if(!$value$plusargs("trace=%s",trace_path))$fatal(1,"missing trace");
        trace_fd=$fopen(trace_path,"w");
        $readmemh("preset_part.hex",definitions);
        repeat(8)@(negedge clk);rst_n=1;
        wait(boot_ready);configure_slots(0);wait_frames(4);if(pcm_nonzero!=0)$fatal(1,"boot ghost note");
        request(0,1,15,0);if(active_count!=1||active_groups!=15)$fatal(1,"four layer admission");
        baseline_nonzero=pcm_nonzero;wait_frames(30);if(pcm_nonzero-baseline_nonzero<15)$fatal(1,"missing real PCM");
        request(0,32'h80000001,5,0);if(active_count!=2)$fatal(1,"source identities merged");
        request(1,32'h00123001,0,3);
        request(1,1,0,1);if((active_groups&15)!=15)$fatal(1,"OFF freed live tail");
        wait_count(1);if((active_groups&15)!=0)$fatal(1,"finished groups retained");
        request(1,32'h80000001,0,1);wait_count(0);wait_frames(6);if(pcm!=0)$fatal(1,"tail failed to end");
        cfg_valid=1;cfg_commit=0;cancel_mode=4;
        fork
            begin request(0,2,15,6);end
            begin wait(cancel_valid);repeat(8)@(negedge clk);cfg_valid=0;end
        join
        if(active_count!=0||active_groups!=0||reserved_groups!=0)$fatal(1,"queued cancellation leaked resources");
        slow_release=1;configure_slots(1);
        for(note_number=10;note_number<18;note_number=note_number+1)begin
            token_number=note_number|((note_number%2)?32'h80000000:0);
            request(0,token_number,15,0);
        end
        if(active_groups!=32'hffffffff||active_count!=8)$fatal(1,"pool was not full");
        request(1,32'h80000011,0,1);young_groups=last_groups;
        request(0,18,15,0);if(last_groups!=young_groups||!dut.core.core.manager.entries_valid[dut.core.core.manager.order[0]])$fatal(1,"released tail priority");
        request(0,32'h80000012,15,0);if(last_groups!=15)$fatal(1,"oldest held priority");
        request(1,10,0,3);
        cancel_mode=1;request(0,19,15,6);
        cancel_mode=2;request(0,20,15,6);
        rsp_ready=0;cancel_mode=3;
        fork
            begin request(0,21,15,6);end
            begin wait(cancel_valid);repeat(8)@(negedge clk);rsp_ready=1;end
        join
        @(negedge clk);rst_n=0;repeat(8)@(negedge clk);rst_n=1;
        wait(boot_ready);wait_count(0);wait_frames(5);if(pcm!=0)$fatal(1,"reset ghost note");
        slow_release=0;configure_slots(0);request(0,1,1,0);anchor_group=rsp_map[4:0];
        for(note_number=2;note_number<264;note_number=note_number+1)begin
            request(0,note_number,1,0);request(1,note_number,0,1);wait_count(1);
            if(!active_groups[anchor_group])$fatal(1,"anchor lost across reuse");
        end
        request(1,1,0,1);wait_count(0);wait_frames(6);
        if(pcm!=0||active_groups!=0||reserved_groups!=0||dut.core.core.backend.owned_groups!=0)$fatal(1,"final resource leak");
        if(protocol_error)$fatal(1,"unexpected real renderer protocol error");
        $display("PASS rendered_audio requests=%0d frames=%0d nonzero_pcm=%0d publishes=%0d retires=%0d max_request_cycles=%0d",requests,frames,pcm_nonzero,publish_count,retire_count,max_latency);
        $fclose(trace_fd);$finish;
    end
    initial begin #2000000000;$fatal(1,"global timeout");end
endmodule
