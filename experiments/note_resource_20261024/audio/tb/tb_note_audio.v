`timescale 1ns/1ps
module tb_note_audio;
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
    wire part_ready=clocks%7!=0;
    reg part_rsp_valid=0;
    reg [7:0] part_rsp_ticket=0;
    reg [31:0] part_rsp_token=0;
    reg [1:0] part_rsp_layer=0;
    reg [3:0] part_rsp_index=0;
    reg provider_busy=0,wrong_sent=0;
    integer provider_delay=0;
    reg [7:0] pending_ticket;
    reg [31:0] pending_token;
    reg [1:0] pending_layer;
    reg [3:0] pending_part;
    reg [6:0] held_note=60;
    reg [3:0] held_velocity=10;
    reg slow_release=0;
    reg [23:0] notes[0:127];
    reg [47:0] partials[0:63];
    wire [47:0] partial_word=partials[{pending_layer,pending_part}];
    wire [39:0] frequency_product=notes[held_note]*partial_word[47:32];
    wire [23:0] part_inc=frequency_product[31:8];
    wire [7:0] part_amp;
    wire [22:0] part_epar={16'd20000,2'd3,5'd12};
    wire [39:0] part_env={4'd0,1'b1,4'd0,16'd4096,4'd0,4'd0,2'd3,(slow_release?5'd13:5'd3)};
    wire signed [17:0] part_gq=0;
    wire [57:0] pmod_cfg=0;
    wire [159:0] timbre_gain_q8={16{10'd256}};
    wire [31:0] timbre_voice_mask=0,finger_active=0;
    wire [575:0] finger_offsets=0;
    wire [15:0] d2_lvl=0;
    wire [4:0] d2_k=0;
    vel_shape shape(.vel(held_velocity),.slot(pending_layer),.part(pending_part),.base(partial_word[31:24]),
        .tilt_bias(10'sd0),.tilt_gain(8'd128),.vscale(9'd256),.amp(part_amp));
    note_resource_audio_probe dut(.*);
    always @(posedge clk)begin
        clocks<=clocks+1;
        if(!rst_n)begin provider_busy<=0;part_rsp_valid<=0;end
        else begin
            if(req_valid&&req_ready&&req_kind==0)begin
                held_note<=60+req_token[2:0];held_velocity<=req_token[3:0]==0?4'd8:req_token[3:0];
            end
            if(part_valid&&part_ready)begin
                if(provider_busy)$fatal(1,"multiple partial requests");
                provider_busy<=1;provider_delay<=3+clocks%11;wrong_sent<=0;
                pending_ticket<=part_ticket;pending_token<=part_token;pending_layer<=part_layer;pending_part<=part_index;
            end
            if(part_rsp_valid&&part_rsp_ready)begin
                part_rsp_valid<=0;
                if(part_rsp_token==pending_token)provider_busy<=0;
            end
            if(provider_busy&&!part_rsp_valid)begin
                if(provider_delay>0)provider_delay<=provider_delay-1;
                else begin
                    part_rsp_valid<=1;part_rsp_ticket<=pending_ticket;
                    part_rsp_layer<=pending_layer;part_rsp_index<=pending_part;
                    if(pending_part==0&&!wrong_sent)begin
                        part_rsp_token<=pending_token^32'h40000000;wrong_sent<=1;
                    end else part_rsp_token<=pending_token;
                end
            end
        end
    end
    integer check_slot,transaction_parts=0,transaction_frame=-1,audio_frame=0,publish_count=0,retire_count=0;
    reg [31:0] transaction_groups=0;
    reg transaction_open=0;
    reg [511:0] consumed_slots=0;
    always @(posedge clk)begin
        if(!rst_n)begin transaction_open=0;consumed_slots=0;transaction_parts=0;transaction_frame=-1;end
        else begin
            if(dut.engine.sc==1)audio_frame=audio_frame+1;
            if(dut.publish_valid&&dut.publish_ready)begin
                if(transaction_open)$fatal(1,"overlapping publication");
                transaction_open=1;transaction_groups=dut.publish_groups;
                consumed_slots=0;transaction_parts=0;transaction_frame=-1;
            end
            if(dut.engine.consume)begin
                if(!transaction_open||!transaction_groups[dut.engine.sl1/16])$fatal(1,"unpublished partial consumed");
                if(transaction_frame<0)transaction_frame=audio_frame;
                if(transaction_frame!=audio_frame)$fatal(1,"non-atomic publish");
                if(consumed_slots[dut.engine.sl1])$fatal(1,"partial consumed twice");
                consumed_slots[dut.engine.sl1]=1;transaction_parts=transaction_parts+1;
            end
            if(dut.backend.response_fire&&dut.backend.part_rsp_token!=dut.backend.token_hold)
                $fatal(1,"stale partial response consumed");
            if(dut.finish_valid&&dut.finish_ready)begin
                for(check_slot=0;check_slot<512;check_slot=check_slot+1)
                    if(dut.finish_groups[check_slot/16]&&
                       (dut.engine.env_mem[check_slot]!==0||dut.engine.stg_mem[check_slot]!==0||
                        dut.engine.gcur_mem[check_slot]!==0||dut.engine.pv_mem[check_slot]!==0))
                        $fatal(1,"false natural completion");
            end
            if(dut.publish_done)begin
                if(!transaction_open)$fatal(1,"publication completion without transaction");
                for(check_slot=0;check_slot<512;check_slot=check_slot+1)
                    if(consumed_slots[check_slot]!==transaction_groups[check_slot/16])$fatal(1,"publication missing layer/partial");
                transaction_open=0;publish_count=publish_count+1;
            end
            if(dut.done_valid&&dut.done_ready&&dut.backend.kind_hold==1)begin
                retire_count=retire_count+1;
                for(check_slot=0;check_slot<512;check_slot=check_slot+1)
                    if(dut.backend.groups_hold[check_slot/16]&&
                       (dut.engine.env_mem[check_slot]!==0||dut.engine.stg_mem[check_slot]!==0||
                        dut.engine.gcur_mem[check_slot]!==0||dut.engine.amp_mem[check_slot]!==0||dut.engine.pv_mem[check_slot]!==0))
                        $fatal(1,"retirement acknowledged before silence");
            end
        end
    end
    always @(negedge clk)begin
        if(!boot_ready&&pcm!==0)$fatal(1,"reset/boot unmuted");
        if(rst_n&&boot_ready&&dut.engine.sc==5)begin
            if(^pcm===1'bx)$fatal(1,"unknown PCM");
            frames=frames+1;if(pcm!=0)pcm_nonzero=pcm_nonzero+1;
            $fdisplay(trace_fd,"P %0d %0d %08h %08h %0d",frames,$signed(pcm),active_groups,reserved_groups,active_count);
        end
    end
    integer cancel_mode=0;
    always @(negedge clk)begin
        cancel_valid=0;
        if(cancel_mode==1&&dut.backend.state==6)begin
            cancel_valid=1;cancel_token=req_token;cancel_mode=0;
        end else if(cancel_mode==2&&dut.backend.state==9&&dut.backend.kind_hold==3)begin
            cancel_valid=1;cancel_token=req_token;cancel_mode=0;
        end else if(cancel_mode==3&&rsp_valid&&rsp_code==0)begin
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
        $readmemh("note_inc.hex",notes);$readmemh("preset_part.hex",partials);
        repeat(8)@(negedge clk);rst_n=1;
        wait(boot_ready);wait_frames(4);if(pcm_nonzero!=0)$fatal(1,"boot ghost note");
        request(0,1,15,0);if(active_count!=1||active_groups!=15)$fatal(1,"four layer admission");
        baseline_nonzero=pcm_nonzero;wait_frames(30);if(pcm_nonzero-baseline_nonzero<15)$fatal(1,"missing real PCM");
        request(0,32'h80000001,5,0);if(active_count!=2)$fatal(1,"source identities merged");
        request(1,32'h00123001,0,3);
        request(1,1,0,1);if((active_groups&15)!=15)$fatal(1,"OFF freed live tail");
        wait_count(1);if((active_groups&15)!=0)$fatal(1,"finished groups retained");
        request(1,32'h80000001,0,1);wait_count(0);wait_frames(6);if(pcm!=0)$fatal(1,"tail failed to end");
        slow_release=1;
        for(note_number=10;note_number<18;note_number=note_number+1)begin
            token_number=note_number|((note_number%2)?32'h80000000:0);
            request(0,token_number,15,0);
        end
        if(active_groups!=32'hffffffff||active_count!=8)$fatal(1,"pool was not full");
        request(1,32'h80000011,0,1);young_groups=last_groups;
        request(0,18,15,0);if(last_groups!=young_groups||!dut.manager.entries_valid[dut.manager.order[0]])$fatal(1,"released tail priority");
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
        slow_release=0;request(0,1,1,0);anchor_group=rsp_map[4:0];
        for(note_number=2;note_number<264;note_number=note_number+1)begin
            request(0,note_number,1,0);request(1,note_number,0,1);wait_count(1);
            if(!active_groups[anchor_group])$fatal(1,"anchor lost across reuse");
        end
        request(1,1,0,1);wait_count(0);wait_frames(6);
        if(pcm!=0||active_groups!=0||reserved_groups!=0||dut.backend.owned_groups!=0)$fatal(1,"final resource leak");
        if(!protocol_error)$fatal(1,"wrong provider token not reported");
        $display("PASS real_audio requests=%0d frames=%0d nonzero_pcm=%0d publishes=%0d retires=%0d max_request_cycles=%0d",requests,frames,pcm_nonzero,publish_count,retire_count,max_latency);
        $fclose(trace_fd);$finish;
    end
    initial begin #2000000000;$fatal(1,"global timeout");end
endmodule
