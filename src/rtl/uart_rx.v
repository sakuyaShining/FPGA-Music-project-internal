//=============================================================================
// uart_rx.v —— UART 接收器（只收不发，够用且最省）
//
// 【为什么要它】
//   顶层曾经只有"演示序列器"在写音高寄存器，CTRL / MIX / ADSR 从来没被写过。
//   综合器很聪明：没被写过的寄存器会按 initial 初值【常量折叠】——
//   于是 CTRL 里的测试模式位恒为 0，整个 test_mode 被优化掉，
//   "现场可切换测试模式"就成了空话。
//   UART 一接上，写端口真正活着，整张寄存器表都不会被折叠。
//
//   ★ 这是一条通用教训：**寄存器表只要有一个字节永远不被写，
//     那一块逻辑就有被综合器吃掉的风险。** 要么让它可写，要么别写进 RTL。
//
// 【协议：两字节一帧】
//   先发【地址】，再发【数据】。收到数据字节时产生一个写脉冲。
//   选两字节而不是"命令+地址+数据"三字节，是因为写寄存器只需要这两样，
//   上位机脚本也最好写（Python 里 pyserial 写两个字节即可）。
//
// 【波特率】
//   27 000 000 / 234 = 115 384.6 —— 相对 115200 偏差 0.16%，UART 完全够用
//   （UART 一位采样在中间，容差通常在 ±2% 以上）。
//   若想整除，可用 125000 baud（27e6/216 正好整除），但多数串口工具的
//   下拉框里没有这一项，所以还是选了 115200。
//
// 【接收时序】
//   经典三态：等起始位 → 位中点采样 8 位数 → 停位 → 输出 valid 脉冲。
//   位中点采样是关键：起始位被拉低后等 1.5 个位周期再采第 1 位，
//   之后每 1 个位周期采一位 —— 这样采样点始终在每一位的正中间。
//=============================================================================

`timescale 1ns/1ps

module uart_rx #(
    parameter integer CLK_HZ = 27000000,
    parameter integer BAUD   = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       rx,          // 串口接收线（空闲为高）
    output reg  [7:0] data,        // 收到的字节
    output reg        valid        // 收妥脉冲（一个时钟宽）
);

    localparam integer DIV = CLK_HZ / BAUD;      // 234
    localparam integer HALF= DIV / 2;            // 117

    reg [1:0]  state;
    localparam S_IDLE = 2'd0, S_START = 2'd1, S_DATA = 2'd2, S_STOP = 2'd3;

    reg [15:0] cnt;
    reg [2:0]  bit_i;
    reg [7:0]  sh;

    // 输入同步（跨时钟域的标准做法：两级寄存器抗亚稳态）
    reg rx_s1, rx_s2;
    always @(posedge clk) begin
        rx_s1 <= rx;
        rx_s2 <= rx_s1;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            cnt   <= 16'd0;
            bit_i <= 3'd0;
            sh    <= 8'd0;
            data  <= 8'd0;
            valid <= 1'b0;
        end
        else begin
            valid <= 1'b0;

            case (state)
                //--------------------------------------------- 等起始位
                S_IDLE: begin
                    if (rx_s2 == 1'b0) begin      // 起始位（低）
                        cnt   <= 16'd0;
                        state <= S_START;
                    end
                end

                //--------------------------------------------- 起始位中点
                S_START: begin
                    if (cnt == HALF[15:0]) begin
                        // 中点处再确认一次：仍为低才是真起始位（滤毛刺）
                        if (rx_s2 == 1'b0) begin
                            cnt   <= 16'd0;
                            bit_i <= 3'd0;
                            state <= S_DATA;
                        end
                        else
                            state <= S_IDLE;
                    end
                    else
                        cnt <= cnt + 16'd1;
                end

                //--------------------------------------------- 8 位数据（LSB 先）
                S_DATA: begin
                    if (cnt == DIV[15:0] - 16'd1) begin
                        cnt <= 16'd0;
                        sh  <= {rx_s2, sh[7:1]};   // UART 是 LSB first
                        if (bit_i == 3'd7)
                            state <= S_STOP;
                        else
                            bit_i <= bit_i + 3'd1;
                    end
                    else
                        cnt <= cnt + 16'd1;
                end

                //--------------------------------------------- 停位
                S_STOP: begin
                    if (cnt == DIV[15:0] - 16'd1) begin
                        cnt   <= 16'd0;
                        data  <= sh;
                        valid <= 1'b1;
                        state <= S_IDLE;
                    end
                    else
                        cnt <= cnt + 16'd1;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
