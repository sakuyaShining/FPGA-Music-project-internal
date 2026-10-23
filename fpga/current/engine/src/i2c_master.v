//=============================================================================
// i2c_master.v —— 单主机 I2C 控制器（开漏 SDA/SCL，容忍时钟拉伸）
//
// 设计原则（前两版失败的教训）：
//   · 全部寄存器只在一个 always 块里驱动，不存在同拍竞争
//   · 没有"按步号动态算动作"的表；每一步要发什么字节，在【进入该步时】显式装载
//   · 状态机是扁平的：起始 / 发送 / 重复起始 / 接收 / 停止 / 结束，一眼可读
//
// 事务格式：
//   写：START, dev|W, reg, [data0], [data1], STOP
//   读：START, dev|W, reg, RSTART, dev|R, 读 rd_n 字节（末字节回 NACK）, STOP
//
// req 是空闲时的一拍请求，参数在接受时锁存。读 1–4 字节，写 0–2 字节。
// rd_d[8*i +: 8] 保存第 i 个收到的字节；未使用的高字节为零。
// 拉伸/总线忙超时由 STRETCH_TIMEOUT 限制，失败释放输出并给 done/err。
// 位周期 4 相位：q=0 SCL 低、建立数据；q=1 释放 SCL（从机拉伸则等待）；
//                q=2 SCL 高、采样；q=3 SCL 拉低收尾。
// 引脚开漏：scl_lo / sda_lo 为 1 表示拉低，必须外接上拉。二者皆为寄存器输出
//（C0 教训：三态使能绝不能用组合逻辑推断）。
//=============================================================================
module i2c_master #(
    parameter integer CLK_HZ = 27000000,
    parameter integer SCL_HZ = 100000,
    parameter integer STRETCH_TIMEOUT = CLK_HZ / 100
)(
    input  wire        clk,
    input  wire        rst_n,

    input  wire        req,
    input  wire [6:0]  dev,
    input  wire        rd,
    input  wire [7:0]  reg_a,
    input  wire [15:0] wr_d,
    input  wire [1:0]  wr_n,
    input  wire [2:0]  rd_n,

    output reg  [31:0] rd_d,
    output reg         busy,
    output reg         done,
    output reg         err,

    output reg         scl_lo,
    output reg         sda_lo,
    input  wire        sda_in,
    input  wire        scl_in
);

    localparam integer DIV = (CLK_HZ + SCL_HZ * 4 - 1) / (SCL_HZ * 4);
    localparam integer PW  = 16;

    localparam [2:0] S_IDLE   = 3'd0,
                     S_START  = 3'd1,
                     S_TX     = 3'd2,
                     S_RSTART = 3'd3,
                     S_RX     = 3'd4,
                     S_STOP   = 3'd5,
                     S_END    = 3'd6;

    localparam [3:0] Q_START  = 4'd0,
                     Q_ADDR   = 4'd1,
                     Q_RSTART = 4'd2,
                     Q_ADDRR  = 4'd3,
                     Q_RDATA  = 4'd4,
                     Q_WD0    = 4'd6,
                     Q_WD1    = 4'd7,
                     Q_STOP   = 4'd9;

    reg [6:0] dev_q;
    reg rd_q;
    reg [7:0] reg_a_q;
    reg [15:0] wr_d_q;
    reg [1:0] wr_n_q;
    reg [2:0] rd_n_q;
    reg sda_meta, sda_sync, scl_meta, scl_sync;
    localparam integer TW = (STRETCH_TIMEOUT > 1) ? $clog2(STRETCH_TIMEOUT+1) : 1;
    reg [TW-1:0] stretch_count;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin sda_meta <= 1; sda_sync <= 1; scl_meta <= 1; scl_sync <= 1; end
        else begin sda_meta <= sda_in; sda_sync <= sda_meta; scl_meta <= scl_in; scl_sync <= scl_meta; end
    end

    reg [2:0]    st;
    reg [3:0]    seq;
    reg [3:0]    bitc;
    reg [1:0]    q;
    reg [PW-1:0] ph;
    reg [7:0]    sh;
    reg [2:0]    rxc;
    reg [31:0]   rdbuf;
    reg          ack_nack;   // q=2 采到的应答位（1 = 从机未应答）

    wire ph_last = (ph == DIV[PW-1:0] - 16'd1);
    wire stretch = (~scl_lo) & (~scl_sync);
    wire is_last = (rxc + 3'd1 >= rd_n_q);

    wire start_wait = st == S_START && bitc == 0 && q == 0 && (!sda_sync || !scl_sync);
    wire stalled = start_wait || (q == 1 && stretch);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stretch_count <= 0;
            dev_q <= 0; rd_q <= 0; reg_a_q <= 0; wr_d_q <= 0; wr_n_q <= 0; rd_n_q <= 0;
            st <= S_IDLE; seq <= Q_START; bitc <= 4'd0; q <= 2'd0; ph <= 16'd0;
            sh <= 8'h00; rxc <= 3'd0; rdbuf <= 32'h0; rd_d <= 32'h0;
            scl_lo <= 1'b0; sda_lo <= 1'b0;
            busy <= 1'b0; done <= 1'b0; err <= 1'b0; ack_nack <= 1'b0;
        end else begin
            done <= 1'b0;
            if (st == S_IDLE || !stalled) stretch_count <= 0;
            else stretch_count <= stretch_count + 1'b1;

            if (st == S_IDLE) begin
                scl_lo <= 1'b0; sda_lo <= 1'b0;
                ph <= 16'd0; q <= 2'd0; bitc <= 4'd0; rxc <= 3'd0; rdbuf <= 32'h0;
                if (req) begin
                    dev_q <= dev; rd_q <= rd; reg_a_q <= reg_a;
                    wr_d_q <= wr_d; wr_n_q <= wr_n; rd_n_q <= rd_n;
                    busy <= 1'b1;
                    st   <= S_START;
                    seq  <= Q_START;
                    bitc <= 4'd0; q <= 2'd0; ph <= 16'd0;
                    err  <= 1'b0;              // 只在新请求时清零
                    if ((rd && (rd_n == 0 || rd_n > 4)) || (!rd && wr_n > 2)) begin
                        st <= S_IDLE; busy <= 0; done <= 1; err <= 1;
                    end
                    rd_d <= 32'h0;             // 否则结果会在回到 IDLE 的瞬间被抹掉
                end
            end else begin
                // ---------------- 相位推进 ----------------
                if (ph_last) begin
                    if (stalled) ph <= ph;
                    else begin ph <= 16'd0; q <= q + 2'd1; end
                end else begin
                    ph <= ph + 16'd1;
                end

                // ---------------- 当前相位的输出 ----------------
                case (st)
                    // ================= 起始 / 重复起始 =================
                    S_START, S_RSTART: begin
                        if (bitc == 4'd0) begin
                            if (q == 2'd0)      begin scl_lo <= (st == S_RSTART); sda_lo <= 1'b0; end
                            else if (q == 2'd1) begin scl_lo <= 1'b0; sda_lo <= 1'b0; end
                            else if (q == 2'd2) begin scl_lo <= 1'b0; sda_lo <= 1'b1; end
                            else                begin scl_lo <= 1'b1; sda_lo <= 1'b1; end
                        end else begin
                            scl_lo <= 1'b1; sda_lo <= 1'b1;
                        end
                    end

                    // ================= 发送 =================
                    S_TX: begin
                        if (q == 2'd0) begin
                            scl_lo <= 1'b1;
                            sda_lo <= (bitc == 4'd8) ? 1'b0 : ~sh[7];
                        end else if (q == 2'd1) begin
                            scl_lo <= 1'b0;
                        end else if (q == 2'd2) begin
                            if (bitc == 4'd8 && ph_last) ack_nack <= sda_sync;   // 先锁存，下一步再判
                        end else begin
                            scl_lo <= 1'b1;
                        end
                    end

                    // ================= 接收 =================
                    S_RX: begin
                        if (q == 2'd0) begin
                            scl_lo <= 1'b1;
                            if (bitc == 4'd8) sda_lo <= is_last ? 1'b0 : 1'b1;
                            else              sda_lo <= 1'b0;
                        end else if (q == 2'd1) begin
                            scl_lo <= 1'b0;
                        end else if (q == 2'd3) begin
                            scl_lo <= 1'b1;
                        end
                    end

                    // ================= 停止 =================
                    S_STOP: begin
                        if (bitc == 4'd0) begin
                            scl_lo <= 1'b1; sda_lo <= 1'b1;
                        end else begin
                            if (q == 2'd0)      begin scl_lo <= 1'b1; sda_lo <= 1'b1; end
                            else if (q == 2'd1) begin scl_lo <= 1'b0; sda_lo <= 1'b1; end
                            else                begin scl_lo <= 1'b0; sda_lo <= 1'b0; end
                        end
                    end

                    default: begin scl_lo <= 1'b0; sda_lo <= 1'b0; end
                endcase

                // ---------------- 采样 ----------------
                if (ph_last && q == 2'd2) begin
                    if (st == S_RX && bitc < 4'd8) sh <= {sh[6:0], sda_sync};
                end

                // ---------------- 位周期结束 ----------------
                if (ph_last && q == 2'd3) begin
                    if (st == S_TX || st == S_RX) begin
                        if (bitc == 4'd8) begin
                            bitc <= 4'd0;
                            if (st == S_TX && ack_nack) err <= 1'b1;   // 用锁存值判，避免晚一拍
                            if (st == S_RX) begin
                                rdbuf[rxc*8 +: 8] <= sh;
                                rxc   <= rxc + 3'd1;
                            end

                            if (st == S_TX) begin
                                if (err || ack_nack) begin
                                    st <= S_STOP; seq <= Q_STOP; bitc <= 4'd0;
                                end else begin
                                    case (seq)
                                        Q_START: begin
                                            seq <= Q_ADDR; sh <= reg_a_q; st <= S_TX;
                                        end
                                        Q_ADDR: begin
                                            if (rd_q) begin
                                                st <= S_RSTART; seq <= Q_RSTART; bitc <= 4'd0;
                                            end else if (wr_n_q >= 2'd1) begin
                                                sh <= wr_d_q[7:0]; seq <= Q_WD0;
                                            end else begin
                                                st <= S_STOP; seq <= Q_STOP; bitc <= 4'd0;
                                            end
                                        end
                                        Q_ADDRR: begin
                                            st <= S_RX; seq <= Q_RDATA; bitc <= 4'd0; rxc <= 3'd0;
                                        end
                                        Q_WD0: begin
                                            if (wr_n_q == 2'd2) begin sh <= wr_d_q[15:8]; seq <= Q_WD1; end
                                            else begin st <= S_STOP; seq <= Q_STOP; bitc <= 4'd0; end
                                        end
                                        Q_WD1: begin
                                            st <= S_STOP; seq <= Q_STOP; bitc <= 4'd0;
                                        end
                                        default: begin
                                            st <= S_STOP; seq <= Q_STOP; bitc <= 4'd0;
                                        end
                                    endcase
                                end
                            end else begin
                                if (is_last) begin
                                    st <= S_STOP; seq <= Q_STOP; bitc <= 4'd0;
                                    rd_d <= rdbuf;
                                    rd_d[rxc*8 +: 8] <= sh;
                                end
                            end
                        end else begin
                            bitc <= bitc + 4'd1;
                            if (st == S_TX) sh <= {sh[6:0], 1'b0};
                        end
                    end else begin
                        if (bitc == 4'd1) begin
                            bitc <= 4'd0;
                            if (st == S_START) begin
                                st <= S_TX; seq <= Q_START; sh <= {dev_q, 1'b0};
                            end else if (st == S_RSTART) begin
                                st <= S_TX; seq <= Q_ADDRR; sh <= {dev_q, 1'b1};
                            end else if (st == S_STOP) begin
                                st <= S_END;
                            end
                        end else begin
                            bitc <= bitc + 4'd1;
                        end
                    end
                end

                // 时钟拉伸或启动总线忙超过限额：释放开漏输出，报告失败。
                if (stalled && stretch_count >= STRETCH_TIMEOUT-1) begin
                    err <= 1; st <= S_END; scl_lo <= 0; sda_lo <= 0;
                end

                // ---------------- 结束 ----------------
                if (st == S_END) begin
                    busy <= 1'b0; done <= 1'b1;
                    scl_lo <= 1'b0; sda_lo <= 1'b0;
                    st <= S_IDLE;
                end
            end
        end
    end

endmodule
