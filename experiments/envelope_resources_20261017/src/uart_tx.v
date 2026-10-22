//=============================================================================
// uart_tx.v —— 串口发送（拓展 E8 的 FPGA 侧一半）
//
// 【协议】与 uart_rx 完全对称：115200 8N1，LSB 先发。
//   DIV = CLK_HZ / BAUD = 27000000 / 115200 = 234（整数，无累积误差）
//   帧结构：起始位(0) + 8 个数据位 + 停止位(1)  = 10 个位时
//
// 【握手】tx_start 给一个时钟宽的脉冲，模块把 tx_data 发出去；
//   发送期间 busy = 1；最后一个停止位的中点 done 拉高一个时钟（可级联下一字节）。
//
// 【为什么要 done 而且不是 busy 下降沿】上位机读回一个寄存器要发两个字节
//   （地址 + 数据），用 done 级联最省事、也最不容易错拍。
//=============================================================================

`timescale 1ns/1ps

module uart_tx #(
    parameter integer CLK_HZ = 27000000,
    parameter integer BAUD   = 115200
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire [7:0] tx_data,
    input  wire       tx_start,
    output reg        tx,          // 串口发送线（空闲为高）
    output reg        busy,
    output reg        done
);

    localparam integer DIV = CLK_HZ / BAUD;      // 234

    localparam S_IDLE  = 2'd0,
               S_START = 2'd1,
               S_DATA  = 2'd2,
               S_STOP  = 2'd3;

    reg [1:0]  st;
    reg [7:0]  sh;          // 待发数据
    reg [3:0]  biti;        // 已发位数
    reg [15:0] cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st   <= S_IDLE;
            tx   <= 1'b1;
            busy <= 1'b0;
            done <= 1'b0;
            sh   <= 8'd0;
            biti <= 4'd0;
            cnt  <= 16'd0;
        end
        else begin
            done <= 1'b0;
            case (st)
                S_IDLE: begin
                    tx <= 1'b1;
                    if (tx_start) begin
                        sh   <= tx_data;
                        st   <= S_START;
                        tx   <= 1'b0;        // 起始位立刻拉低
                        busy <= 1'b1;
                        cnt  <= DIV[15:0] - 16'd1;
                    end
                    else busy <= 1'b0;
                end

                S_START: begin
                    if (cnt == 16'd0) begin
                        tx   <= sh[0];       // LSB 先发
                        sh   <= {1'b0, sh[7:1]};
                        biti <= 4'd1;
                        cnt  <= DIV[15:0] - 16'd1;
                        st   <= S_DATA;
                    end
                    else cnt <= cnt - 16'd1;
                end

                S_DATA: begin
                    if (cnt == 16'd0) begin
                        if (biti == 4'd8) begin
                            tx  <= 1'b1;     // 停止位
                            cnt <= DIV[15:0] - 16'd1;
                            st  <= S_STOP;
                        end
                        else begin
                            tx   <= sh[0];
                            sh   <= {1'b0, sh[7:1]};
                            biti <= biti + 4'd1;
                            cnt  <= DIV[15:0] - 16'd1;
                        end
                    end
                    else cnt <= cnt - 16'd1;
                end

                S_STOP: begin
                    if (cnt == 16'd0) begin
                        tx   <= 1'b1;
                        busy <= 1'b0;
                        done <= 1'b1;        // 一个时钟宽的完成脉冲
                        st   <= S_IDLE;
                    end
                    else cnt <= cnt - 16'd1;
                end

                default: st <= S_IDLE;
            endcase
        end
    end

endmodule
