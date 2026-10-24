//=============================================================================
// scan_shift165.v —— 74LV165 并行输入 / 串行输出读取
//
// 【这颗芯片在载板上干什么】
//   载板的 `INPUT_LOAD_N` / `BUS_SCK` / `BUS_RETURN` 三根线接 74LV165。
//   它把按键、预置开关、以及各通道的使能状态这类"并行但变化慢"的信号
//   收进一个 8 位移位寄存器，再借 595 已经在用的 SCK 串行读回 FPGA。
//   这样 8 个按键只花 1 根输入线 + 共用的时钟。
//
// 【为什么全仓库此前没有实现】
//   搜遍 fpga/current 只命中 budget.py 里一行文字预算
//   "165/encoder/buttons"，没有任何 .v。`rc_mux_scan` 只管 595 输出侧，
//   `INPUT_LOAD_N` / `BUS_RETURN` 这两个端口在 RTL 里完全悬空。
//
// 【时序：MSB first，不是 LSB first —— 这是最容易写错的地方】
//   74HC165 内部是 8 个 D 触发器串成一条移位链，QH 是**最后一级**输出。
//   并行装载时 H 直接装进最后一级，所以：
//       PL 拉低后，QH 立刻 = H  (bit7)
//       第 1 个 CP 上升沿后，QH = G  (bit6)
//       第 2 个 CP 上升沿后，QH = F  (bit5)
//       ...
//   即 **MSB (H) 先出**。若按 LSB first 去拼字节，读回来的按键会整体位序颠倒，
//   而"按了键但响的是别的键"这种 bug 在仿真里如果激励也按同样错误顺序给，
//   是查不出来的。所以这里把方向做成参数 MSB_FIRST，默认 1，并写清依据。
//
// 【采样点为什么放在 SCK 拉高之前】
//   状态机顺序是 LOW(采样) → HIGH(SCK↑) → LOW(采样) ...
//   即"先采当前位，再打时钟让下一位出来"。等价于在 SCK 低电平期间采样，
//   此时 QH 已经稳定了整整一个 HALF_PERIOD，不依赖 QH 的建立时间余量。
//
// 【与 595 共总线】
//   本模块只驱动 SCK / LOAD_N，不碰 MOSI / LATCH。595 的 LATCH 保持低，
//   所以 165 打的 SCK 只会让 595 的移位寄存器空转，输出锁存内容不变 —— 安全。
//   但代价是 595 的移位寄存器内容被打乱，因此 595 每次必须重写完整 8 位，
//   `scan_shift595` 正是这么做的（每字都从 bit7 开始完整移入）。
//=============================================================================

`timescale 1ns/1ps

module scan_shift165 #(
    parameter integer HALF_PERIOD = 8,      // SCK 半周期（clk 拍数）
    parameter integer WIDTH       = 8,      // 165 是 8 位；级联时改这里
    parameter integer MSB_FIRST   = 1       // 1 = H(bit7) 先出（74HC165 原生行为）
)(
    input  wire             clk,
    input  wire             rst_n,
    input  wire             start,          // 单拍脉冲：启动一次读取
    output wire             ready,          // 空闲，可接受新的 start
    output wire             bus_request,    // 给仲裁器
    input  wire             bus_grant,      // 来自仲裁器
    output reg              sck,            // 与 595 共用 BUS_SCK
    output reg              load_n,         // INPUT_LOAD_N，低有效
    input  wire             serial_in,      // BUS_RETURN
    output reg  [WIDTH-1:0] data,           // 读回的并行字
    output reg              data_valid,     // 单拍脉冲
    output reg              grant_error     // 传输中途丢 grant（不应发生）
);

    localparam IDLE   = 3'd0,
               WAIT   = 3'd1,
               LOAD   = 3'd2,
               SAMPLE = 3'd3,
               CLOCK  = 3'd4,
               FINISH = 3'd5;

    reg [2:0] state;
    reg [3:0] bit_index;                    // 支持最多 16 位级联
    reg [WIDTH-1:0] shift;

    localparam TW = (HALF_PERIOD < 2) ? 1 : $clog2(HALF_PERIOD);
    reg [TW-1:0] timer;

    assign ready       = (state == IDLE);
    assign bus_request = (state != IDLE);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= IDLE;
            bit_index  <= 4'd0;
            timer      <= {TW{1'b0}};
            sck        <= 1'b0;
            load_n     <= 1'b1;
            shift      <= {WIDTH{1'b0}};
            data       <= {WIDTH{1'b0}};
            data_valid <= 1'b0;
            grant_error<= 1'b0;
        end else begin
            data_valid <= 1'b0;

            // 一旦开始占用总线，中途丢失 grant 就是协议错误
            if (state >= LOAD && state <= CLOCK && !bus_grant)
                grant_error <= 1'b1;

            case (state)

                IDLE: begin
                    if (start) begin
                        bit_index <= WIDTH - 1;
                        load_n    <= 1'b1;      // 先确保不在装载态
                        state     <= WAIT;
                    end
                end

                WAIT: begin
                    if (bus_grant) begin
                        load_n <= 1'b0;         // 并行装载（低有效）
                        timer  <= {TW{1'b0}};
                        state  <= LOAD;
                    end
                end

                LOAD: begin
                    if (timer == HALF_PERIOD - 1) begin
                        timer  <= {TW{1'b0}};
                        load_n <= 1'b1;         // 释放装载 ⇒ QH 此时 = H (bit7)
                        state  <= SAMPLE;
                    end else timer <= timer + 1'b1;
                end

                SAMPLE: begin
                    if (timer == HALF_PERIOD - 1) begin
                        timer <= {TW{1'b0}};
                        // 此刻 QH 已稳定一个完整半周期
                        if (MSB_FIRST)
                            shift[bit_index] <= serial_in;
                        else
                            shift[WIDTH-1-bit_index] <= serial_in;
                        sck   <= 1'b1;          // 上升沿 ⇒ 下一位移出
                        state <= CLOCK;
                    end else timer <= timer + 1'b1;
                end

                CLOCK: begin
                    if (timer == HALF_PERIOD - 1) begin
                        timer <= {TW{1'b0}};
                        sck   <= 1'b0;
                        if (bit_index == 4'd0)
                            state <= FINISH;
                        else begin
                            bit_index <= bit_index - 1'b1;
                            state     <= SAMPLE;
                        end
                    end else timer <= timer + 1'b1;
                end

                FINISH: begin
                    data       <= shift;
                    data_valid <= 1'b1;
                    state      <= IDLE;
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule
