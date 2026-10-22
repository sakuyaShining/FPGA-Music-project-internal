// Structural scan harness ONLY. All controls are independently reachable over
// serial history, but arbitrary bit shifts are not valid performance events.
// Never program this bitstream: no functional bench gate or user protocol.
module joint_timing_top(
 input wire clk,reset_button,scan_in,output wire probe_out,
 output wire [5:0] led,output wire dac_din,dac_ws,dac_bck,pa_en,
 output wire O_sdram_clk,O_sdram_cke,O_sdram_cs_n,
 output wire O_sdram_ras_n,O_sdram_cas_n,O_sdram_wen_n,
 output wire [10:0] O_sdram_addr,output wire [1:0] O_sdram_ba,
 output wire [3:0] O_sdram_dqm,inout wire [31:0] IO_sdram_dq
);
 wire logic_clk,clock_locked;
`ifdef TIMING_RTL_SIM
 // Only for functional protocol simulation; not a model of PLL jitter/lock.
 assign logic_clk=clk;
 assign clock_locked=1'b1;
`else
 rPLL clocking(.CLKOUT(logic_clk),.LOCK(clock_locked),.CLKOUTP(),.CLKOUTD(),.CLKOUTD3(),
 .RESET(1'b0),.RESET_P(1'b0),.CLKIN(clk),.CLKFB(1'b0),
 .FBDSEL(6'd0),.IDSEL(6'd0),.ODSEL(6'd0),.PSDA(4'd0),.DUTYDA(4'd0),.FDLY(4'd0));
 defparam clocking.FCLKIN="27",clocking.DYN_IDIV_SEL="false",clocking.IDIV_SEL=0,
 clocking.DYN_FBDIV_SEL="false",clocking.FBDIV_SEL=0,clocking.DYN_ODIV_SEL="false",clocking.ODIV_SEL=32,
 clocking.PSDA_SEL="0000",clocking.DYN_DA_EN="true",clocking.DUTYDA_SEL="1000",
 clocking.CLKOUT_FT_DIR=1'b1,clocking.CLKOUTP_FT_DIR=1'b1,clocking.CLKOUT_DLY_STEP=0,
 clocking.CLKOUTP_DLY_STEP=0,clocking.CLKFB_SEL="internal",clocking.CLKOUT_BYPASS="false",
 clocking.CLKOUTP_BYPASS="false",clocking.CLKOUTD_BYPASS="false",clocking.DYN_SDIV_SEL=2,
 clocking.CLKOUTD_SRC="CLKOUT",clocking.CLKOUTD3_SRC="CLKOUT",clocking.DEVICE="GW2AR-18C";
`endif
 wire reset_assert=reset_button || !clock_locked;
 reg [1:0] reset_release=0;
 always @(posedge logic_clk or posedge reset_assert)
  if(reset_assert)reset_release<=0;else reset_release<={reset_release[0],1'b1};
 wire rst_n=reset_release[1];

 // External scan_in reaches only the first synchronizer stage.
 reg scan_meta,scan_sync;
 always @(posedge logic_clk)begin scan_meta<=scan_in;scan_sync<=scan_meta;end
 localparam INPUT_BITS=587,OUTPUT_BITS=956,OBS_CHUNKS=30;
 reg [INPUT_BITS-1:0] controls;
 always @(posedge logic_clk)controls<={controls[INPUT_BITS-2:0],scan_sync};
 tri [15:0] unused_pad;
 wire  probe_rec_clear_ready;
 wire  probe_play_clear_ready;
 wire  probe_rec_clear_done;
 wire  probe_play_clear_done;
 wire  probe_rec_clearing;
 wire  probe_play_clearing;
 wire  probe_mem_busy;
 wire [17:0] probe_rec_ring_level;
 wire [17:0] probe_play_ring_level;
 wire  probe_sdram_req_ready;
 wire  probe_sdram_rsp_valid;
 wire  probe_sdram_init_done;
 wire [15:0] probe_sdram_rsp_data;
 wire  probe_feed_ready;
 wire  probe_rec_valid;
 wire  probe_rec_overflow;
 wire  probe_play_valid;
 wire  probe_play_underflow;
 wire  probe_play_miss;
 wire [15:0] probe_rec_data;
 wire [15:0] probe_play_data;
 wire [10:0] probe_rec_level;
 wire [10:0] probe_play_level;
 wire  probe_cfg_ready;
 wire  probe_cfg_applied;
 wire  probe_cfg_error;
 wire  probe_layer_protocol_error;
 wire  probe_layer_selection_error;
 wire  probe_sensor_report_ready;
 wire  probe_frame_error;
 wire  probe_link_error;
 wire  probe_sensor_error;
 wire  probe_watchdog_error;
 wire [25:0] probe_bound_contacts;
 wire [25:0] probe_blocked_contacts;
 wire  probe_scan_bus_request;
 wire  probe_scan_bus_sck;
 wire  probe_scan_bus_mosi;
 wire  probe_scan_latch;
 wire  probe_sensor_report_valid;
 wire  probe_sensor_report_calibration;
 wire  probe_sensor_protocol_error;
 wire  probe_sensor_grant_error;
 wire [25:0] probe_sensor_contact;
 wire [25:0] probe_sensor_invalid;
 wire [233:0] probe_sensor_position;
 wire [31:0] probe_sensor_sequence;
 wire  probe_uart_tx_pin;
 wire  probe_finger_valid;
 wire [1:0] probe_finger_cmd;
 wire [4:0] probe_finger_id;
 wire [4:0] probe_finger_group;
 wire signed [11:0] probe_finger_position;
 wire  probe_touch_ready;
 wire [79:0] probe_fader_y;
 wire [159:0] probe_gains;
 wire  probe_touch_done;
 wire  probe_gain_done;
 wire  probe_control_error;
 wire  probe_dac_din;
 wire  probe_dac_ws;
 wire  probe_dac_bck;
 wire  probe_pa_en;
 wire  probe_voice_valid;
 wire  probe_voice_on;
 wire [4:0] probe_voice_group;
 wire [6:0] probe_voice_note;
 wire  probe_pcm_valid;
 wire signed [23:0] probe_pcm;
 wire  probe_lcd_reset_n;
 wire  probe_lcd_cs_n;
 wire  probe_lcd_sck;
 wire  probe_lcd_mosi;
 wire  probe_lcd_dc;
 wire [31:0] probe_rendered_frames;
 wire [31:0] probe_late_frames;
 wire [31:0] probe_analysis_gaps;
 wire [31:0] probe_spectrum_sequence;
 sdram_stream_probe system(.rec_clear_ready(probe_rec_clear_ready),
 .play_clear_ready(probe_play_clear_ready),
 .rec_clear_done(probe_rec_clear_done),
 .play_clear_done(probe_play_clear_done),
 .rec_clearing(probe_rec_clearing),
 .play_clearing(probe_play_clearing),
 .mem_busy(probe_mem_busy),
 .rec_ring_level(probe_rec_ring_level),
 .play_ring_level(probe_play_ring_level),
 .sdram_req_valid(1'd0),
 .sdram_req_write(1'd0),
 .sdram_rsp_ready(1'd0),
 .sdram_req_addr(22'd0),
 .sdram_req_data(16'd0),
 .sdram_req_ready(probe_sdram_req_ready),
 .sdram_rsp_valid(probe_sdram_rsp_valid),
 .sdram_init_done(probe_sdram_init_done),
 .sdram_rsp_data(probe_sdram_rsp_data),
 .sd_clk(O_sdram_clk),
 .sd_cke(O_sdram_cke),
 .sd_cs_n(O_sdram_cs_n),
 .sd_ras_n(O_sdram_ras_n),
 .sd_cas_n(O_sdram_cas_n),
 .sd_we_n(O_sdram_wen_n),
 .sd_addr(O_sdram_addr),
 .sd_bank(O_sdram_ba),
 .sd_dqm(O_sdram_dqm),
 .sd_dq(IO_sdram_dq),
 .rec_clear(controls[0 +: 1]),
 .rec_enable(controls[1 +: 1]),
 .rec_ready(controls[2 +: 1]),
 .play_clear(controls[3 +: 1]),
 .play_enable(controls[4 +: 1]),
 .feed_valid(controls[5 +: 1]),
 .feed_data(controls[6 +: 16]),
 .feed_ready(probe_feed_ready),
 .rec_valid(probe_rec_valid),
 .rec_overflow(probe_rec_overflow),
 .play_valid(probe_play_valid),
 .play_underflow(probe_play_underflow),
 .play_miss(probe_play_miss),
 .rec_data(probe_rec_data),
 .play_data(probe_play_data),
 .rec_level(probe_rec_level),
 .play_level(probe_play_level),
 .layer_selection(controls[22 +: 4]),
 .cfg_valid(controls[26 +: 1]),
 .cfg_commit(controls[27 +: 1]),
 .cfg_slot(controls[28 +: 2]),
 .cfg_part(controls[30 +: 4]),
 .cfg_word(controls[34 +: 88]),
 .cfg_ready(probe_cfg_ready),
 .cfg_applied(probe_cfg_applied),
 .cfg_error(probe_cfg_error),
 .layer_protocol_error(probe_layer_protocol_error),
 .layer_selection_error(probe_layer_selection_error),
 .sense_n(controls[122 +: 6]),
 .calibrate(controls[128 +: 1]),
 .scan_bus_grant(controls[129 +: 1]),
 .sensor_report_ready(probe_sensor_report_ready),
 .left_note_map(controls[130 +: 182]),
 .left_velocity(controls[312 +: 4]),
 .frame_error(probe_frame_error),
 .link_error(probe_link_error),
 .sensor_error(probe_sensor_error),
 .watchdog_error(probe_watchdog_error),
 .bound_contacts(probe_bound_contacts),
 .blocked_contacts(probe_blocked_contacts),
 .threshold_on(controls[316 +: 14]),
 .threshold_off(controls[330 +: 14]),
 .scan_bus_request(probe_scan_bus_request),
 .scan_bus_sck(probe_scan_bus_sck),
 .scan_bus_mosi(probe_scan_bus_mosi),
 .scan_latch(probe_scan_latch),
 .sensor_report_valid(probe_sensor_report_valid),
 .sensor_report_calibration(probe_sensor_report_calibration),
 .sensor_protocol_error(probe_sensor_protocol_error),
 .sensor_grant_error(probe_sensor_grant_error),
 .sensor_contact(probe_sensor_contact),
 .sensor_invalid(probe_sensor_invalid),
 .sensor_position(probe_sensor_position),
 .sensor_sequence(probe_sensor_sequence),
 .clk(logic_clk),
 .rst_n(rst_n),
 .uart_rx_pin(controls[344 +: 1]),
 .uart_tx_pin(probe_uart_tx_pin),
 .ev_valid(controls[345 +: 1]),
 .ev_on(controls[346 +: 1]),
 .ev_note(controls[347 +: 7]),
 .ev_vel(controls[354 +: 4]),
 .preset(controls[358 +: 2]),
 .finger_valid(probe_finger_valid),
 .finger_cmd(probe_finger_cmd),
 .finger_id(probe_finger_id),
 .finger_group(probe_finger_group),
 .finger_position(probe_finger_position),
 .pad(unused_pad),
 .touch_valid(controls[360 +: 1]),
 .touch_ready(probe_touch_ready),
 .touch_active(controls[361 +: 5]),
 .touch_x(controls[366 +: 50]),
 .touch_y(controls[416 +: 50]),
 .touch_id(controls[466 +: 20]),
 .radius(controls[486 +: 10]),
 .slew_step(controls[496 +: 10]),
 .part_to_control(controls[506 +: 48]),
 .restore_valid(controls[554 +: 1]),
 .voice_mask(controls[555 +: 32]),
 .fader_y(probe_fader_y),
 .gains(probe_gains),
 .touch_done(probe_touch_done),
 .gain_done(probe_gain_done),
 .control_error(probe_control_error),
 .led(led),
 .dac_din(probe_dac_din),
 .dac_ws(probe_dac_ws),
 .dac_bck(probe_dac_bck),
 .pa_en(probe_pa_en),
 .voice_valid(probe_voice_valid),
 .voice_on(probe_voice_on),
 .voice_group(probe_voice_group),
 .voice_note(probe_voice_note),
 .pcm_valid(probe_pcm_valid),
 .pcm(probe_pcm),
 .lcd_reset_n(probe_lcd_reset_n),
 .lcd_cs_n(probe_lcd_cs_n),
 .lcd_sck(probe_lcd_sck),
 .lcd_mosi(probe_lcd_mosi),
 .lcd_dc(probe_lcd_dc),
 .rendered_frames(probe_rendered_frames),
 .late_frames(probe_late_frames),
 .analysis_gaps(probe_analysis_gaps),
 .spectrum_sequence(probe_spectrum_sequence));
 wire [OUTPUT_BITS-1:0] observable={probe_rec_clear_ready,probe_play_clear_ready,probe_rec_clear_done,probe_play_clear_done,probe_rec_clearing,probe_play_clearing,probe_mem_busy,probe_rec_ring_level,probe_play_ring_level,probe_sdram_req_ready,probe_sdram_rsp_valid,probe_sdram_init_done,probe_sdram_rsp_data,probe_feed_ready,probe_rec_valid,probe_rec_overflow,probe_play_valid,probe_play_underflow,probe_play_miss,probe_rec_data,probe_play_data,probe_rec_level,probe_play_level,probe_cfg_ready,probe_cfg_applied,probe_cfg_error,probe_layer_protocol_error,probe_layer_selection_error,probe_sensor_report_ready,probe_frame_error,probe_link_error,probe_sensor_error,probe_watchdog_error,probe_bound_contacts,probe_blocked_contacts,probe_scan_bus_request,probe_scan_bus_sck,probe_scan_bus_mosi,probe_scan_latch,probe_sensor_report_valid,probe_sensor_report_calibration,probe_sensor_protocol_error,probe_sensor_grant_error,probe_sensor_contact,probe_sensor_invalid,probe_sensor_position,probe_sensor_sequence,probe_uart_tx_pin,probe_finger_valid,probe_finger_cmd,probe_finger_id,probe_finger_group,probe_finger_position,probe_touch_ready,probe_fader_y,probe_gains,probe_touch_done,probe_gain_done,probe_control_error,probe_dac_din,probe_dac_ws,probe_dac_bck,probe_pa_en,probe_voice_valid,probe_voice_on,probe_voice_group,probe_voice_note,probe_pcm_valid,probe_pcm,probe_lcd_reset_n,probe_lcd_cs_n,probe_lcd_sck,probe_lcd_mosi,probe_lcd_dc,probe_rendered_frames,probe_late_frames,probe_analysis_gaps,probe_spectrum_sequence};
 wire [OBS_CHUNKS*32-1:0] padded={{(OBS_CHUNKS*32-OUTPUT_BITS){1'b0}},observable};
 reg [OBS_CHUNKS-1:0] observation;
 wire [OBS_CHUNKS-1:0] capture;
 genvar c;generate for(c=0;c<OBS_CHUNKS;c=c+1)begin: observer
  assign capture[c]=^padded[c*32+:32];
 end endgenerate
 reg [5:0] phase;
 always @(posedge logic_clk or negedge rst_n)
  if(!rst_n)begin phase<=0;observation<=0;end
  else begin
   phase<=phase+1'b1;
   if(phase==0)observation<=capture;
   else observation<={1'b0,observation[OBS_CHUNKS-1:1]};
  end
 assign probe_out=observation[0];
 // No acoustic output: internal DAC logic remains visible in observation.
 assign {dac_din,dac_ws,dac_bck,pa_en}=4'd0;
endmodule
