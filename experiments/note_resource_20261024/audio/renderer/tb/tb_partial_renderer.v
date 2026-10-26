`timescale 1ns/1ps
module tb_partial_renderer;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,note_valid=0,note_finish=0;
    wire note_ready,context_active,protocol_error;
    reg [31:0] note_token=0;
    reg [6:0] note_number=0;
    reg [7:0] note_velocity=0;
    reg signed [17:0] note_glide=0;
    reg cfg_valid=0,cfg_commit=0;
    reg [1:0] cfg_slot=0;
    reg [3:0] cfg_part=0;
    reg [87:0] cfg_word=0;
    wire cfg_ready,cfg_applied,cfg_error;
    wire [3:0] cfg_enabled_status;
    reg spec_we=0,spec_commit=0,spec_replace=0;
    reg [3:0] spec_addr=0;
    reg [7:0] spec_wdata=0,tilt=0,tilt_vgain=0;
    reg signed [9:0] tilt_vbias=0;
    reg [15:0] pad_mask=0,artic_mask=0;
    reg [8:0] vel_vscale=0;
    reg artic_enable=0;
    reg [1:0] strike_d_m=0;
    reg [4:0] strike_d_k_base=0;
    reg [3:0] strike_d_k_curve=0,strike_s_lvl=0;
    reg part_valid=0,part_rsp_ready=0;
    wire part_ready,part_rsp_valid;
    reg [7:0] part_ticket=0;
    reg [31:0] part_token=0;
    reg [1:0] part_layer=0;
    reg [3:0] part_index=0;
    wire [7:0] part_rsp_ticket,part_amp;
    wire [31:0] part_rsp_token;
    wire [1:0] part_rsp_layer;
    wire [3:0] part_rsp_index;
    wire [23:0] part_inc;
    wire [22:0] part_epar;
    wire [39:0] part_env;
    wire signed [17:0] part_gq;
    note_partial_renderer dut(.*);
    integer commands,trace_fd,operation,fields,expected_commit,request_delay,response_delay,wait_cycles;
    integer query_count=0,context_count=0,commit_count=0,hold_index;
    reg [2047:0] command_path,trace_path;
    reg [158:0] held_response;
    task configuration;
        begin
            @(negedge clk);cfg_valid=1;note_valid=1;
            #1;
            if(!cfg_ready||note_ready)$fatal(1,"configuration priority deadlock");
            @(posedge clk);@(negedge clk);cfg_valid=0;note_valid=0;
            if(context_active)$fatal(1,"note bypassed configuration priority");
            if(cfg_commit)begin
                if(cfg_applied!==expected_commit||cfg_error===expected_commit)$fatal(1,"incomplete configuration publication");
                commit_count=commit_count+1;
            end else if(cfg_error)$fatal(1,"legal configuration rejected");
        end
    endtask
    initial begin
        if(!$value$plusargs("commands=%s",command_path)||!$value$plusargs("trace=%s",trace_path))$fatal(1,"missing paths");
        commands=$fopen(command_path,"r");trace_fd=$fopen(trace_path,"w");
        repeat(6)@(negedge clk);rst_n=1;
        while($fscanf(commands,"%d",operation)==1)begin
            case(operation)
                0:begin
                    fields=$fscanf(commands,"%d %d %h",cfg_slot,cfg_part,cfg_word);
                    if(fields!=3)$fatal(1,"bad configuration command");cfg_commit=0;configuration;
                end
                1:begin
                    fields=$fscanf(commands,"%d %d",cfg_slot,expected_commit);
                    if(fields!=2)$fatal(1,"bad commit command");cfg_commit=1;configuration;cfg_commit=0;
                end
                2:begin
                    fields=$fscanf(commands,"%d %d",spec_addr,spec_wdata);
                    if(fields!=2)$fatal(1,"bad spectrum command");
                    @(negedge clk);spec_we=1;@(negedge clk);spec_we=0;
                end
                3:begin
                    fields=$fscanf(commands,"%d %d",spec_addr,spec_wdata);
                    if(fields!=2)$fatal(1,"bad spectrum commit");
                    @(negedge clk);spec_we=1;spec_commit=1;@(negedge clk);spec_we=0;spec_commit=0;
                end
                4:begin
                    fields=$fscanf(commands,"%h %d %d %h %d %d %d %d %d %h %d %h %d %d %d %d",
                        note_token,note_number,note_velocity,note_glide,tilt,tilt_vbias,tilt_vgain,vel_vscale,
                        spec_replace,pad_mask,artic_enable,artic_mask,strike_d_m,strike_d_k_base,strike_d_k_curve,strike_s_lvl);
                    if(fields!=16)$fatal(1,"bad note context");
                    @(negedge clk);note_valid=1;
                    if(!note_ready)$fatal(1,"note context unexpectedly blocked");
                    @(negedge clk);note_valid=0;
                    if(!context_active||cfg_ready)$fatal(1,"context did not lock definition");
                    cfg_valid=1;cfg_commit=1;repeat(3)@(negedge clk);
                    if(cfg_ready||cfg_applied)$fatal(1,"configuration consumed during context");cfg_valid=0;cfg_commit=0;
                    tilt=~tilt;vel_vscale=~vel_vscale;note_velocity=~note_velocity;note_glide=~note_glide;
                    pad_mask=~pad_mask;spec_replace=!spec_replace;artic_enable=!artic_enable;artic_mask=~artic_mask;
                    strike_d_m=~strike_d_m;strike_d_k_base=~strike_d_k_base;strike_d_k_curve=~strike_d_k_curve;strike_s_lvl=~strike_s_lvl;
                    context_count=context_count+1;
                end
                5:begin
                    fields=$fscanf(commands,"%d %d %d %d",part_layer,part_index,request_delay,response_delay);
                    if(fields!=4)$fatal(1,"bad query");
                    repeat(request_delay)@(negedge clk);
                    part_token=note_token;part_ticket=query_count[7:0];part_valid=1;
                    #1;
                    wait_cycles=0;
                    while(!part_ready)begin @(negedge clk);wait_cycles=wait_cycles+1;if(wait_cycles>20)$fatal(1,"query backpressure timeout");end
                    @(posedge clk);@(negedge clk);part_valid=0;wait_cycles=0;
                    while(!part_rsp_valid)begin @(negedge clk);wait_cycles=wait_cycles+1;if(wait_cycles>20)$fatal(1,"partial response timeout");end
                    held_response={part_rsp_ticket,part_rsp_token,part_rsp_layer,part_rsp_index,part_inc,part_amp,part_epar,part_env,part_gq};
                    if(^held_response===1'bx)$fatal(1,"unknown partial payload");
                    for(hold_index=0;hold_index<response_delay;hold_index=hold_index+1)begin
                        @(negedge clk);
                        if(!part_rsp_valid||held_response!=={part_rsp_ticket,part_rsp_token,part_rsp_layer,part_rsp_index,part_inc,part_amp,part_epar,part_env,part_gq})
                            $fatal(1,"partial response unstable");
                    end
                    $fdisplay(trace_fd,"R %0d %08h %02h %01h %01h %06h %02h %06h %010h %05h",query_count,
                        part_rsp_token,part_rsp_ticket,part_rsp_layer,part_rsp_index,part_inc,part_amp,part_epar,part_env,part_gq);
                    part_rsp_ready=1;@(negedge clk);part_rsp_ready=0;query_count=query_count+1;
                end
                6:begin
                    @(negedge clk);note_finish=1;@(negedge clk);note_finish=0;
                    if(context_active)$fatal(1,"context not released");
                end
                7:begin
                    @(negedge clk);part_token=note_token^32'h40000000;part_valid=1;
                    repeat(3)begin @(negedge clk);if(part_ready||part_rsp_valid)$fatal(1,"stale query accepted");end
                    part_valid=0;if(!protocol_error)$fatal(1,"stale query not diagnosed");
                end
                default:$fatal(1,"unknown command");
            endcase
        end
        $display("PASS partial_renderer contexts=%0d queries=%0d commits=%0d",context_count,query_count,commit_count);
        $fclose(trace_fd);$finish;
    end
    initial begin #200000000;$fatal(1,"global timeout");end
endmodule
