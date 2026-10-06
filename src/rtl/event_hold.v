//=============================================================================
// event_hold.v —— 演奏事件的「待处理队列 + 接收确认」
//
// 【它解决什么】
//   note_map 一次装载要占用约 20 拍（≈0.74 µs）。在这段时间里到达的事件，
//   如果只是"单拍脉冲"，就会被静默丢掉 —— 表现是丢音，以及更糟的
//   **丢 note-off 挂音**。
//
//   实测分工（见 docs/02-技术方案/33-审计复核记录 §3）：
//     · pads 路径【已经安全】：pad_scan 用 8 位待发位图 + note_busy 反压，
//       不丢、只是推迟 ⇒ **不要去改它**。
//     · UART(0x61) / 定序器 / 排针 ev_* 都是【单拍脉冲且不受反压】⇒ 忙时被忽略。
//   本模块就是给这三类"无反压源"补上待处理与接收确认。
//
// 【接口语义（标准 ready/valid）】
//     源端：把事件放上 in_*，并**保持 in_valid 直到看见 in_ready=1**（"接收确认"）。
//           只发一拍就不管的源端，本模块救不了它 —— 这是源端的责任。
//     本模块：in_ready=1 的那一拍把事件收进队列。
//     消费端：out_valid=1 表示队首有事件；out_ready=1 的那一拍取走它。
//
// 【"不丢 note-off"这条保证来自哪里（设计说明，重要）】
//   来自**源端被反压后仍然持有事件**，而不是来自出队顺序。
//   只要 in_valid 一直举着直到 in_ready=1，事件就必然进队、必然出队，
//   与它是 note-on 还是 note-off 无关。
//   ⇒ 因此本模块采用**最朴素的环形 FIFO（严格先进先出）**，不做"note-off 优先"
//     的重排。理由是可验证性：环形 FIFO 的空/满/顺序都只有一种解释，
//     而"带优先级的紧凑队列"要额外证明"重排不会破坏配对"。
//     （第一版曾试过紧凑式 + off 优先，出队顺序被搅乱且出现重复项 ——
//      定位成本远高于它带来的那点收益。**简单到显然正确的结构更容易守住。**）
//
// 【溢出怎么办】
//   队列满时 in_ready=0 ⇒ 合规源端继续持有，不丢。
//   若源端违反协议（单拍脉冲硬灌），本模块记 overflow 计数，**不假装没发生** ——
//   验收判据就是读这个计数（src/sim/tb_evhold.v 的 H4）。
//
// 【参数】DEPTH 建议取 2 的幂（便于空/满判断）。AW+1 位指针用于区分空与满。
//=============================================================================
`timescale 1ns/1ps

module event_hold #(
    parameter DEPTH = 8,
    parameter NB    = 7,        // 音符号位宽
    parameter VB    = 4         // 力度位宽
)(
    input  wire            clk,
    input  wire            rst_n,

    // ---- 源端口（已仲裁好的单个事件流）----
    input  wire            in_valid,
    input  wire            in_on,
    input  wire [NB-1:0]   in_note,
    input  wire [VB-1:0]   in_vel,
    output wire            in_ready,     // 接收确认：1 = 本拍收下

    // ---- 消费端口（接 note_map 侧）----
    output wire            out_valid,
    output wire            out_on,
    output wire [NB-1:0]   out_note,
    output wire [VB-1:0]   out_vel,
    input  wire            out_ready,    // 消费拍

    // ---- 诊断 ----
    output wire [$clog2(DEPTH+1)-1:0] level,
    output reg  [15:0]     overflow
);

    localparam AW = $clog2(DEPTH);

    reg              q_on   [0:DEPTH-1];
    reg [NB-1:0]     q_note [0:DEPTH-1];
    reg [VB-1:0]     q_vel  [0:DEPTH-1];

    reg [AW:0]       wr_ptr, rd_ptr;

    wire full  = ((wr_ptr - rd_ptr) == DEPTH[AW:0]);
    wire empty = (wr_ptr == rd_ptr);

    assign in_ready = ~full;

    //-------------------------------------------------------------------------
    // 入队（写指针）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr   <= {(AW+1){1'b0}};
            overflow <= 16'd0;
        end
        else if (in_valid) begin
            if (in_ready) begin
                q_on  [wr_ptr[AW-1:0]] <= in_on;
                q_note[wr_ptr[AW-1:0]] <= in_note;
                q_vel [wr_ptr[AW-1:0]] <= in_vel;
                wr_ptr <= wr_ptr + 1'b1;
            end
            else
                overflow <= overflow + 16'd1;   // 源端违反协议：如实记一笔
        end
    end

    //-------------------------------------------------------------------------
    // 出队（读指针）：严格先进先出
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rd_ptr <= {(AW+1){1'b0}};
        else if (out_valid && out_ready) rd_ptr <= rd_ptr + 1'b1;
    end

    //   输出**寄存一级**再给下游。
    //   为什么：下游是 tdm_top 的"事件源优先级 mux + 寄存器"，
    //   若本模块直接给出组合输出，等于把"寄存器堆读 + 队列读"串成一条长链；
    //   本项目已经为同类问题栽过（加定序器后 SETUP slack 只剩 +0.105 ns）。
    //
    //   ★★ out_valid 必须与数据【一起】寄存，且判定用的是"读指针所指那一项
    //      在上一拍是否有效"：
    //          valid_r <= ~empty | (out_valid & out_ready)
    //      踩过的坑：先写成 `out_valid = ~empty`（组合）而数据寄存 ——
    //      当队列从【空】变为【有】的那一拍，~empty 立刻为 1，但寄存后的数据
    //      还是上一拍的旧值（此时 rd_ptr 恰好指向刚写入的那一项，数据尚未被采到），
    //      于是消费者会读到一个**错位的条目**。
    //      实测症状非常有欺骗性：note 号完全正确、但 on/off 标志整体错开
    //      （第 1 条本应 off 却报 on，序列整体位移）。定位方式就是看"号对、标志错"。
    //      正确语义：数据可用的那一拍才宣告 valid。
    reg              ov_r, oon_r;
    reg [NB-1:0]     onote_r;
    reg [VB-1:0]     ovel_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ov_r <= 1'b0; oon_r <= 1'b0; onote_r <= {NB{1'b0}}; ovel_r <= {VB{1'b0}};
        end
        else begin
            ov_r    <= ~empty | (ov_r & out_ready);
            oon_r   <= q_on  [rd_ptr[AW-1:0]];
            onote_r <= q_note[rd_ptr[AW-1:0]];
            ovel_r  <= q_vel [rd_ptr[AW-1:0]];
        end
    end

    assign out_valid = ov_r;
    assign out_on    = oon_r;
    assign out_note  = onote_r;
    assign out_vel   = ovel_r;
    assign level     = wr_ptr - rd_ptr;

endmodule
