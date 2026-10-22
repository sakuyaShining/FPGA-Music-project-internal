// Resource/board-integration wrapper for an 800px, 8-zone example panel.
// Geometry is compile-time; radius remains adjustable. No pinout or audio binding.
module rh_fader_panel #(
    parameter integer NF=8,
    parameter integer NT=5,
    parameter integer PANEL_WIDTH=800,
    parameter integer Y_MIN=52,
    parameter integer Y_MAX=420
)(
    input wire clk,rst_n,frame_valid,
    output wire frame_ready,
    input wire [NT-1:0] touch_active,
    input wire [NT*10-1:0] touch_x,touch_y,
    input wire [NT*4-1:0] touch_id,
    input wire [9:0] radius,
    input wire restore_valid,
    output wire [NF*10-1:0] target_y,
    output wire [NF-1:0] driven,
    output wire frame_done,restore_done,config_error
);
    wire [NF*10-1:0] axes,zlo,zhi,initial_y;
    genvar i;
    generate for(i=0;i<NF;i=i+1)begin: panel_geometry
        localparam integer LO=i*PANEL_WIDTH/NF;
        localparam integer HI=(i+1)*PANEL_WIDTH/NF;
        localparam integer MID=(LO+HI)/2;
        assign axes[i*10+:10]=MID[9:0];
        assign zlo[i*10+:10]=LO[9:0];
        assign zhi[i*10+:10]=HI[9:0];
        assign initial_y[i*10+:10]=Y_MAX[9:0];
    end endgenerate
    rh_fader_bank #(.NF(NF),.NT(NT),.RESET_Y(Y_MAX)) bank(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),
        .touch_active(touch_active),.touch_x(touch_x),.touch_y(touch_y),.touch_id(touch_id),
        .fader_x(axes),.zone_lo(zlo),.zone_hi(zhi),.radius(radius),
        .y_min(Y_MIN[9:0]),.y_max(Y_MAX[9:0]),.restore_valid(restore_valid),.restore_y(initial_y),
        .target_y(target_y),.driven(driven),.frame_done(frame_done),.restore_done(restore_done),.config_error(config_error),
        .left_present(),.right_present(),.left_id(),.right_id()
    );
endmodule
