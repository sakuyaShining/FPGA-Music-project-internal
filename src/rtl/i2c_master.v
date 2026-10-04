//=============================================================================
// i2c_master.v —— 单主机 I2C 控制器（开漏 SDA/SCL，容忍时钟拉伸）
//
// 用途：读取 MPR121 一类电容触摸控制器。纯 RTL，无软核参与发声通路。
//
// 两层结构：
//   · 事务脚本：由 rd / wr_n 决定总共要走哪些步，动作表与字节表都用
//     【带参数的函数】从"步号"算出，因此不存在读写同一拍的竞争。
//   · 位引擎：只负责执行一个原子动作（起始 / 停止 / 发一字节并收 ACK /
//     收一字节并回 ACK 或 NACK）。
//
// 事务格式（一次 req 只做一件）：
//   写：START, dev|W, reg, [data0], [data1], STOP
//   读：START, dev|W, reg, RSTART, dev|R, 读 rd_n 字节（末字节回 NACK）, STOP
//
// 位周期 4 相位：q=0 SCL 低建数据；q=1 释放 SCL（从机拉伸则等待）；
//                q=2 SCL 高采样；q=3 SCL 拉低收尾。
// 引脚开漏：scl_lo / sda_lo 为 1 表示拉低，必须外接上拉。
//=============================================================================
module i2c_master #(
    parameter integer CLK_HZ = 27000000,
    parameter integer SCL_HZ = 100000
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

    // 原子动作
    localparam [2:0] A_START = 3'd0,
                     A_TX    = 3'd1,
                     A_RSTART= 3'd2,
                     A_RX    = 3'd3,
                     A_STOP  = 3'd4,
                     A_END   = 3'd5;

    // 位引擎模式
    localparam [1:0] M_TX = 2'd0, M_RX = 2'd1, M_START = 2'd2, M_STOP = 2'd3;

    //-------------------------------------------------------------------------
    // 事务脚本：动作表与字节表（纯函数，输入是步号）
    //-------------------------------------------------------------------------
    function [2:0] act_of;
        input [4:0] s;
        input       is_rd;
        input [1:0] wn;
        input [2:0] rn;
        begin
            if      (s == 5'd0) act_of = A_START;
            else if (s == 5'd1) act_of = A_TX;          // dev|W
            else if (s == 5'd2) act_of = A_TX;          // reg_a
            else if (is_rd) begin
                if      (s == 5'd3)                       act_of = A_RSTART;
                else if (s == 5'd4)                       act_of = A_TX;   // dev|R
                else if (s >= 5'd5 && s < (5'd5 + rn))    act_of = A_RX;
                else                                      act_of = A_STOP;
            end else begin
                if      (wn >= 2'd1 && s == 5'd3)         act_of = A_TX;   // data0
                else if (wn == 2'd2 && s == 5'd4)         act_of = A_TX;   // data1
                else                                      act_of = A_STOP;
            end
        end
    endfunction

    function [7:0] byte_of;
        input [4:0]  s;
        input [6:0]  d;
        input [7:0]  ra;
        input [15:0] wd;
        begin
            if      (s == 5'd1) byte_of = {d, 1'b0};
            else if (s == 5'd2) byte_of = ra;
            else if (s == 5'd4) byte_of = {d, 1'b1};
            else if (s == 5'd3) byte_of = wd[7:0];
            else                byte_of = wd[15:8];
        end
    endfunction

    //-------------------------------------------------------------------------
    // 状态
    //-------------------------------------------------------------------------
    reg [4:0]  st;         // 当前步号
    reg [4:0]  st_n;       // 下一步号
    reg [2:0]  act;        // 当前动作
    reg [2:0]  act_n;      // 下一个动作
    reg [1:0]  mode;       // 位引擎模式
    reg [7:0]  txb;        // 本次要发的字节
    reg [7:0]  sh;         // 发送移位
    reg [7:0]  rxsh;       // 接收移位
    reg [3:0]  rxc;        // 已接收字节数（用于判末字节）

    reg [PW-1:0] ph;
    reg [1:0]    q;
    reg [3:0]    bitc;     // 0..7 数据位；8 = ACK 位
    reg          be_done;  // 单拍

    wire ph_last = (ph == DIV[PW-1:0] - 16'd1);
    wire stretch = (~scl_lo) & (~scl_in);

    // 下一步的动作与字节（组合，来自 st_n）
    always @(*) begin
        st_n  = st + 5'd1;
        act_n = act_of(st_n, rd, wr_n, rd_n);
    end

    //-------------------------------------------------------------------------
    // 唯一时序块
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st <= 5'd0; act <= A_START; mode <= M_START;
            txb <= 8'h00; sh <= 8'h00; rxsh <= 8'h00; rxc <= 4'd0;
            ph <= 0; q <= 2'd0; bitc <= 4'd0; be_done <= 1'b0;
            scl_lo <= 1'b0; sda_lo <= 1'b0;
            busy <= 1'b0; done <= 1'b0; err <= 1'b0; rd_d <= 32'h0;
        end else begin
            be_done <= 1'b0;
            done    <= 1'b0;

            if (!busy) begin
                // 空闲：总线释放
                scl_lo <= 1'b0; sda_lo <= 1'b0;
                ph <= 0; q <= 2'd0; bitc <= 4'd0; rxc <= 4'd0;
                err <= 1'b0; rd_d <= 32'h0;
                if (req) begin
                    busy  <= 1'b1;
                    st    <= 5'd0;
                    act   <= A_START;
                    mode  <= M_START;
                    ph    <= 0; q <= 2'd0; bitc <= 4'd0; rxc <= 4'd0;
                end
            end else begin
                // 相位推进（释放 SCL 时若从机拉伸则原地等待）
                if (ph_last) begin
                    if (q == 2'd1 && stretch) ph <= ph;
                    else begin ph <= 0; q <= q + 2'd1; end
                end else begin
                    ph <= ph + 16'd1;
                end

                // ---------------- 各相位的输出 ----------------
                case (q)
                    2'd0: begin
                        if (mode == M_TX) begin
                            scl_lo <= 1'b1;
                            sda_lo <= (bitc == 4'd8) ? 1'b0 : ~sh[7];
                        end else if (mode == M_RX) begin
                            scl_lo <= 1'b1;
                            sda_lo <= 1'b0;                 // 释放，由从机驱动
                        end else if (mode == M_START) begin
                            if (bitc == 4'd0) begin scl_lo <= 1'b0; sda_lo <= 1'b0; end
                            else              begin scl_lo <= 1'b1; sda_lo <= 1'b1; end
                        end else begin // M_STOP
                            if (bitc == 4'd0) begin scl_lo <= 1'b1; sda_lo <= 1'b1; end
                            else              begin scl_lo <= 1'b0; sda_lo <= 1'b0; end
                        end
                    end

                    2'd1: begin
                        if (mode == M_START) begin
                            scl_lo <= (bitc == 4'd0) ? 1'b0 : 1'b1;
                            sda_lo <= (bitc == 4'd0) ? 1'b0 : 1'b1;   // SCL 高时 SDA 下降
                        end else if (mode == M_STOP) begin
                            scl_lo <= (bitc == 4'd0) ? 1'b1 : 1'b0;
                            sda_lo <= (bitc == 4'd0) ? 1'b1 : 1'b0;   // 先放 SCL 再放 SDA
                        end else begin
                            scl_lo <= 1'b0;                            // 释放 SCL
                        end
                    end

                    2'd2: begin
                        if (mode == M_TX && bitc == 4'd8) begin
                            if (sda_in) err <= 1'b1;                   // 从机未应答
                        end else if (mode == M_RX && bitc < 4'd8) begin
                            rxsh <= {rxsh[6:0], sda_in};
                        end
                    end

                    2'd3: begin
                        scl_lo <= 1'b1;
                        if (mode == M_TX || mode == M_RX) begin
                            if (bitc == 4'd8) begin
                                bitc    <= 4'd0;
                                be_done <= 1'b1;
                                if (mode == M_RX) begin
                                    rd_d <= {rd_d[23:0], rxsh};
                                    rxc  <= rxc + 4'd1;
                                end
                            end else begin
                                bitc <= bitc + 4'd1;
                                if (mode == M_TX) sh <= {sh[6:0], 1'b0};
                            end
                        end else begin
                            // 起始 / 停止：两个位周期即完成
                            if (bitc == 4'd1) begin
                                bitc    <= 4'd0;
                                be_done <= 1'b1;
                            end else begin
                                bitc <= bitc + 4'd1;
                            end
                        end
                    end
                endcase

                // ---------------- 动作完成 → 推进一步 ----------------
                if (be_done) begin
                    if (act == A_STOP) begin
                        busy   <= 1'b0;
                        done   <= 1'b1;
                        scl_lo <= 1'b0;
                        sda_lo <= 1'b0;
                    end else begin
                        st  <= st_n;
                        act <= act_n;
                        // 装载下一个动作
                        case (act_n)
                            A_TX:     begin mode <= M_TX;    sh  <= byte_of(st_n, dev, reg_a, wr_d); bitc <= 4'd0; end
                            A_RX:     begin mode <= M_RX;    rxsh <= 8'h00; bitc <= 4'd0; end
                            A_START,
                            A_RSTART: begin mode <= M_START; bitc <= 4'd0; end
                            A_STOP:   begin mode <= M_STOP;  bitc <= 4'd0; end
                            default:  begin mode <= M_STOP;  bitc <= 4'd0; end
                        endcase
                    end
                end
            end
        end
    end

endmodule
