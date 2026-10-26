module note_contact_adapter #(
    parameter integer NF=26,SERIAL_W=31,SOURCE=0,
    parameter [30:0] INITIAL_SERIAL=0
)(
    input wire clk,rst_n,
    input wire on_valid,
    output wire on_ready,
    input wire [4:0] on_contact,
    input wire [7:0] on_generation,on_velocity,
    input wire [6:0] on_note,
    input wire signed [17:0] on_glide,
    input wire [3:0] on_layers,
    input wire release_valid,
    output wire release_ready,
    input wire [31:0] release_token,
    input wire move_valid,
    input wire [31:0] move_token,
    input wire signed [11:0] move_position,
    input wire retire_valid,finish_valid,
    input wire [31:0] retire_token,finish_token,finish_groups,
    output wire event_valid,
    input wire event_ready,
    output reg event_on,
    output wire [30:0] event_serial,
    output reg [31:0] event_token,
    output reg [6:0] event_note,
    output reg [7:0] event_velocity,
    output reg signed [17:0] event_glide,
    output reg [3:0] event_layers,
    output wire cancel_valid,
    output wire [31:0] cancel_token,
    input wire response_valid,
    output wire response_ready,
    input wire [31:0] response_token,response_groups,
    input wire [2:0] response_code,
    input wire [3:0] response_layers,
    input wire [19:0] response_map,
    output reg reply_valid,
    input wire reply_ready,
    output reg reply_on,
    output reg [31:0] reply_token,reply_groups,
    output reg [2:0] reply_code,
    output reg [3:0] reply_layers,
    output reg [19:0] reply_map,
    output reg [4:0] reply_contact,
    output reg [7:0] reply_generation,
    output wire expression_valid,
    output wire [31:0] expression_token,expression_groups,
    output wire [3:0] expression_layers,
    output wire signed [11:0] expression_position,
    input wire [4:0] query_contact,
    output wire query_held,
    output wire [31:0] query_token,query_groups,
    output wire [3:0] query_layers,
    output wire [19:0] query_map,
    output wire epoch_exhausted,
    output reg protocol_error
);
    localparam IDLE=0,SEND=1,WAIT_RESPONSE=2;
    reg [1:0] state;
    reg [NF-1:0] held,known;
    reg [31:0] tokens[0:NF-1],groups[0:NF-1];
    reg [3:0] layers[0:NF-1];
    reg [19:0] maps[0:NF-1];
    reg [7:0] generations[0:NF-1];
    reg [6:0] notes[0:NF-1];
    reg [SERIAL_W-1:0] next_serial;
    reg [SERIAL_W:0] issued;
    reg [4:0] pending_contact;
    reg [7:0] pending_generation;
    reg cancelled;
    reg release_found,move_found;
    reg [4:0] release_index,move_index;
    integer scan;
    always @*begin
        release_found=0;move_found=0;release_index=0;move_index=0;
        for(scan=0;scan<NF;scan=scan+1)begin
            if(known[scan]&&held[scan]&&tokens[scan]==release_token)begin
                release_found=1;release_index=scan;
            end
            if(known[scan]&&held[scan]&&tokens[scan]==move_token)begin
                move_found=1;move_index=scan;
            end
        end
    end
    function [3:0] remaining_layers;
        input [3:0] selected;
        input [19:0] mapping;
        input [31:0] completed;
        integer layer;
        begin
            remaining_layers=selected;
            for(layer=0;layer<4;layer=layer+1)
                if(selected[layer]&&completed[mapping[layer*5+:5]])remaining_layers[layer]=0;
        end
    endfunction
    reg allocation_valid;
    reg [31:0] mapped_groups;
    integer slot;
    always @*begin
        allocation_valid=response_layers==event_layers&&response_layers!=0&&response_groups!=0;
        mapped_groups=0;
        for(slot=0;slot<4;slot=slot+1)if(response_layers[slot])begin
            if(mapped_groups[response_map[slot*5+:5]])allocation_valid=0;
            mapped_groups[response_map[slot*5+:5]]=1;
        end
        if(mapped_groups!=response_groups)allocation_valid=0;
    end
    wire reply_space=!reply_valid||reply_ready;
    wire pending_release=(state==SEND||state==WAIT_RESPONSE)&&event_on&&release_token==event_token;
    assign release_ready=rst_n&&((state==IDLE&&reply_space)||pending_release);
    wire release_accept=release_valid&&release_ready;
    wire cancel_now=release_accept&&pending_release;
    assign on_ready=rst_n&&state==IDLE&&reply_space&&!release_valid&&!epoch_exhausted&&
        on_contact<NF&&!held[on_contact]&&on_layers!=0;
    assign event_valid=rst_n&&state==SEND;
    assign event_serial=event_token[30:0];
    assign cancel_valid=rst_n&&state!=IDLE&&event_on&&(cancelled||cancel_now);
    assign cancel_token=event_token;
    wire code_valid=event_on?(response_code==0||(response_code>=3&&response_code<=6)):(response_code==1||response_code==3||response_code==4);
    wire matched=state==WAIT_RESPONSE&&response_token==event_token;
    assign response_ready=rst_n&&matched&&reply_space&&code_valid&&
        (response_code!=0||(allocation_valid&&!cancelled&&!cancel_now));
    wire response_accept=response_valid&&response_ready;
    wire allocated=response_accept&&event_on&&response_code==0;
    wire [31:0] move_owned=move_found?groups[move_index]:32'd0;
    wire same_finish=finish_valid&&finish_token==move_token&&(finish_groups&~move_owned)==0;
    wire [31:0] surviving_groups=move_owned&~(same_finish?finish_groups:32'd0);
    assign expression_valid=rst_n&&move_valid&&move_found&&surviving_groups!=0&&
        !(retire_valid&&retire_token==move_token)&&!(release_accept&&release_token==move_token);
    assign expression_token=move_token;
    assign expression_groups=surviving_groups;
    assign expression_layers=move_found?remaining_layers(layers[move_index],maps[move_index],same_finish?finish_groups:32'd0):4'd0;
    assign expression_position=move_position;
    assign query_held=query_contact<NF?held[query_contact]:1'b0;
    assign query_token=query_contact<NF&&known[query_contact]?tokens[query_contact]:32'd0;
    assign query_groups=query_contact<NF?groups[query_contact]:32'd0;
    assign query_layers=query_contact<NF?layers[query_contact]:4'd0;
    assign query_map=query_contact<NF?maps[query_contact]:20'd0;
    assign epoch_exhausted=issued[SERIAL_W];
    integer row;
    reg [31:0] finish_base;
    reg [3:0] finish_layers;
    reg [19:0] finish_map;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            state<=IDLE;held<=0;known<=0;next_serial<=INITIAL_SERIAL;issued<=0;
            pending_contact<=0;pending_generation<=0;cancelled<=0;
            event_on<=0;event_token<=0;event_note<=0;event_velocity<=0;event_glide<=0;event_layers<=0;
            reply_valid<=0;reply_on<=0;reply_token<=0;reply_groups<=0;reply_code<=0;
            reply_layers<=0;reply_map<=0;reply_contact<=0;reply_generation<=0;protocol_error<=0;
            for(row=0;row<NF;row=row+1)begin
                tokens[row]<=0;groups[row]<=0;layers[row]<=0;maps[row]<=0;generations[row]<=0;notes[row]<=0;
            end
        end else begin
            if(reply_valid&&reply_ready)reply_valid<=0;
            if(response_valid&&(!matched||!code_valid||(response_code==0&&!allocation_valid)))protocol_error<=1;
            if(release_accept&&release_found)held[release_index]<=0;
            if(cancel_now)cancelled<=1;
            case(state)
                IDLE:begin
                    if(release_accept&&release_found)begin
                        event_on<=0;event_token<=release_token;event_note<=notes[release_index];
                        event_velocity<=0;event_glide<=0;event_layers<=0;
                        pending_contact<=release_index;pending_generation<=generations[release_index];
                        cancelled<=0;state<=SEND;
                    end else if(on_valid&&on_ready)begin
                        event_on<=1;event_token<={SOURCE[0],{(31-SERIAL_W){1'b0}},next_serial};
                        event_note<=on_note;event_velocity<=on_velocity;event_glide<=on_glide;event_layers<=on_layers;
                        pending_contact<=on_contact;pending_generation<=on_generation;
                        tokens[on_contact]<={SOURCE[0],{(31-SERIAL_W){1'b0}},next_serial};
                        held[on_contact]<=1;known[on_contact]<=1;generations[on_contact]<=on_generation;
                        notes[on_contact]<=on_note;groups[on_contact]<=0;layers[on_contact]<=0;maps[on_contact]<=0;
                        next_serial<=next_serial+1'b1;issued<=issued+1'b1;cancelled<=0;state<=SEND;
                    end
                end
                SEND:if(event_ready)state<=WAIT_RESPONSE;
                WAIT_RESPONSE:if(response_accept)begin
                    reply_valid<=1;reply_on<=event_on;reply_token<=response_token;reply_groups<=response_groups;
                    reply_code<=response_code;reply_layers<=response_layers;reply_map<=response_map;
                    reply_contact<=pending_contact;reply_generation<=pending_generation;
                    if(event_on)begin
                        groups[pending_contact]<=allocated?response_groups:32'd0;
                        layers[pending_contact]<=allocated?response_layers:4'd0;
                        maps[pending_contact]<=allocated?response_map:20'd0;
                    end
                    cancelled<=0;state<=IDLE;
                end
                default:state<=IDLE;
            endcase
            for(row=0;row<NF;row=row+1)begin
                if(known[row]&&!(on_valid&&on_ready&&row==on_contact)&&retire_valid&&tokens[row]==retire_token)begin
                    groups[row]<=0;layers[row]<=0;maps[row]<=0;
                end else if(known[row]&&!(on_valid&&on_ready&&row==on_contact)&&finish_valid&&tokens[row]==finish_token)begin
                    finish_base=(allocated&&row==pending_contact)?response_groups:groups[row];
                    finish_layers=(allocated&&row==pending_contact)?response_layers:layers[row];
                    finish_map=(allocated&&row==pending_contact)?response_map:maps[row];
                    if(finish_groups==0||(finish_groups&~finish_base)!=0)protocol_error<=1;
                    else begin
                        groups[row]<=finish_base&~finish_groups;
                        layers[row]<=remaining_layers(finish_layers,finish_map,finish_groups);
                    end
                end
            end
        end
    end
endmodule
