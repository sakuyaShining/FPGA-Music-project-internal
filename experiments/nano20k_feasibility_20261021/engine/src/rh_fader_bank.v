// Snapshot-based touch -> fader targets. No audio, preset or SPI side effects.
// LSB-packed arrays: element i occupies [i*WIDTH +: WIDTH].
// Prototype geometry: nearest means horizontal distance; radius is inclusive.
// On-axis touches participate in both sides. Distance ties use lowest touch ID.
module rh_fader_bank #(
    parameter integer NF = 8,
    parameter integer NT = 5,
    parameter integer XW = 10,
    parameter integer YW = 10,
    parameter integer IDW = 4,
    parameter integer RESET_Y = 479
)(
    input wire clk, rst_n,
    input wire frame_valid,
    output wire frame_ready,
    input wire [NT-1:0] touch_active,
    input wire [NT*XW-1:0] touch_x,
    input wire [NT*YW-1:0] touch_y,
    input wire [NT*IDW-1:0] touch_id,
    input wire [NF*XW-1:0] fader_x,
    input wire [NF*XW-1:0] zone_lo, zone_hi,
    input wire [XW-1:0] radius,
    input wire [YW-1:0] y_min, y_max,
    input wire restore_valid,
    input wire [NF*YW-1:0] restore_y,
    output reg [NF*YW-1:0] target_y,
    output reg [NF-1:0] driven,
    output reg [NF-1:0] left_present, right_present,
    output reg [NF*IDW-1:0] left_id, right_id,
    output reg frame_done, restore_done, config_error
);
    localparam FW = (NF < 2) ? 1 : $clog2(NF);
    localparam TW = (NT < 2) ? 1 : $clog2(NT);
    localparam IDLE=2'd0, SCAN=2'd1, APPLY=2'd2, COMMIT=2'd3;
    reg [1:0] state;
    reg [FW-1:0] fi;
    reg [TW-1:0] ti;
    reg [NT-1:0] active_q;
    reg [NT*XW-1:0] tx_q;
    reg [NT*YW-1:0] ty_q;
    reg [NT*IDW-1:0] id_q;
    reg [NF*XW-1:0] fx_q;
    reg [NF*XW-1:0] zlo_q, zhi_q;
    reg [XW-1:0] radius_q;
    reg [YW-1:0] lo_q, hi_q;
    reg lf, rf;
    reg [XW-1:0] ld, rd;
    reg [YW-1:0] ly, ry;
    reg [IDW-1:0] lid, rid;
    reg [NF*YW-1:0] work_y;
    reg [NF-1:0] work_left, work_right;
    reg [NF*IDW-1:0] work_lid, work_rid;

    wire [XW-1:0] x = tx_q[ti*XW +: XW];
    wire [YW-1:0] y = ty_q[ti*YW +: YW];
    wire [IDW-1:0] id = id_q[ti*IDW +: IDW];
    wire [XW-1:0] axis = fx_q[fi*XW +: XW];
    wire [XW-1:0] zone_start = zlo_q[fi*XW +: XW];
    wire [XW-1:0] zone_end = zhi_q[fi*XW +: XW];
    wire [XW-1:0] distance_x = (x <= axis) ? axis-x : x-axis;
    wire eligible = active_q[ti] && x >= zone_start && x < zone_end && distance_x <= radius_q;
    // Zones are ordered disjoint half-open intervals; invalid frames are rejected.
    wire [NF-1:0] geometry_ok;
    genvar g;
    generate for (g=0; g<NF; g=g+1) begin: check_geometry
        wire contains_axis = zone_lo[g*XW +: XW] <= fader_x[g*XW +: XW] &&
                             fader_x[g*XW +: XW] < zone_hi[g*XW +: XW];
        if (g==0) assign geometry_ok[g] = contains_axis;
        else assign geometry_ok[g] = contains_axis && zone_hi[(g-1)*XW +: XW] <= zone_lo[g*XW +: XW];
    end endgenerate
    wire [YW:0] midpoint_sum = {1'b0, ly} + {1'b0, ry};
    wire [YW-1:0] chosen_y = (lf && rf) ? midpoint_sum[YW:1] : (lf ? ly : ry);
    wire [YW-1:0] bounded_y = (chosen_y < lo_q) ? lo_q : ((chosen_y > hi_q) ? hi_q : chosen_y);
    assign frame_ready = state == IDLE && !restore_valid;

    integer j;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE; fi <= 0; ti <= 0;
            active_q <= 0; tx_q <= 0; ty_q <= 0; id_q <= 0;
            fx_q <= 0; zlo_q <= 0; zhi_q <= 0; radius_q <= 0; lo_q <= 0; hi_q <= 0;
            lf <= 0; rf <= 0; ld <= 0; rd <= 0;
            ly <= 0; ry <= 0; lid <= 0; rid <= 0;
            target_y <= {NF{RESET_Y[YW-1:0]}};
            work_y <= {NF{RESET_Y[YW-1:0]}};
            driven <= 0; left_present <= 0; right_present <= 0;
            left_id <= 0; right_id <= 0;
            work_left <= 0; work_right <= 0; work_lid <= 0; work_rid <= 0;
            frame_done <= 0; restore_done <= 0; config_error <= 0;
        end else begin
            frame_done <= 0; restore_done <= 0; config_error <= 0;
            // Explicit restore aborts an in-flight frame: no stale later commit.
            // This sets targets only. Audio-side smoothing is a separate adapter.
            if (restore_valid) begin
                if (y_min > y_max) config_error <= 1;
                else begin
                    for (j=0; j<NF; j=j+1)
                        target_y[j*YW +: YW] <=
                            (restore_y[j*YW +: YW] < y_min) ? y_min :
                            ((restore_y[j*YW +: YW] > y_max) ? y_max : restore_y[j*YW +: YW]);
                    state <= IDLE;
                    driven <= 0; left_present <= 0; right_present <= 0;
                    left_id <= 0; right_id <= 0;
                    restore_done <= 1;
                end
            end else case (state)
                IDLE: if (frame_valid) begin
                    if (y_min > y_max || !(&geometry_ok)) config_error <= 1;
                    else begin
                        active_q <= touch_active; tx_q <= touch_x; ty_q <= touch_y; id_q <= touch_id;
                        fx_q <= fader_x; zlo_q <= zone_lo; zhi_q <= zone_hi;
                        radius_q <= radius; lo_q <= y_min; hi_q <= y_max;
                        work_y <= target_y;
                        work_left <= 0; work_right <= 0; work_lid <= 0; work_rid <= 0;
                        fi <= 0; ti <= 0; lf <= 0; rf <= 0;
                        state <= SCAN;
                    end
                end
                SCAN: begin
                    if (eligible && x <= axis && (!lf || distance_x < ld || (distance_x == ld && id < lid))) begin
                        lf <= 1; ld <= distance_x; ly <= y; lid <= id;
                    end
                    if (eligible && x >= axis && (!rf || distance_x < rd || (distance_x == rd && id < rid))) begin
                        rf <= 1; rd <= distance_x; ry <= y; rid <= id;
                    end
                    if (ti == NT-1) state <= APPLY;
                    else ti <= ti + 1'b1;
                end
                APPLY: begin
                    if (lf || rf) work_y[fi*YW +: YW] <= bounded_y;
                    work_left[fi] <= lf; work_right[fi] <= rf;
                    work_lid[fi*IDW +: IDW] <= lf ? lid : {IDW{1'b0}};
                    work_rid[fi*IDW +: IDW] <= rf ? rid : {IDW{1'b0}};
                    if (fi == NF-1) state <= COMMIT;
                    else begin
                        fi <= fi + 1'b1; ti <= 0; lf <= 0; rf <= 0; state <= SCAN;
                    end
                end
                COMMIT: begin
                    target_y <= work_y;
                    left_present <= work_left; right_present <= work_right;
                    driven <= work_left | work_right;
                    left_id <= work_lid; right_id <= work_rid;
                    frame_done <= 1; state <= IDLE;
                end
                default: state <= IDLE;
            endcase
        end
    end
endmodule
