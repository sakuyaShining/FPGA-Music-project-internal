// Candidate eight-fader follow kernel; NOT connected to tdm_ship yet.
// Targets are normalized positions prepared by a separate touch mapper.
// No valid target: hold CURRENT value, never finish chasing a stale target.
// follow_step is distance per control tick, not touch transport latency.
module right_fader_follow #(
    parameter integer N = 8,
    parameter integer W = 12
)(
    input wire clk,
    input wire rst_n,
    input wire control_tick,
    input wire [N-1:0] target_valid,
    input wire [N*W-1:0] target_flat,
    input wire [W-1:0] follow_step,
    input wire [N-1:0] load_mask,
    input wire [N*W-1:0] load_flat,
    output reg [N*W-1:0] current_flat
);
    integer i;
    reg [W-1:0] current_value;
    reg [W-1:0] target_value;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) current_flat <= {N*W{1'b0}};
        else begin
            for (i = 0; i < N; i = i + 1) begin
                if (load_mask[i]) current_flat[i*W +: W] <= load_flat[i*W +: W];
                else if (control_tick && target_valid[i] && follow_step != 0) begin
                    current_value = current_flat[i*W +: W];
                    target_value = target_flat[i*W +: W];
                    if (target_value > current_value) begin
                        if (target_value - current_value <= follow_step)
                            current_flat[i*W +: W] <= target_value;
                        else current_flat[i*W +: W] <= current_value + follow_step;
                    end else if (target_value < current_value) begin
                        if (current_value - target_value <= follow_step)
                            current_flat[i*W +: W] <= target_value;
                        else current_flat[i*W +: W] <= current_value - follow_step;
                    end
                end
            end
        end
    end
endmodule
