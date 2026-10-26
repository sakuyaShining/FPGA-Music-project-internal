module note_frame_transport #(parameter integer NF=26,BAD_FRAMES=8,FRAME_TIMEOUT=2700000,LINK_TIMEOUT=8192)(
    input wire clk,
    input wire rst_n,
    input wire frame_valid,
    input wire [NF-1:0] contact,
    input wire [NF-1:0] invalid,
    input wire [NF*9-1:0] position,
    input wire [NF*7-1:0] note_map,
    input wire [31:0] frame_sequence,
    input wire frame_calibration,
    input wire [7:0] velocity,
    input wire [17:0] glide,
    input wire [3:0] layer_selection,
    input wire retire_valid,
    input wire [31:0] retire_token,
    input wire finish_valid,
    input wire [31:0] finish_token,
    input wire [31:0] finish_groups,
    input wire event_ready,
    input wire response_valid,
    input wire [31:0] response_token,
    input wire [2:0] response_code,
    input wire [31:0] response_groups,
    input wire [3:0] response_layers,
    input wire [19:0] response_map,
    input wire reply_ready,
    output wire frame_ready,
    output wire frame_error,
    output wire link_error,
    output wire sensor_error,
    output wire watchdog_error,
    output wire admission_error,
    output wire [NF-1:0] seen_contacts,
    output wire [NF-1:0] blocked_contacts,
    output wire anchor_valid,
    output wire [4:0] anchor_contact,
    output wire [11:0] anchor_position,
    output wire event_valid,
    output wire event_on,
    output wire [30:0] event_serial,
    output wire [31:0] event_token,
    output wire [6:0] event_note,
    output wire [7:0] event_velocity,
    output wire [17:0] event_glide,
    output wire [3:0] event_layers,
    output wire cancel_valid,
    output wire [31:0] cancel_token,
    output wire response_ready,
    output wire reply_valid,
    output wire reply_on,
    output wire [31:0] reply_token,
    output wire [31:0] reply_groups,
    output wire [2:0] reply_code,
    output wire [3:0] reply_layers,
    output wire [19:0] reply_map,
    output wire [4:0] reply_contact,
    output wire [7:0] reply_generation,
    output wire expression_valid,
    output wire [31:0] expression_token,
    output wire [31:0] expression_groups,
    output wire [3:0] expression_layers,
    output wire [11:0] expression_position,
    output wire epoch_exhausted,
    output wire protocol_error
);
    wire on_valid;
    wire [4:0] on_contact;
    wire [7:0] on_generation;
    wire [6:0] on_note;
    wire [7:0] on_velocity;
    wire [17:0] on_glide;
    wire [3:0] on_layers;
    wire release_valid;
    wire [31:0] release_token;
    wire move_valid;
    wire [31:0] move_token;
    wire [11:0] move_position;
    wire [4:0] query_contact;
    wire on_ready;
    wire release_ready;
    wire query_held;
    wire [31:0] query_token;
    wire [31:0] query_groups;
    wire [3:0] query_layers;
    wire [19:0] query_map;
    wire signed [11:0] on_position;
    reg link_pending;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)link_pending<=0;
        else begin
            if(reply_valid&&reply_ready)link_pending<=0;
            if((on_valid&&on_ready)||(release_valid&&release_ready))link_pending<=1;
        end
    end
    assign anchor_valid=on_valid&&on_ready;
    assign anchor_contact=on_contact;
    assign anchor_position=on_position;
    contact_frame_source #(.NF(NF),.BAD_FRAMES(BAD_FRAMES),.FRAME_TIMEOUT(FRAME_TIMEOUT),.LINK_TIMEOUT(LINK_TIMEOUT)) source(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.contact(contact),.invalid(invalid),.position(position),.note_map(note_map),.frame_sequence(frame_sequence),.frame_calibration(frame_calibration),.velocity(velocity),.glide(glide),.layer_selection(layer_selection),.on_valid(on_valid),.on_ready(on_ready),.on_contact(on_contact),.on_generation(on_generation),.on_velocity(on_velocity),.on_note(on_note),.on_glide(on_glide),.on_layers(on_layers),.on_position(on_position),.release_valid(release_valid),.release_ready(release_ready),.release_token(release_token),.move_valid(move_valid),.move_token(move_token),.move_position(move_position),.query_contact(query_contact),.query_held(query_held),.query_token(query_token),.query_groups(query_groups),.frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.admission_error(admission_error),.seen_contacts(seen_contacts),.blocked_contacts(blocked_contacts),.link_pending(link_pending));
    note_contact_adapter #(.NF(NF)) ledger(
        .clk(clk),.rst_n(rst_n),.on_valid(on_valid),.on_contact(on_contact),.on_generation(on_generation),.on_note(on_note),.on_velocity(on_velocity),.on_glide(on_glide),.on_layers(on_layers),.release_valid(release_valid),.release_token(release_token),.move_valid(move_valid),.move_token(move_token),.move_position(move_position),.retire_valid(retire_valid),.retire_token(retire_token),.finish_valid(finish_valid),.finish_token(finish_token),.finish_groups(finish_groups),.event_ready(event_ready),.response_valid(response_valid),.response_token(response_token),.response_code(response_code),.response_groups(response_groups),.response_layers(response_layers),.response_map(response_map),.reply_ready(reply_ready),.query_contact(query_contact),.on_ready(on_ready),.release_ready(release_ready),.event_valid(event_valid),.event_on(event_on),.event_serial(event_serial),.event_token(event_token),.event_note(event_note),.event_velocity(event_velocity),.event_glide(event_glide),.event_layers(event_layers),.cancel_valid(cancel_valid),.cancel_token(cancel_token),.response_ready(response_ready),.reply_valid(reply_valid),.reply_on(reply_on),.reply_token(reply_token),.reply_groups(reply_groups),.reply_code(reply_code),.reply_layers(reply_layers),.reply_map(reply_map),.reply_contact(reply_contact),.reply_generation(reply_generation),.expression_valid(expression_valid),.expression_token(expression_token),.expression_groups(expression_groups),.expression_layers(expression_layers),.expression_position(expression_position),.query_held(query_held),.query_token(query_token),.query_groups(query_groups),.query_layers(query_layers),.query_map(query_map),.epoch_exhausted(epoch_exhausted),.protocol_error(protocol_error));
endmodule
