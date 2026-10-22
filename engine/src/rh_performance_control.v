// Ordered pipeline: complete touch report -> faders -> gain targets -> ramp.
// Coordinates/range match the replaceable 800x480 audition panel configuration.
module rh_performance_control(
    input wire clk,rst_n,sample_ce,
    input wire touch_valid,
    output wire touch_ready,
    input wire [4:0] touch_active,
    input wire [49:0] touch_x,touch_y,
    input wire [19:0] touch_id,
    input wire [9:0] radius,
    input wire [47:0] part_to_control,
    input wire [9:0] slew_step,
    input wire restore_valid,
    output wire [79:0] fader_y,
    output wire [159:0] current_gain,
    output wire frame_done,gain_done,error
);
    localparam IDLE=2'd0,GEOMETRY=2'd1,MAP=2'd2,WAIT_GAIN=2'd3;
    reg [1:0] state;
    reg [47:0] map_q;
    wire panel_ready,panel_done,panel_error;
    wire mapper_ready,mapper_valid,mapper_error;
    wire target_ready,tick_overrun;
    wire [159:0] targets;
    wire map_valid=state==MAP;
    assign touch_ready=state==IDLE&&panel_ready&&mapper_ready&&!restore_valid;
    assign frame_done=mapper_valid&&target_ready;
    assign error=panel_error|mapper_error|tick_overrun;
    rh_fader_panel panel(.clk(clk),.rst_n(rst_n),.frame_valid(touch_valid&&touch_ready),.frame_ready(panel_ready),
        .touch_active(touch_active),.touch_x(touch_x),.touch_y(touch_y),.touch_id(touch_id),.radius(radius),
        .restore_valid(restore_valid),.target_y(fader_y),.driven(),.frame_done(panel_done),.restore_done(),.config_error(panel_error));
    rh_fader_gain_map mapper(.clk(clk),.rst_n(rst_n),.fader_valid(map_valid),.fader_ready(mapper_ready),
        .fader_y(fader_y),.part_to_control(map_q),.restore_valid(restore_valid),.gain_valid(mapper_valid),
        .gain_ready(target_ready),.gain_target(targets),.map_error(mapper_error));
    rh_timbre_slew slew(.clk(clk),.rst_n(rst_n),.sample_ce(sample_ce),.target_valid(mapper_valid),.target_ready(target_ready),
        .target_gain(targets),.slew_step(slew_step),.restore_valid(restore_valid),.current_gain(current_gain),
        .bank_done(gain_done),.tick_overrun(tick_overrun));
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin state<=IDLE;map_q<=0;end
        else if(restore_valid)state<=IDLE;
        else case(state)
            IDLE:if(touch_valid&&touch_ready)begin map_q<=part_to_control;state<=GEOMETRY;end
            GEOMETRY:if(panel_error)state<=IDLE;else if(panel_done)state<=MAP;
            MAP:if(mapper_ready)state<=WAIT_GAIN;
            WAIT_GAIN:if(mapper_error||frame_done)state<=IDLE;
            default:state<=IDLE;
        endcase
    end
endmodule
