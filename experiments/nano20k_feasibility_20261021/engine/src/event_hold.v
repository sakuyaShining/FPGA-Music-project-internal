// event_hold: power-of-two ring FIFO with a registered, stable output head.
// Transfers occur on in_valid && in_ready and out_valid && out_ready.
// Empty -> nonempty incurs one prefetch clock; subsequent output transfers
// can occur on consecutive clocks. Full input waits one clock after a pop.
//
// overflow is a saturating count of cycles with in_valid && !in_ready.
// For unthrottled one-clock pulse sources this counts discarded events.
// A producer that holds valid while waiting does NOT lose that event, although
// its blocked cycles are counted. The top-level shared FIFO gates its valid
// with ready so its diagnostic does not count backpressure as discarded pulses.
// DEPTH must be a power of two >= 2. level includes the registered output head.
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
                if (overflow != 16'hffff) overflow <= overflow + 16'd1;   // count rejected pulse / blocked cycle
        end
    end

    //-------------------------------------------------------------------------
    // 出队（读指针）：严格先进先出
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) rd_ptr <= {(AW+1){1'b0}};
        else if (out_valid && out_ready) rd_ptr <= rd_ptr + 1'b1;
    end

    // Registered head: after a transfer, read the NEXT pointer and invalidate
    // immediately when the last queued item is consumed. Empty -> nonempty
    // takes one extra clock so a new write never exposes uninitialized RAM.
    reg              ov_r, oon_r;
    reg [NB-1:0]     onote_r;
    reg [VB-1:0]     ovel_r;
    wire [AW:0]     head_ptr = rd_ptr + {{AW{1'b0}}, (ov_r && out_ready)};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ov_r <= 1'b0; oon_r <= 1'b0; onote_r <= {NB{1'b0}}; ovel_r <= {VB{1'b0}};
        end
        else begin
            ov_r <= (head_ptr != wr_ptr);
            if (head_ptr != wr_ptr) begin
                oon_r   <= q_on  [head_ptr[AW-1:0]];
                onote_r <= q_note[head_ptr[AW-1:0]];
                ovel_r  <= q_vel [head_ptr[AW-1:0]];
            end
        end
    end

    assign out_valid = ov_r;
    assign out_on    = oon_r;
    assign out_note  = onote_r;
    assign out_vel   = ovel_r;
    assign level     = wr_ptr - rd_ptr;

endmodule
