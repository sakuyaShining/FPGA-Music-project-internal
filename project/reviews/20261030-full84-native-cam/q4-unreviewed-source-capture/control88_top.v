//=============================================================================
// control88_top.v —— Control88 四层控制板产品顶层（接合候选）
//
// 【与 tdm_ship 的区别】tdm_ship 是"裸 Tang Nano 20K"顶层：16 路电极直连、
//   测试/调试口接常量、无 I2C 初始化、无按键链。Control88 的物理接口完全不同：
//     · 琴键经 6 片 4067 阵列（JB0..JB5）复用，只有 6 根 SENSE 回 FPGA
//     · 地址/放电由 74HC595(U8) 输出，按键/拨轮/编码器经 74HC165(U9+UX1) 读回
//     · 屏与 165 共用 SCK/MOSI，返回线由 U11 按 HARM_CS_N 二选一
//     · PCM5122 是 I2C 软件模式，必须由 FPGA 初始化才会出声
//   本顶层把这些都接上，音频引擎仍然原样复用 tdm_top（不改一行）。
//
// 【tdm_top 的 pad 口怎么处理】Control88 没有"16 路电极直连"这回事，
//   所以 tdm_top 的 pad 口在板上不存在。这里接一根**只有常量 z 驱动**的网：
//   pad_scan 自己的三态驱动器是唯一有效驱动，读回恒为高阻/常量
//   ⇒ 计数不增长、基线为 0、阈值不触发 ⇒ **零 pad 事件**（不产生幽灵音符）。
//   键事件全部由 ev_* 从 c88_evq 送入。
//
// 【未接的部分（红项，见 Q4 报告）】
//   · J10 屏：控制器型号未确认（RA_MISO 命名指向 RA8875 系，但 DISP_* 与 165
//     共用总线，且 U11 的返回通道选择必须在 165 读窗口外），本批不驱动，HARM_CS_N 恒 1
//   · 音色非易失存储：**2026-10-30 已接**（c88_nvstore + U10 24Cxx，地址 0x50）
//   · 力度：控制板无压力传感 ⇒ 固定 12/15
//=============================================================================
`timescale 1ns/1ps

module control88_top (
    input  wire        clk_27m,            // pin 4：板载 27 MHz
    input  wire        btn_rst,            // pin 87：板载按键，高有效

    // ---- J6：共享三线总线 + 感应 ----
    output wire        bus_sck,            // pin 27  BUS_SCK
    output wire        bus_mosi,           // pin 15  BUS_MOSI
    input  wire        bus_return,         // pin 28  BUS_RETURN
    output wire        scan_latch,         // pin 16  SCAN_LATCH
    output wire        input_load_n,       // pin 17  INPUT_LOAD_N
    output wire        harm_cs_n,          // pin 19  HARM_CS_N
    input  wire [2:0]  sense_lo,           // pin 29/30/31  SENSE_0..2
    input  wire [2:0]  sense_hi,           // pin 41/42/48  SENSE_3..5

    // ---- I2C（PCM5122 + EEPROM）----
    inout  wire        i2c_sda,            // pin 25
    inout  wire        i2c_scl,            // pin 26

    // ---- I2S 到 PCM5122 ----
    output wire        i2s_bck,            // pin 56
    output wire        i2s_din,            // pin 54
    output wire        i2s_lrck,           // pin 55

    // ---- 触摸中断（本批不驱动屏，仅作状态观测）----
    input  wire        tp_int,             // pin 77

    // ---- 板载 USB 串口（Nano 模块自带，不在排针上）----
    input  wire        uart_rx,            // pin 70
    output wire        uart_tx,            // pin 69

    // ---- 仅剩的两个可自由使用的板载 LED ----
    output wire        led3,               // pin 18（载板 J6-18 空脚）
    output wire        led5,               // pin 20（载板 J6-16 空脚）

    // ---- 空脚占位：pin 51 在 Control88 上是 J5-9，载板未接 ----
    //   GW2AR-18 的 51/54/55/56 属同一组专用 SSPI 引脚，只约束 54/55/56
    //   会让 PnR 报 "constrained location is useless in current package"。
    //   必须四个一起约束，所以把 pa_en 引出到 51（板上悬空，驱动无副作用）。
    output wire        pa_en_nc
);

    //-------------------------------------------------------------------------
    // 复位：按键（高有效）+ 上电计数
    //-------------------------------------------------------------------------
    reg [15:0] por_cnt;
    reg        rst_n;

    always @(posedge clk_27m) begin
        if (btn_rst) begin
            por_cnt <= 16'd0;
            rst_n   <= 1'b0;
        end else if (por_cnt != 16'hFFFF) begin
            por_cnt <= por_cnt + 16'd1;
            rst_n   <= 1'b0;
        end else begin
            rst_n   <= 1'b1;
        end
    end

    wire [5:0] sense = {sense_hi, sense_lo};

    //-------------------------------------------------------------------------
    // 板级粘合层
    //-------------------------------------------------------------------------
    wire [83:0] touch;
    wire        ev_valid, ev_on;
    wire [6:0]  ev_note;
    wire [3:0]  ev_vel;
    wire [3:0]  preset_pin;                // 面板 PRESET0..3（c88_top 解出）
    wire [3:0]  preset;                    // 生效预设（EEPROM 覆盖后）
    wire        edit_btn, edit_apply, edit_save, edit_cancel;
    wire        enc_push, enc_up, enc_dn;
    wire [7:0]  dbg_frame;

    c88_top #(.NCH(6), .NV(84), .BASE_N(36)) u_c88 (
        .clk(clk_27m), .rst_n(rst_n),
        .bus_sck(bus_sck), .bus_mosi(bus_mosi), .bus_return(bus_return),
        .scan_latch(scan_latch), .input_load_n(input_load_n), .harm_cs_n(harm_cs_n),
        .sense(sense),
        .touch(touch),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(preset_pin), .edit_btn(edit_btn),
        .edit_apply(edit_apply), .edit_save(edit_save), .edit_cancel(edit_cancel),
        .enc_push(enc_push), .enc_up(enc_up), .enc_dn(enc_dn),
        .dbg_frame(dbg_frame)
    );

    //-------------------------------------------------------------------------
    // PCM5122 初始化（复用已验证的 17 条 ROM，SLAS763C 语义反算过）
    //   器件地址 0x4C：Control88 上 U12 的 ADR1/ADR2 无网络 ⇒ 取默认 0。
    //-------------------------------------------------------------------------
    wire pcm_scl_lo, pcm_sda_lo, pcm_done, pcm_locked, pcm_failed;

    pcm5122_init #(.CLK_HZ(27000000), .SCL_HZ(100000), .DEV(7'h4C)) u_pcm (
        .clk(clk_27m), .rst_n(rst_n),
        .scl_lo(pcm_scl_lo), .sda_lo(pcm_sda_lo),
        .sda_in(i2c_sda), .scl_in(i2c_scl),
        .done(pcm_done), .pll_locked(pcm_locked), .failed(pcm_failed)
    );

    //-------------------------------------------------------------------------
    // 音色预设非易失存储（U10 = 24Cxx，地址 0x50）
    //
    // 【总线归属】pcm5122_init 完成后停在 S_FIN，不再驱动 scl_lo/sda_lo
    //   （保持释放）。所以 nvstore 在 pcm_done 之后接管总线是安全的。
    //   两路开漏用"线或"合成：任一拉低即为低，不会短路。
    //
    // 【为什么必须自己带一份 I2C 主机】共享 RTL i2c_master.v 的接收路径是坏的
    //   （每 bit 被移 DIV 次 + 末字节 ACK/NACK 极性反），实测读回全错。
    //   详见 rtl/c88_i2c.v 文件头与 tb_i2c_read 的修前/修后对照。
    //-------------------------------------------------------------------------
    reg pcm_done_q;
    always @(posedge clk_27m or negedge rst_n) begin
        if (!rst_n)       pcm_done_q <= 1'b0;
        else if (pcm_done) pcm_done_q <= 1'b1;
    end

    wire        nv_scl_lo, nv_sda_lo;
    wire [3:0]  preset_nv;
    wire        nv_valid, nv_busy, nv_err;
    wire [1:0]  nv_phase;

    c88_nvstore #(
        .DEV(7'h50), .CLK_HZ(27000000), .SCL_HZ(100000), .TWR_MS(6)
    ) u_nv (
        .clk(clk_27m), .rst_n(rst_n),
        .start(pcm_done_q), .save(edit_save), .preset_in(preset_pin),
        .preset_out(preset_nv), .valid(nv_valid), .busy(nv_busy), .err(nv_err),
        .phase_dbg(nv_phase),
        .scl_lo(nv_scl_lo), .sda_lo(nv_sda_lo),
        .sda_in(i2c_sda), .scl_in(i2c_scl)
    );

    // 开漏线或：任一路拉低总线即为低
    assign i2c_scl = (pcm_scl_lo | nv_scl_lo) ? 1'b0 : 1'bz;
    assign i2c_sda = (pcm_sda_lo | nv_sda_lo) ? 1'b0 : 1'bz;

    // nvstore 在无效记录时自己退回 preset_in，所以这里直接用它的输出
    assign preset = preset_nv;

    //-------------------------------------------------------------------------
    // 音频引擎：tdm_top 原样复用
    //   pad 口接"仅常量 z 驱动"的网 ⇒ pad_scan 读回恒高阻 ⇒ 零事件
    //-------------------------------------------------------------------------
    wire [15:0] pad_idle;
    assign pad_idle = 16'hzzzz;

    wire [5:0] led_nc;
    wire       dac_din, dac_ws, dac_bck;

    tdm_top u_engine (
        .clk(clk_27m), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(preset[1:0]),
        .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(led_nc),
        .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck), .pa_en(pa_en_nc),
        .pad(pad_idle)
    );

    assign i2s_din  = dac_din;
    assign i2s_lrck = dac_ws;
    assign i2s_bck  = dac_bck;

    //-------------------------------------------------------------------------
    // 两个保留 LED 的状态编码
    //   led5：扫描帧最高位翻转（心跳，证明扫描在跑）
    //   led3：PCM5122 PLL 锁定（灭=锁定成功）或失败（常亮）
    //   共阳极：输出低点亮
    //-------------------------------------------------------------------------
    reg [15:0] hb_div;
    always @(posedge clk_27m or negedge rst_n) begin
        if (!rst_n) hb_div <= 16'd0;
        else        hb_div <= hb_div + 16'd1;
    end

    //   led5：心跳（证明扫描在跑）
    //   led3：PCM5122 状态 —— 灭=已锁；常亮=初始化失败；4 Hz 闪=触摸中断有效
    assign led5 = ~hb_div[15];
    assign led3 = pcm_failed ? 1'b0 :
                  tp_int     ? ~hb_div[13] :
                               ~pcm_locked;

endmodule
