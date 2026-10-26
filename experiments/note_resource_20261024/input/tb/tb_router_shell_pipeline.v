`timescale 1ns/1ps
module tb_router_shell_pipeline;
    reg clk=0;always #5 clk=~clk;
    reg load=0,shift=0,capture=0;
    reg [3:0] data_in=0;
    wire [3:0] original_out,registered_out;
    note_router_timing_original original_shell(clk,load,shift,capture,data_in,original_out);
    note_router_timing_probe registered_shell(clk,load,shift,capture,data_in,registered_out);
    reg [639:0] expected=0;
    reg [167:0] expected_outputs=0;
    wire [167:0] original_outputs={original_shell.live_ready,original_shell.score_ready,
        original_shell.event_valid,original_shell.event_on,original_shell.event_token,
        original_shell.event_note,original_shell.event_velocity,original_shell.event_glide,
        original_shell.event_layers,original_shell.response_ready,original_shell.live_response_valid,
        original_shell.score_response_valid,original_shell.routed_token,original_shell.routed_groups,
        original_shell.routed_code,original_shell.routed_layers,original_shell.routed_map,original_shell.protocol_error};
    wire [167:0] registered_outputs={registered_shell.live_ready,registered_shell.score_ready,
        registered_shell.event_valid,registered_shell.event_on,registered_shell.event_token,
        registered_shell.event_note,registered_shell.event_velocity,registered_shell.event_glide,
        registered_shell.event_layers,registered_shell.response_ready,registered_shell.live_response_valid,
        registered_shell.score_response_valid,registered_shell.routed_token,registered_shell.routed_groups,
        registered_shell.routed_code,registered_shell.routed_layers,registered_shell.routed_map,registered_shell.protocol_error};
    reg [31:0] random_state=32'h93ac7041;
    integer cycle,overlaps=0,shifts=0,loads=0,captures=0;
    initial begin
        for(cycle=0;cycle<24000;cycle=cycle+1)begin
            @(negedge clk);
            random_state=random_state^(random_state<<13);
            random_state=random_state^(random_state>>17);
            random_state=random_state^(random_state<<5);
            {load,shift,capture,data_in}=random_state[6:0];
            if(cycle<12000)begin
                shift=1;load=(cycle%59==58);capture=(cycle%43==42);
            end
            if(load)loads=loads+1;
            if(shift)shifts=shifts+1;
            if(capture)captures=captures+1;
            if(load&&shift&&capture)overlaps=overlaps+1;
            @(posedge clk);#1;
            if(cycle>1)begin
                if({registered_shell.staging,registered_shell.controls,registered_shell.observation}!==expected)
                    $fatal(1,"shell pipeline state mismatch cycle=%0d",cycle);
                if(registered_outputs!==expected_outputs)
                    $fatal(1,"shell pipeline router mismatch cycle=%0d",cycle);
            end
            expected={original_shell.staging,original_shell.controls,original_shell.observation};
            expected_outputs=original_outputs;
        end
        if(loads<1000||shifts<15000||captures<1000||overlaps<500)$fatal(1,"shell pipeline coverage insufficient");
        $display("PASS shell_pipeline cycles=24000 loads=%0d shifts=%0d captures=%0d overlaps=%0d",loads,shifts,captures,overlaps);
        $finish;
    end
    initial begin #1000000;$fatal(1,"shell pipeline timeout");end
endmodule
