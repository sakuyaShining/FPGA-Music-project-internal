module note_event_router(
    input wire clk,rst_n,
    input wire live_valid,live_on,
    output wire live_ready,
    input wire [30:0] live_serial,
    input wire [6:0] live_note,
    input wire [7:0] live_velocity,
    input wire signed [17:0] live_glide,
    input wire [3:0] live_layers,
    input wire score_valid,score_on,
    output wire score_ready,
    input wire [30:0] score_serial,
    input wire [6:0] score_note,
    input wire [7:0] score_velocity,
    input wire signed [17:0] score_glide,
    input wire [3:0] score_layers,
    output wire event_valid,
    input wire event_ready,
    output reg event_on,
    output reg [31:0] event_token,
    output reg [6:0] event_note,
    output reg [7:0] event_velocity,
    output reg signed [17:0] event_glide,
    output reg [3:0] event_layers,
    input wire response_valid,
    output wire response_ready,
    input wire [31:0] response_token,response_groups,
    input wire [2:0] response_code,
    input wire [3:0] response_layers,
    input wire [19:0] response_map,
    output wire live_response_valid,score_response_valid,
    input wire live_response_ready,score_response_ready,
    output wire [31:0] routed_token,routed_groups,
    output wire [2:0] routed_code,
    output wire [3:0] routed_layers,
    output wire [19:0] routed_map,
    output reg protocol_error
);
    localparam IDLE=0,SEND=1,WAIT_RESPONSE=2;
    reg [1:0] state;
    reg next_source;
    wire select_score=score_valid&&(!live_valid||next_source);
    wire selected_valid=live_valid||score_valid;
    assign live_ready=rst_n&&state==IDLE&&!select_score;
    assign score_ready=rst_n&&state==IDLE&&select_score;
    assign event_valid=rst_n&&state==SEND;
    wire matches_response=state==WAIT_RESPONSE&&response_token==event_token;
    assign live_response_valid=rst_n&&response_valid&&matches_response&&!event_token[31];
    assign score_response_valid=rst_n&&response_valid&&matches_response&&event_token[31];
    assign response_ready=rst_n&&matches_response&&(event_token[31]?score_response_ready:live_response_ready);
    assign routed_token=response_token;
    assign routed_groups=response_groups;
    assign routed_code=response_code;
    assign routed_layers=response_layers;
    assign routed_map=response_map;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;next_source<=0;event_on<=0;event_token<=0;event_note<=0;
            event_velocity<=0;event_glide<=0;event_layers<=0;protocol_error<=0;
        end else begin
            if(response_valid&&!matches_response)protocol_error<=1;
            case(state)
                IDLE:if(selected_valid)begin
                    event_on<=select_score?score_on:live_on;
                    event_token<=select_score?{1'b1,score_serial}:{1'b0,live_serial};
                    event_note<=live_note;
                    event_velocity<=select_score?score_velocity:live_velocity;
                    event_glide<=select_score?score_glide:live_glide;
                    event_layers<=select_score?score_layers:live_layers;
                    next_source<=!select_score;state<=SEND;
                end
                SEND:if(event_ready)state<=WAIT_RESPONSE;
                WAIT_RESPONSE:if(response_valid&&response_ready)state<=IDLE;
                default:state<=IDLE;
            endcase
        end
    end
endmodule
