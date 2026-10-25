//=============================================================================
// pcm5122_init.v —— PCM5122 上电初始化（I2C 软件模式）
//
// #############################################################################
// ##  重要：这里的 "PLL" 是 PCM5122 芯片【内部】的音频 PLL，不是 FPGA 的 PLL  ##
// #############################################################################
//
//   本模块**不碰 FPGA 的任何时钟资源**：
//     · 没有例化 rPLL / CLKDIV / DCS / CLKSEL，一个都没有
//     · 全部逻辑跑在既有 27 MHz 单时钟域，靠慢使能分频（i2c_master 内部 4 相位计数）
//     · 不产生任何派生时钟，不新增全局时钟网络
//     · SDC 仍然只有一条 create_clock（clk, 37.037 ns）
//
//   构建报告可自证（5. Clock Resource Usage Summary / 6. Global Clock Signals）：
//     PRIMARY 1/8、LW 5/8、GCLK_PIN 1/5 —— 与不含本模块的基线码流**逐项相同**
//
//   那 96 MHz 是什么？
//     是 U12（PCM5122）晶片【内部】用它自己的 PLL 把 BCK(1.5 MHz) 倍频出来的
//     内部主时钟，只用于它自己的 ΔΣ 调制器。这个频率：
//       · 不出现在板子上的任何一根线上
//       · 不是 FPGA 产生的，FPGA 只提供 BCK —— 而 BCK 在基线码流里就已经是 1.5 MHz
//       · 只能通过 I2C 写寄存器去"告诉"它怎么倍频，改不了也碰不到
//
//   FPGA 这边唯一新增的动作：用两根 GPIO 以 100 kHz 的速率bit-bang 出 I2C 波形。
//   100 kHz 是**数据速率**，不是时钟域。
//
//=============================================================================
//
// 【为什么需要这个模块】
//   载板 U12 的 MODE1=GND、MODE2=DAC_3V3 ⇒ TI SLAS763C 定义的 I2C 软件模式。
//   手册 §8.3.6.3 明文：
//     "In hardwired mode ... if BCK and LRCK start correctly while SCK remains
//      at ground level for 16 successive LRCK periods, then the internal PLL
//      starts, automatically generating an internal SCK from the BCK reference."
//     "In software mode, the user must set all the PLL registers and clock
//      divider registers for referencing BCK."
//   而板上 SCK(pin20) 是接地的 ⇒ 硬件模式那条自动兜底在这里不存在。
//
//   更糟的是寄存器默认值本身就把芯片锁死：
//     P0/0x04 b0 PLLE = 1        PLL 开着
//     P0/0x0D b6:4 SREF = 000    PLL 基准 = SCK（接地，是死的）
//     P0/0x25 b3 IDCH = 0        SCK 停振视为时钟错误
//     P0/0x25 b4 IDSK = 0        SCK/LRCK 比值校验（比值=0，越界）
//   上电即判时钟错误 → standby → 输出恒静音，且不会自愈。
//
// 【本模块做的事】
//   上电后按固定序列写 17 个寄存器，然后回读 P0/0x04 确认 PLL 是否锁定。
//   序列按本板实际时钟算出（不是抄手册示例）：
//
//     BCK = 27 MHz / 18 = 1,500,000 Hz     （audio_clk_en.v: DIV_BCK=18）
//     fs  = BCK / 32    = 46,875 Hz        （BCK_PER_LRCK=32）
//     BCK/fs            = 32
//
//   取手册 Table 131 中 "fS=48k / RSCK=32" 那一行做等比缩放（该行 BCK/fs 也是 32）：
//     PLLCK = 2048 × fs = 96.000 MHz = BCK × R × J.D / P = 1.5M × 2 × 32 / 1  ✓
//     ↑ PLLCK 是 U12 晶片内部的音频主时钟（由 BCK 倍频而来），不是 FPGA 的时钟
//     DSP 时钟 = 1024 fs = 48.0 MHz → NMAC = 96/48 = 2
//     DAC 时钟 =  128 fs =  6.0 MHz → NDAC = 96/6  = 16
//     OSR 时钟 =  256 fs = 12.0 MHz → DOSR = 96/12 = 8
//     NCP 时钟 = PLLCK/4 = 24.0 MHz → NCP  = 4
//
// 【为什么先关 PLL 再编程】
//   第 3 步写 P0/0x04=0x00 把 PLL 关掉，等 P/J/D/R 和分频器都写完再打开。
//   否则 PLL 会拿旧配置去锁，可能在编程途中反复失锁。手册没有强制要求，
//   但这是标准做法，代价为零。
//
// 【顺序不能乱】
//   第 2 步（0x25=0x1A）必须最先做：它关掉自动时钟配置、并忽略 SCK 检测。
//   否则在改 SREF 的过程中，SCK-halt 检测就会把芯片打进 standby。
//
// 【重试】
//   FPGA 走 Nano 的 USB，DAC 走载板 J13 的 5V —— 两个独立电源域，
//   DAC 很可能比 FPGA 后上电。所以任何一笔写失败（NACK）都从序列头重来，
//   最多 RETRY_MAX 次。全部失败才置 failed，且**不阻断音频通路**。
//
// 【时序】
//   全部逻辑在 27 MHz 单时钟域内，用慢使能分频，不产生任何派生时钟
//   （项目既有规矩：见 src/sim/README.md「不要分频出慢时钟」）。
//   I2C 100 kHz 下每位有 270 个 clk 的余量，加流水线级数不影响功能，
//   所以本模块对时序收敛没有任何压力。
//=============================================================================

