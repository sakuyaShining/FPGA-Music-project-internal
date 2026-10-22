module board_audio_top #(
    parameter UART_BAUD=115200,WARM_CYCLES=27000000,DIAG_CAPTURE_SAMPLES=2048,
    parameter REPORT_CYCLES=135000,CASE_CYCLES=27000000,TAIL_CYCLES=40500000
)(
    input wire clk,reset_button,uart_rx_pin,
    output wire uart_tx_pin,
    output wire [5:0] led,
    output wire dac_din,dac_ws,dac_bck,pa_en
);
    // S1/pin87 is active HIGH. Async assertion, two-clock synchronous release.
    reg [1:0] reset_release=0;
    always @(posedge clk or posedge reset_button)
        if(reset_button)reset_release<=0;else reset_release<={reset_release[0],1'b1};
    wire rst_n=reset_release[1];
    reg [31:0] warm_count,heartbeat;
    wire warm=warm_count>=WARM_CYCLES;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin warm_count<=0;heartbeat<=0;end
        else begin heartbeat<=heartbeat+1'b1;if(!warm)warm_count<=warm_count+1'b1;end
    end
    wire armed,running,initialized,wr_en;
    wire [7:0] test_case,wr_addr,wr_data;
    wire cfg_valid,cfg_commit,cfg_ready,cfg_error,cfg_applied;
    wire [1:0] cfg_slot;wire [3:0] cfg_part;wire [47:0] cfg_word;
    wire frame_valid,frame_ready;
    wire [25:0] contact,bound,blocked;
    wire [233:0] position;wire [181:0] note_map;wire [31:0] frame_sequence;
    wire [3:0] selection;
    wire frame_error,link_error,sensor_error,watchdog_error,layer_error,selection_error,control_error;
    wire fault=frame_error||link_error||sensor_error||watchdog_error||layer_error||selection_error||control_error||cfg_error;
    wire [7:0] status={fault,(|bound),running,initialized,warm,armed,1'b0,(warm&&initialized)};
    wire raw_din,raw_ws,raw_bck,raw_pa;
    wire permit=warm&&initialized&&armed&&!fault&&test_case!=6;
    assign pa_en=permit&&raw_pa;
    assign dac_din=permit?raw_din:1'b0;
    assign dac_ws=raw_ws;assign dac_bck=raw_bck;
    assign led=~{heartbeat[24],fault,(|bound),running,armed,(warm&&initialized)};
    tri [15:0] internal_pad;
    board_test_driver #(.REPORT_CYCLES(REPORT_CYCLES),.CASE_CYCLES(CASE_CYCLES),.TAIL_CYCLES(TAIL_CYCLES)) driver(
        .clk(clk),.rst_n(rst_n),.warm(warm),.fault(fault),.wr_en(wr_en),.wr_addr(wr_addr),.wr_data(wr_data),
        .armed(armed),.running(running),.test_case(test_case),.initialized(initialized),
        .cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),
        .frame_valid(frame_valid),.frame_ready(frame_ready),.contact(contact),.position(position),.note_map(note_map),.frame_sequence(frame_sequence),.selection(selection),.bound(bound));
    left_layer_music_probe #(.BOARD_DIAG(1),.BOARD_BOOT_SCRUB(1),.UART_BAUD(UART_BAUD),.DIAG_CAPTURE_SAMPLES(DIAG_CAPTURE_SAMPLES)) music(
        .clk(clk),.rst_n(rst_n),.uart_rx_pin(uart_rx_pin),.uart_tx_pin(uart_tx_pin),
        .board_status(status),.board_case(test_case),.board_wr_en(wr_en),.board_wr_addr(wr_addr),.board_wr_data(wr_data),
        .layer_selection(selection),.cfg_valid(cfg_valid),.cfg_commit(cfg_commit),.cfg_slot(cfg_slot),.cfg_part(cfg_part),.cfg_word(cfg_word),.cfg_ready(cfg_ready),.cfg_applied(cfg_applied),.cfg_error(cfg_error),
        .layer_protocol_error(layer_error),.layer_selection_error(selection_error),
        .left_valid(frame_valid),.left_ready(frame_ready),.left_contact(contact),.left_invalid(26'd0),.left_position(position),.left_sequence(frame_sequence),.left_calibration(1'b0),.left_note_map(note_map),.left_velocity(4'd4),
        .frame_error(frame_error),.link_error(link_error),.sensor_error(sensor_error),.watchdog_error(watchdog_error),.bound_contacts(bound),.blocked_contacts(blocked),
        .ev_valid(1'b0),.ev_on(1'b0),.ev_note(7'd0),.ev_vel(4'd0),.preset(2'd0),.pad(internal_pad),
        .touch_valid(1'b0),.touch_active(5'd0),.touch_x(50'd0),.touch_y(50'd0),.touch_id(20'd0),.radius(10'd50),.slew_step(10'd1),.part_to_control(48'd0),.restore_valid(1'b0),.voice_mask(32'hffffffff),.control_error(control_error),
        .dac_din(raw_din),.dac_ws(raw_ws),.dac_bck(raw_bck),.pa_en(raw_pa));
endmodule
