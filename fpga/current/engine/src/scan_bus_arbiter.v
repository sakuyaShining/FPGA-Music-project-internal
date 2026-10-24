//=============================================================================
// scan_bus_arbiter.v —— 扫描总线（SCK 共享）仲裁器
//
// 【为什么需要这个模块】
//   `rc_mux_scan` 内部的 `scan_shift595` 在 `word_valid` 时拉高 `bus_request`，
//   然后等外部给 `bus_grant` 才开始打 SCK。原设计里这个 grant 从来没接过：
//   所有 testbench（check_joint.py / check_joint_variant.py）直接把
//   `scan_bus_grant` 常量绑成 1'b1 —— 也就是说"永远授权"，单请求者时看不出问题。
//
//   但载板上有两个东西要打 SCK：
//     1) 74LV595（输出侧，写 ADDR / CHARGE / DISABLE 字）
//     2) 74LV165（输入侧，读按键与预置状态）
//   两者共用 `BUS_SCK`。若同时驱动，SCK 会变成两个时钟源的线与，595 与 165
//   同时移位 ⇒ 595 的移位寄存器被 165 的时钟打乱、165 读到的位序错位。
//
// 【设计约束：持有到释放，不抢占】
//   `scan_shift595` 里有这一行：
//       if (state>=LOW && !bus_grant) grant_error <= 1;
//   意思是"一旦开始打 SCK，中途撤掉 grant 就记一次错误"。
//   所以本仲裁器**不允许**抢占正在进行的传输：一旦 grant 给出，必须等请求方
//   自己撤销 `request` 才释放。这条比"公平性"优先级更高。
//
// 【优先级】
//   固定优先级，request[0] 最高。
//   在 sensor_frontend_board 里 request[0] 接 165（低频、单次、必须及时），
//   request[1] 接 595（高频、可等，因为 rc_mux_scan 有 waiting 状态机兜着）。
//   若反过来，595 在扫描时会持续请求，165 有被长期压住的风险。
//
// 【为什么不做轮转】
//   轮转需要记住"上次给到谁"，在 2 个请求者时收益很小，而固定优先级配合
//   "165 优先"已经能保证 165 的延迟上界 = 一次 165 读取（约 136 周期）。
//   少一个状态就少一类上板才发现的错。
//=============================================================================

`timescale 1ns/1ps

module scan_bus_arbiter #(
    parameter integer REQ = 2
)(
    input  wire             clk,
    input  wire             rst_n,
    input  wire [REQ-1:0]   request,    // 各请求者的 bus_request
    output reg  [REQ-1:0]   grant       // 各请求者的 bus_grant（one-hot 或全 0）
);

    // holder：当前持有者（one-hot），全 0 = 空闲
    // 单独存一份而不是直接看 grant，是因为释放条件取决于 request，
    // 而 grant 在释放那一拍还要保持为 0 一整个周期。
    reg [REQ-1:0] holder;
    reg [REQ-1:0] winner;

    integer i;

    // 固定优先级：倒序扫描，最后赋值的是 i=0 ⇒ request[0] 优先级最高
    always @(*) begin
        winner = {REQ{1'b0}};
        for (i = REQ-1; i >= 0; i = i - 1)
            if (request[i])
                winner = {{(REQ-1){1'b0}}, 1'b1} << i;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            holder <= {REQ{1'b0}};
            grant  <= {REQ{1'b0}};
        end else if (|holder) begin
            // 持有中：只要请求方还没撤销，就一直给
            if (|(request & holder)) begin
                grant <= holder;
            end else begin
                // 请求方撤销 ⇒ 同拍释放，下一拍可授权给别人
                holder <= {REQ{1'b0}};
                grant  <= {REQ{1'b0}};
            end
        end else if (|request) begin
            // 空闲：按固定优先级选一个
            holder <= winner;
            grant  <= winner;
        end
    end

endmodule