`timescale 1ns/1ps

module pcm5122_init #(
    parameter integer CLK_HZ     = 27000000,
    parameter integer SCL_HZ     = 100000,
    parameter integer BOOT_MS    = 20,      // 上电到第一次写之间的等待
    parameter integer LOCK_MS    = 30,      // PLL 打开后到回读 PLCK 的等待
    parameter integer RETRY_MAX  = 8,       // 整序列重试次数
    parameter [6:0]   DEV        = 7'h4C    // ADR1=ADR2=GND ⇒ 0x4C（写 0x98）
)(
    input  wire clk,
    input  wire rst_n,

    // I2C 开漏（1 = 拉低）。板上 R33/R34(4.7k) 与 R60/R61(4.7k) 已上拉
    output wire scl_lo,
    output wire sda_lo,
    input  wire sda_in,
    input  wire scl_in,

    // 状态
    output reg  done,          // 序列执行完毕（无论成败），单拍脉冲
    output reg  pll_locked,    // 回读 P0/0x04 b4 PLCK == 0
    output reg  failed         // 重试耗尽仍失败
);

    //-------------------------------------------------------------------------
    // 状态编码（必须在 assign 之前声明）
    //-------------------------------------------------------------------------
    localparam [2:0] S_BOOT   = 3'd0,
                     S_GAP    = 3'd1,
                     S_REQ    = 3'd2,
                     S_ACK    = 3'd3,
                     S_LOCK   = 3'd4,
                     S_RDREQ  = 3'd5,
                     S_RDACK  = 3'd6,
                     S_FIN    = 3'd7;

    reg [2:0] st;
    reg [1:0] gap;
    reg [4:0] idx;
    reg [7:0] wait_cnt;
    reg [3:0] retry_cnt;
    reg       fin_d;

    //-------------------------------------------------------------------------
    // 1 ms 时基
    //-------------------------------------------------------------------------
    localparam integer MS_DIV = CLK_HZ / 1000;      // 27000

    reg [15:0] ms_cnt;
    reg        ms_tick;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ms_cnt  <= 16'd0;
            ms_tick <= 1'b0;
        end
        else if (ms_cnt == MS_DIV - 1) begin
            ms_cnt  <= 16'd0;
            ms_tick <= 1'b1;
        end
        else begin
            ms_cnt  <= ms_cnt + 1'b1;
            ms_tick <= 1'b0;
        end
    end

    //-------------------------------------------------------------------------
    // 初始化 ROM：{寄存器地址, 数据}，共 17 条
    //
    //   idx  reg   val   含义
    //    0   0x00  0x00  选 Page 0
    //    1   0x25  0x1A  b1 DCAS=1 关自动时钟配置；b3 IDCH=1 忽略 SCK 停振；
    //                    b4 IDSK=1 忽略 SCK 比值校验
    //    2   0x04  0x00  PLLE=0，编程期间先关 PLL
    //    3   0x0D  0x10  SREF=001，PLL 基准改为 BCK
    //    4   0x14  0x00  P = 1        （写 P-1）
    //    5   0x15  0x20  J = 32
    //    6   0x16  0x00  D 高位 = 0
    //    7   0x17  0x00  D 低位 = 0
    //    8   0x18  0x01  R = 2        （写 R-1）
    //    9   0x1B  0x01  DSP 分频 ÷2   （96/48）
    //   10   0x1C  0x0F  DAC 分频 ÷16  （96/6）
    //   11   0x1D  0x03  NCP 分频 ÷4
    //   12   0x1E  0x07  OSR 分频 ÷8   （96/12）
    //   13   0x28  0x00  I2S 格式 + 16 bit 字长（对齐 32 BCK/帧的现帧）
    //   14   0x04  0x01  PLLE=1，打开 PLL
    //   15   0x02  0x00  退出 standby（b4 RQST=0 / b0 RQPD=0）
    //   ---  等待 LOCK_MS，回读 0x04 判 PLCK ---
    //   16   0x03  0x00  解除左右声道软静音（RQML/RQMR=0）
    //-------------------------------------------------------------------------
    localparam [4:0] IDX_LAST = 5'd16;

    function [15:0] rom_entry;
        input [4:0] i;
        begin
            case (i)
                5'd0:  rom_entry = {8'h00, 8'h00};
                5'd1:  rom_entry = {8'h25, 8'h1A};
                5'd2:  rom_entry = {8'h04, 8'h00};
                5'd3:  rom_entry = {8'h0D, 8'h10};
                5'd4:  rom_entry = {8'h14, 8'h00};
                5'd5:  rom_entry = {8'h15, 8'h20};
                5'd6:  rom_entry = {8'h16, 8'h00};
                5'd7:  rom_entry = {8'h17, 8'h00};
                5'd8:  rom_entry = {8'h18, 8'h01};
                5'd9:  rom_entry = {8'h1B, 8'h01};
                5'd10: rom_entry = {8'h1C, 8'h0F};
                5'd11: rom_entry = {8'h1D, 8'h03};
                5'd12: rom_entry = {8'h1E, 8'h07};
                5'd13: rom_entry = {8'h28, 8'h00};
                5'd14: rom_entry = {8'h04, 8'h01};
                5'd15: rom_entry = {8'h02, 8'h00};
                5'd16: rom_entry = {8'h03, 8'h00};
                default: rom_entry = {8'h00, 8'h00};
            endcase
        end
    endfunction

    //-------------------------------------------------------------------------
    // I2C 主机接口
    //-------------------------------------------------------------------------
    wire [15:0] ent     = rom_entry(idx);
    wire        is_read = (st == S_RDREQ);

    wire        m_req  = (st == S_REQ) || (st == S_RDREQ);
    wire [6:0]  m_dev  = DEV;
    wire        m_rd   = is_read;
    wire [7:0]  m_reg  = is_read ? 8'h04 : ent[15:8];
    wire [15:0] m_wr_d = {8'h00, ent[7:0]};
    wire [1:0]  m_wr_n = is_read ? 2'd0 : 2'd1;
    wire [2:0]  m_rd_n = 3'd1;

    wire [31:0] m_rd_d;
    wire        m_busy;
    wire        m_done;
    wire        m_err;

    i2c_master #(
        .CLK_HZ (CLK_HZ),
        .SCL_HZ (SCL_HZ)
    ) u_i2c (
        .clk      (clk),
        .rst_n    (rst_n),
        .req      (m_req),
        .dev      (m_dev),
        .rd       (m_rd),
        .reg_a    (m_reg),
        .wr_d     (m_wr_d),
        .wr_n     (m_wr_n),
        .rd_n     (m_rd_n),
        .rd_d     (m_rd_d),
        .busy     (m_busy),
        .done     (m_done),
        .err      (m_err),
        .scl_lo   (scl_lo),
        .sda_lo   (sda_lo),
        .sda_in   (sda_in),
        .scl_in   (scl_in)
    );

    //-------------------------------------------------------------------------
    // 主状态机
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st         <= S_BOOT;
            idx        <= 5'd0;
            gap        <= 2'd0;
            wait_cnt   <= 8'd0;
            retry_cnt  <= 4'd0;
            fin_d      <= 1'b0;
            done       <= 1'b0;
            pll_locked <= 1'b0;
            failed     <= 1'b0;
        end
        else begin
            done <= 1'b0;

            case (st)

                // 上电等待：DAC 可能比 FPGA 晚上电
                S_BOOT: begin
                    if (ms_tick) begin
                        if (wait_cnt == BOOT_MS - 1) begin
                            wait_cnt <= 8'd0;
                            st       <= S_GAP;
                            gap      <= 2'd2;
                        end
                        else begin
                            wait_cnt <= wait_cnt + 1'b1;
                        end
                    end
                end

                // 两条死拍，保证主机已回到 IDLE 再发下一个 req
                S_GAP: begin
                    if (gap == 2'd0)
                        st <= S_REQ;
                    else
                        gap <= gap - 1'b1;
                end

                S_REQ:   st <= S_ACK;
                S_RDREQ: st <= S_RDACK;

                // 等 done（单拍脉冲）
                S_ACK: begin
                    if (m_done) begin
                        if (m_err) begin
                            // 任一字节 NACK：整序列重来
                            if (retry_cnt == RETRY_MAX - 1) begin
                                failed <= 1'b1;
                                st     <= S_FIN;
                            end
                            else begin
                                retry_cnt <= retry_cnt + 1'b1;
                                idx       <= 5'd0;
                                wait_cnt  <= 8'd0;
                                st        <= S_BOOT;
                            end
                        end
                        else if (idx == 5'd15) begin
                            // 时钟树已写完、PLL 已打开 → 等锁定再回读
                            idx      <= 5'd16;
                            wait_cnt <= 8'd0;
                            st       <= S_LOCK;
                        end
                        else if (idx == IDX_LAST) begin
                            st <= S_FIN;              // 软静音解除完成
                        end
                        else begin
                            idx <= idx + 1'b1;
                            gap <= 2'd2;
                            st  <= S_GAP;
                        end
                    end
                end

                // 等 PLL 锁
                S_LOCK: begin
                    if (ms_tick) begin
                        if (wait_cnt == LOCK_MS - 1) begin
                            wait_cnt <= 8'd0;
                            st       <= S_RDREQ;
                        end
                        else begin
                            wait_cnt <= wait_cnt + 1'b1;
                        end
                    end
                end

                // 回读 P0/0x04，b4 PLCK：0 = 已锁
                S_RDACK: begin
                    if (m_done) begin
                        pll_locked <= m_err ? 1'b0 : ~m_rd_d[4];
                        gap        <= 2'd2;
                        st         <= S_GAP;          // 接着发 idx=16（解除静音）
                    end
                end

                S_FIN: begin
                    // done 只在一拍上为 1：用 fin_d 记住"已经报过"
                    done  <= ~fin_d;
                    fin_d <= 1'b1;
                    st    <= S_FIN;                   // 停在这里，不再动总线
                end

                default: st <= S_BOOT;
            endcase
        end
    end

endmodule
