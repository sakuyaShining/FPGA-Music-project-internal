//=============================================================================
// sensor_sim.v —— 传感器仿真器（测试用，不上板）
//
// 【为什么需要它】
//   交互层核心只认一条通用测量总线（m1/m2/pads）。真实器件还没定，
//   但这条总线必须能"被驱动"才能把 M1/M9 的判据做完。
//   本模块就是那条总线的**信号发生器**：它模拟几种典型的人手动作/器件时序。
//
// 【★ 将来怎么替换】
//   上板时把本模块换成真正的解码模块（例如 sensor_range.v / sensor_touch.v），
//   它们输出的仍是同一条总线 ⇒ perf_ctrl 与所有判据一个字都不用改。
//   这就是"器件未定也能先把交互层做完"的关键。
//
// 【模式】（由 tb 或将来的自检模式选择）
//   0 静止：m1/m2 保持不变，只持续给测量脉冲
//   1 慢扫：m1 每次减 m1_step（模拟手慢慢靠近）→ 只改"选音"维度
//   2 挥手：每 4 次测量跳一次 m1_step（脉冲式快速动作）→ 只改"变化率/力度"
//   3 触摸：pads 依次按下-松开
//   4 双维：m1 减小 且 m2 减小（用于验证锁存：触发后改维度不该改变已发的音）
//   5 只改力度：m1 不动，m2 每次加 m2_step
//=============================================================================

`timescale 1ns/1ps

module sensor_sim #(
    parameter integer PERIOD = 200,       // 每 PERIOD 个时钟产生一次"新测量"
    parameter integer PAD_ON = 300,       // pads 按下持续时钟数
    parameter integer PAD_OFF = 200       // pads 松开持续时钟数
)(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        run,

    input  wire [2:0]  mode,
    input  wire [15:0] m1_start,
    input  wire [15:0] m1_step,
    input  wire [15:0] m2_start,
    input  wire [15:0] m2_step,
    input  wire [7:0]  n_upd,             // 总共产生多少次测量

    output reg  [15:0] m1_raw,
    output reg  [15:0] m2_raw,
    output reg         m1_vld,
    output reg         m2_vld,
    output reg  [3:0]  pads
);

    integer cnt;          // 采样节拍
    integer k;            // 第几次测量

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            cnt <= 0; k <= 0;
            m1_raw <= 16'd0; m2_raw <= 16'd0;
            m1_vld <= 1'b0; m2_vld <= 1'b0;
        end
        else begin
            m1_vld <= 1'b0;
            m2_vld <= 1'b0;

            if (!run) begin
                cnt <= 0; k <= 0;
            end
            else if (cnt == PERIOD - 1) begin
                cnt <= 0;
                if (k < n_upd) begin
                    m1_vld <= 1'b1;
                    m2_vld <= 1'b1;
                    case (mode)
                        3'd0: begin end                                   // 静止
                        3'd1: m1_raw <= m1_start - k * m1_step;            // 慢扫
                        3'd2: begin                                        // 挥手
                            if (k % 4 == 3) m1_raw <= m1_start - (k / 4 + 1) * m1_step;
                        end
                        3'd4: begin                                        // 双维同时变
                            m1_raw <= m1_start - k * m1_step;
                            m2_raw <= m2_start - k * m2_step;
                        end
                        3'd5: m2_raw <= m2_start + k * m2_step;            // 只改力度
                        default: begin end
                    endcase
                    k <= k + 1;
                end
            end
            else cnt <= cnt + 1;
        end
    end

    //-------------------------------------------------------------------------
    // 触摸序列用一个独立的简单状态机（避免和测量节拍纠缠）
    //   周期：pad_i 按下 PAD_ON 拍 → 松开 PAD_OFF 拍 → 换下一个 pad
    //-------------------------------------------------------------------------
    localparam S_IDLE = 2'd0, S_ON = 2'd1, S_OFF = 2'd2;
    reg [1:0]  ps;
    integer    pt;
    integer    pidx;      // 当前按第几个 pad

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ps <= S_IDLE; pt <= 0; pidx <= 0; pads <= 4'd0;
        end
        else if (!run || mode != 3'd3) begin
            ps <= S_IDLE; pt <= 0; pidx <= 0; pads <= 4'd0;
        end
        else begin
            case (ps)
                S_IDLE: begin
                    if (pidx < 4) begin
                        pads[pidx] <= 1'b1;
                        pt <= PAD_ON;
                        ps <= S_ON;
                    end
                end
                S_ON: begin
                    if (pt != 0) pt <= pt - 1;
                    else begin
                        pads[pidx] <= 1'b0;
                        pt <= PAD_OFF;
                        ps <= S_OFF;
                    end
                end
                S_OFF: begin
                    if (pt != 0) pt <= pt - 1;
                    else begin
                        pidx <= pidx + 1;
                        ps   <= S_IDLE;
                    end
                end
                default: ps <= S_IDLE;
            endcase
        end
    end

endmodule
