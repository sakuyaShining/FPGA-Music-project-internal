module note_router_timing_probe(input wire clk,load,shift,capture,input wire [3:0] data_in,output wire [3:0] data_out);
    reg [235:0] staging=0,controls=0;
    reg [167:0] observation=0;
    wire rst_n;
    wire live_valid,live_on;
    wire live_ready;
    wire [30:0] live_serial;
    wire [6:0] live_note;
    wire [7:0] live_velocity;
    wire signed [17:0] live_glide;
    wire [3:0] live_layers;
    wire score_valid,score_on;
    wire score_ready;
    wire [30:0] score_serial;
    wire [6:0] score_note;
    wire [7:0] score_velocity;
    wire signed [17:0] score_glide;
    wire [3:0] score_layers;
    wire event_valid;
    wire event_ready;
    wire event_on;
    wire [31:0] event_token;
    wire [6:0] event_note;
    wire [7:0] event_velocity;
    wire signed [17:0] event_glide;
    wire [3:0] event_layers;
    wire response_valid;
    wire response_ready;
    wire [31:0] response_token,response_groups;
    wire [2:0] response_code;
    wire [3:0] response_layers;
    wire [19:0] response_map;
    wire live_response_valid,score_response_valid;
    wire live_response_ready,score_response_ready;
    wire [31:0] routed_token,routed_groups;
    wire [2:0] routed_code;
    wire [3:0] routed_layers;
    wire [19:0] routed_map;
    wire protocol_error;
    assign {rst_n,live_valid,live_on,live_serial,live_note,live_velocity,live_glide,live_layers,score_valid,score_on,score_serial,score_note,score_velocity,score_glide,score_layers,event_ready,response_valid,response_token,response_groups,response_code,response_layers,response_map,live_response_ready,score_response_ready}=controls;
    assign data_out=observation[3:0];
    always @(posedge clk)begin
        if(shift)staging<={staging[231:0],data_in};
        if(load)controls<=staging;
        if(capture)observation<={live_ready,score_ready,event_valid,event_on,event_token,event_note,event_velocity,event_glide,event_layers,response_ready,live_response_valid,score_response_valid,routed_token,routed_groups,routed_code,routed_layers,routed_map,protocol_error};
        else if(shift)observation<={4'd0,observation[167:4]};
    end
    note_event_router dut(
        .clk(clk),.rst_n(rst_n),
        .live_valid(live_valid),.live_on(live_on),.live_ready(live_ready),.live_serial(live_serial),
        .live_note(live_note),.live_velocity(live_velocity),.live_glide(live_glide),.live_layers(live_layers),
        .score_valid(score_valid),.score_on(score_on),.score_ready(score_ready),.score_serial(score_serial),
        .score_note(score_note),.score_velocity(score_velocity),.score_glide(score_glide),.score_layers(score_layers),
        .event_valid(event_valid),.event_ready(event_ready),.event_on(event_on),.event_token(event_token),
        .event_note(event_note),.event_velocity(event_velocity),.event_glide(event_glide),.event_layers(event_layers),
        .response_valid(response_valid),.response_ready(response_ready),.response_token(response_token),
        .response_groups(response_groups),.response_code(response_code),.response_layers(response_layers),.response_map(response_map),
        .live_response_valid(live_response_valid),.score_response_valid(score_response_valid),
        .live_response_ready(live_response_ready),.score_response_ready(score_response_ready),
        .routed_token(routed_token),.routed_groups(routed_groups),.routed_code(routed_code),
        .routed_layers(routed_layers),.routed_map(routed_map),.protocol_error(protocol_error));
endmodule
