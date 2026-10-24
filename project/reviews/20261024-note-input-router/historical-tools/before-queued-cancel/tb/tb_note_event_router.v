`timescale 1ns/1ps
module tb_note_event_router;
    reg clk=0;always #5 clk=~clk;
    reg [235:0] stimulus=0;
    wire rst_n,live_valid,live_on,live_ready,score_valid,score_on,score_ready;
    wire [30:0] live_serial,score_serial;
    wire [6:0] live_note,score_note,event_note;
    wire [7:0] live_velocity,score_velocity,event_velocity;
    wire signed [17:0] live_glide,score_glide,event_glide;
    wire [3:0] live_layers,score_layers,event_layers,response_layers,routed_layers;
    wire event_valid,event_ready,event_on,response_valid,response_ready;
    wire [31:0] event_token,response_token,response_groups,routed_token,routed_groups;
    wire [2:0] response_code,routed_code;
    wire [19:0] response_map,routed_map;
    wire live_response_valid,score_response_valid,live_response_ready,score_response_ready,protocol_error;
    assign {rst_n,live_valid,live_on,live_serial,live_note,live_velocity,live_glide,live_layers,
        score_valid,score_on,score_serial,score_note,score_velocity,score_glide,score_layers,
        event_ready,response_valid,response_token,response_groups,response_code,response_layers,response_map,
        live_response_ready,score_response_ready}=stimulus;
    note_event_router dut(.*);
    wire [167:0] observed={live_ready,score_ready,event_valid,event_on,event_token,event_note,event_velocity,event_glide,event_layers,
        response_ready,live_response_valid,score_response_valid,routed_token,routed_groups,routed_code,routed_layers,routed_map,protocol_error};
    integer input_fd,trace_fd,fields,cycle=0;
    reg [2047:0] input_path,trace_path;
    initial begin
        if(!$value$plusargs("inputs=%s",input_path)||!$value$plusargs("trace=%s",trace_path))$fatal(1,"missing paths");
        input_fd=$fopen(input_path,"r");trace_fd=$fopen(trace_path,"w");
        if(!input_fd||!trace_fd)$fatal(1,"file open failed");
        while(!$feof(input_fd))begin
            @(negedge clk);fields=$fscanf(input_fd,"%h",stimulus);
            if(fields==1)begin
                #1;$fdisplay(trace_fd,"%0d %042h",cycle,observed);cycle=cycle+1;
                @(posedge clk);
            end
        end
        $display("PASS event_router cycles=%0d",cycle);$fclose(trace_fd);$finish;
    end
    initial begin #10000000;$fatal(1,"global timeout");end
endmodule
