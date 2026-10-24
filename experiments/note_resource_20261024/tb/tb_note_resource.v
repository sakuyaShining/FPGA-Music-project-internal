`timescale 1ns/1ps
module tb_note_resource;
    reg clk=0;always #5 clk=~clk;
    reg rst_n=0,req_valid=0,rsp_ready=0,cancel_valid=0;
    reg [1:0] req_kind=0;
    reg [31:0] req_token=0,req_groups=0,cancel_token=0;
    reg [3:0] req_layers=0;
    wire req_ready,work_valid,done_ready,rsp_valid,protocol_error;
    wire [1:0] work_kind;
    wire [2:0] work_ticket;
    wire [31:0] work_token,work_groups,rsp_token,rsp_groups,active_groups,reserved_groups;
    wire [3:0] work_layers,rsp_layers;
    wire [19:0] work_map,rsp_map;
    wire [2:0] rsp_code;
    wire [5:0] active_count;
    reg done_valid=0;
    reg [2:0] done_ticket=0;
    reg [31:0] done_token=0;
    wire work_ready;
    integer ready_delay=0,done_delay=1,response_delay=2,cancel_stage=0,wrong_ack=0;
    integer command_fd,trace_fd,read_count,command_index=0,wait_count,entry_number,position_number;
    reg [2047:0] command_path,trace_path;
    reg command_active=0,cancel_sent=0;
    integer command_kind;
    reg [31:0] command_token,command_groups;
    reg [3:0] command_layers;
    note_resource_mgr #(.TICKET_W(3)) dut(.*);

    reg backend_busy=0,wrong_sent=0;
    integer ready_ticks=0,backend_ticks=0;
    reg [1:0] pending_kind;
    reg [2:0] pending_ticket;
    reg [31:0] pending_token,pending_groups,audible_mask=0,prepared_mask=0;
    reg [3:0] pending_layers;
    reg [19:0] pending_map;
    integer finish_index;
    assign work_ready=!backend_busy&&ready_ticks>=ready_delay;
    always @(posedge clk)begin
        if(!rst_n)begin
            backend_busy<=0;done_valid<=0;ready_ticks<=0;audible_mask<=0;prepared_mask<=0;
        end else begin
            done_valid<=0;
            if(work_valid&&!work_ready&&!backend_busy)ready_ticks<=ready_ticks+1;
            if(work_valid&&work_ready)begin
                $fdisplay(trace_fd,"W %0d %0d %08h %08h %01h %05h",work_kind,work_ticket,work_token,work_groups,work_layers,work_map);
                backend_busy<=1;backend_ticks<=done_delay;wrong_sent<=0;ready_ticks<=0;
                pending_kind<=work_kind;pending_ticket<=work_ticket;pending_token<=work_token;
                pending_groups<=work_groups;pending_layers<=work_layers;pending_map<=work_map;
                if(work_groups==0)$fatal(1,"empty backend transaction");
                if(work_kind==2&&((audible_mask|prepared_mask)&work_groups)!=0)$fatal(1,"prepare reused audible/reserved groups");
            end
            if(backend_busy)begin
                if(backend_ticks>0)backend_ticks<=backend_ticks-1;
                else if(wrong_ack&&!wrong_sent)begin
                    done_valid<=1;done_ticket<=wrong_ack==2?pending_ticket:pending_ticket+1'b1;
                    done_token<=wrong_ack==1?pending_token:pending_token^32'd1;
                    wrong_sent<=1;backend_ticks<=1;
                end else begin
                    done_valid<=1;done_ticket<=pending_ticket;done_token<=pending_token;backend_busy<=0;
                    case(pending_kind)
                        1:begin audible_mask<=audible_mask&~pending_groups;prepared_mask<=prepared_mask&~pending_groups;end
                        2:begin
                            if(prepared_mask!=0)$fatal(1,"two simultaneous preparations");
                            prepared_mask<=pending_groups;
                        end
                        3:begin
                            if(prepared_mask!==pending_groups)$fatal(1,"published partial or unprepared note");
                            audible_mask<=audible_mask|pending_groups;prepared_mask<=0;
                        end
                        default:begin end
                    endcase
                end
            end
            if(req_valid&&req_ready&&req_kind==2)begin
                for(finish_index=0;finish_index<32;finish_index=finish_index+1)
                    if(dut.entries_valid[finish_index]&&dut.entry_tokens[finish_index]==req_token&&req_groups!=0&&
                       (req_groups&~dut.entry_masks[finish_index])==0)
                        audible_mask<=audible_mask&~req_groups;
            end
            if(rsp_valid&&rsp_ready)
                $fdisplay(trace_fd,"R %0d %08h %08h %01h %05h",rsp_code,rsp_token,rsp_groups,rsp_layers,rsp_map);
        end
    end

    always @(negedge clk)begin
        cancel_valid=0;
        if(rst_n&&command_active&&!cancel_sent&&req_kind==0)begin
            if((cancel_stage==2&&work_valid&&work_ready&&work_kind==1)||
               (cancel_stage==3&&work_valid&&work_ready&&work_kind==2)||
               (cancel_stage==4&&work_valid&&work_ready&&work_kind==3)||
               (cancel_stage==5&&rsp_valid&&rsp_code==0)||
               (cancel_stage==6&&dut.state==1&&dut.scan_index==2))begin
                cancel_valid=1;cancel_token=req_token;cancel_sent=1;
            end
        end
    end

    integer check_entry,check_other,check_layer,valid_count;
    reg [31:0] union_mask,mapped_mask;
    reg held_work=0;
    reg [92:0] held_payload;
    reg held_response=0;
    reg [90:0] response_payload;
    always @(posedge clk)if(rst_n&&done_valid&&done_ready&&
        (done_ticket!=work_ticket||done_token!=work_token))begin
        #1;if(dut.state!=9)$fatal(1,"stale completion advanced transaction");
    end
    always @(negedge clk)if(rst_n)begin
        if(held_work&&(!work_valid||{work_kind,work_ticket,work_token,work_groups,work_layers,work_map}!==held_payload))
            $fatal(1,"backend payload changed under backpressure");
        held_work=work_valid&&!work_ready;
        held_payload={work_kind,work_ticket,work_token,work_groups,work_layers,work_map};
        if(held_response&&!rsp_ready&&!(cancel_stage==5&&cancel_sent)&&
           (!rsp_valid||{rsp_code,rsp_token,rsp_groups,rsp_layers,rsp_map}!==response_payload))
            $fatal(1,"response changed under backpressure");
        held_response=rsp_valid&&!rsp_ready;
        response_payload={rsp_code,rsp_token,rsp_groups,rsp_layers,rsp_map};
        union_mask=0;valid_count=0;
        for(check_entry=0;check_entry<32;check_entry=check_entry+1)if(dut.entries_valid[check_entry])begin
            valid_count=valid_count+1;mapped_mask=0;
            for(check_layer=0;check_layer<4;check_layer=check_layer+1)
                if(dut.entry_layers[check_entry][check_layer])mapped_mask[dut.entry_maps[check_entry][check_layer*5+:5]]=1;
            if(mapped_mask!==dut.entry_masks[check_entry]||mapped_mask==0)$fatal(1,"layer/group identity mismatch");
            if((union_mask&mapped_mask)!=0)$fatal(1,"double group ownership");
            union_mask=union_mask|mapped_mask;
            for(check_other=check_entry+1;check_other<32;check_other=check_other+1)
                if(dut.entries_valid[check_other]&&dut.entry_tokens[check_other]==dut.entry_tokens[check_entry])$fatal(1,"duplicate note identity");
        end
        if(union_mask!==active_groups||(active_groups&reserved_groups)!=0)$fatal(1,"group conservation");
        if((dut.state==0||dut.state==11)&&valid_count!=active_count)$fatal(1,"entry/order conservation");
    end

    task wait_response;
        begin
            wait_count=0;
            while(!rsp_valid)begin
                @(negedge clk);#1;wait_count=wait_count+1;
                if(wait_count>2000)$fatal(1,"request watchdog command=%0d",command_index);
            end
        end
    endtask
    initial begin
        if(!$value$plusargs("commands=%s",command_path)||!$value$plusargs("trace=%s",trace_path))$fatal(1,"missing paths");
        command_fd=$fopen(command_path,"r");trace_fd=$fopen(trace_path,"w");
        if(!command_fd||!trace_fd)$fatal(1,"open files");
        repeat(4)@(negedge clk);#1;rst_n=1;
        while(!$feof(command_fd))begin
            read_count=$fscanf(command_fd,"%d %h %h %h %d %d %d %d %d\n",command_kind,command_token,command_layers,command_groups,
                cancel_stage,ready_delay,done_delay,response_delay,wrong_ack);
            if(read_count==9)begin
                @(negedge clk);#1;
                command_active=1;cancel_sent=0;req_kind=command_kind;req_token=command_token;
                req_layers=command_layers;req_groups=command_groups;req_valid=1;rsp_ready=0;
                if(cancel_stage==1&&command_kind==0)begin cancel_valid=1;cancel_token=command_token;cancel_sent=1;end
                $fdisplay(trace_fd,"C %0d",command_index);
                while(!req_ready)begin @(negedge clk);#1;end
                @(negedge clk);#1;req_valid=0;
                wait_response;
                repeat(response_delay)begin @(negedge clk);#1;end
                wait_response;
                rsp_ready=1;@(negedge clk);#1;rsp_ready=0;command_active=0;
                $fdisplay(trace_fd,"S %08h %08h %0d %0d",active_groups,reserved_groups,active_count,protocol_error);
                for(position_number=0;position_number<active_count;position_number=position_number+1)begin
                    entry_number=dut.order[position_number];
                    $fdisplay(trace_fd,"E %08h %08h %01h %05h %0d",dut.entry_tokens[entry_number],dut.entry_masks[entry_number],
                        dut.entry_layers[entry_number],dut.entry_maps[entry_number],dut.entries_released[entry_number]);
                end
                command_index=command_index+1;
            end else if(read_count!=-1)$fatal(1,"malformed command");
        end
        if(active_groups||reserved_groups||active_count||audible_mask||prepared_mask)$fatal(1,"final resources leaked");
        $display("PASS resource commands=%0d ticket_width=3 tails_kept_until_finish atomic_mock_backend",command_index);
        $finish;
    end
    initial begin #100000000;$fatal(1,"global watchdog");end
endmodule
