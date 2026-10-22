//=============================================================================
// bringup_top.v —— Tang Nano 9K + 4.3 寸 RGB 屏：图片显示 + 自检图案
//-----------------------------------------------------------------------------
// 板卡：Sipeed Tang Nano 9K（GW1NR-LV9QN88PC6/I5）
// 屏幕：Sipeed 4.3 寸 RGB 屏，480×272，40P 排线
//
// 【两个画面，按键切换】
//   默认：显示图片（image_view，8 色抖动图）
//   按住按键 S2 ：显示自检图案（test_pattern：彩条 + 白边框 + 二进制计数条）
//   自检图案留着是为了以后换屏/换线时还能一键回到"已知正确"的画面。
//
// 【结构】三个模块，各管一件事
//
//     ┌─────────────────────┐
//     │   lcd_480x272       │  可复用显示驱动：PLL + 行场时序 + 打拍 + 消隐
//     │   （画布）           │  对外暴露有效区相对坐标 (px_x, px_y, px_de)
//     └──────────┬──────────┘  收回 (px_r/g/b)
//                │
//        ┌───────┴────────┐
//        ▼                ▼
//   ┌──────────┐    ┌──────────────┐
//   │image_view│    │ test_pattern │      两个"客户"，都是纯组合逻辑
//   │ (图片)    │    │  (自检图案)   │
//   └──────────┘    └──────────────┘
//
//     ┌─────────────────┐
//     │  led_heartbeat  │  6 颗 LED，跑 27 MHz 直连（**独立于 PLL**）
//     └─────────────────┘
//
// 【为什么 LED 要独立于 PLL —— 本设计的诊断核心】
//   两个**互相独立**的时钟域，刻意不共用：
//     ① 27 MHz 域（晶振直连）：只驱动 6 颗 LED
//     ② 像素时钟域（经 PLL）：驱动视频通路
//   如果 LED 也跑像素时钟，一旦 PLL 没锁，LED 和屏幕会**一起死**，
//   就分不清是"PLL 挂了"还是"屏挂了"。分开之后故障现象唯一：
//       LED 全不亮                → FPGA 没配置成功，或晶振没起振
//       LED 在闪 + led[5] 常亮    → PLL 没锁定（屏不亮属正常）
//       LED 在闪 + led[5] 灭 + 屏黑 → PLL 正常，问题在屏幕侧
//       LED 在闪 + led[5] 灭 + 出图 → 全部通过
//
// 【引脚】见 src/constr/bringup_top.cst，全部取自 Sipeed 官方例程。
//=============================================================================

module bringup_top (
    input  wire       clk_27m,      // 引脚 52：板载 27 MHz 晶振
    input  wire       btn_rst_n,    // 引脚 4 ：按键（兼作复位），按下 = 0
    input  wire       btn_user_n,   // 引脚 3 ：按键（按住看自检图案），按下 = 0

    output wire [5:0] led,          // 引脚 16/15/14/13/11/10：6 颗 LED，低电平点亮

    output wire       lcd_clk,      // 引脚 35：像素时钟
    output wire       lcd_de,       // 引脚 33：数据有效
    output wire       lcd_hsync,    // 引脚 40：行同步（低有效）
    output wire       lcd_vsync,    // 引脚 34：场同步（低有效）
    output wire [4:0] lcd_r,        // 引脚 75/74/73/72/71：R[4:0]
    output wire [5:0] lcd_g,        // 引脚 70/69/68/57/56/55：G[5:0]
    output wire [4:0] lcd_b         // 引脚 54/53/51/42/41：B[4:0]
);

    //=========================================================================
    // 一、按键同步（跨时钟域处理的最小范例）
    //     按键相对于像素时钟是完全异步的信号，直接采可能采到亚稳态，
    //     所以要过两级触发器（俗称"打两拍"）。这里不加消抖：
    //     本按键只用来切换画面，触点抖动的后果只是画面闪一下，
    //     不影响正确性，没必要为它引入消抖状态机。
    //=========================================================================
    wire        pix_clk;
    wire        pll_locked;
    wire [15:0] px_x, px_y;
    wire        px_de, px_frame_tick;
    wire [4:0]  px_r;
    wire [5:0]  px_g;
    wire [4:0]  px_b;

    wire rst_n = btn_rst_n & pll_locked;

    reg s2_meta;    // 第一级：可能采到亚稳态
    reg s2_sync;    // 第二级：输出已经稳定

    always @(posedge pix_clk or negedge rst_n) begin
        if (!rst_n) begin
            s2_meta <= 1'b1;
            s2_sync <= 1'b1;
        end
        else begin
            s2_meta <= btn_user_n;
            s2_sync <= s2_meta;
        end
    end

    wire show_pattern = ~s2_sync;   // 按住（0）时显示自检图案，松开显示图片

    //=========================================================================
    // 二、显示驱动（画布）
    //=========================================================================
    lcd_480x272 u_lcd (
        .clk_27m        (clk_27m),
        .rst_btn_n      (btn_rst_n),
        .pix_clk        (pix_clk),
        .pll_locked     (pll_locked),

        .px_x           (px_x),
        .px_y           (px_y),
        .px_de          (px_de),
        .px_frame_tick  (px_frame_tick),
        .px_r           (px_r),
        .px_g           (px_g),
        .px_b           (px_b),

        .lcd_clk        (lcd_clk),
        .lcd_de         (lcd_de),
        .lcd_hsync      (lcd_hsync),
        .lcd_vsync      (lcd_vsync),
        .lcd_r          (lcd_r),
        .lcd_g          (lcd_g),
        .lcd_b          (lcd_b)
    );

    //=========================================================================
    // 三、两个画布客户（都是纯组合逻辑：给坐标，出颜色）
    //=========================================================================
    wire [4:0] img_r;
    wire [5:0] img_g;
    wire [4:0] img_b;

    image_view u_img (
        .pix_clk (pix_clk),
        .x       (px_x),
        .y       (px_y),
        .r       (img_r),
        .g       (img_g),
        .b       (img_b)
    );

    wire [4:0] pat_r;
    wire [5:0] pat_g;
    wire [4:0] pat_b;

    test_pattern #(
        .MARKERS (0)                // 方向诊断角标：0 = 关闭（方向已于上板验证）
    ) u_pat (
        .pix_clk    (pix_clk),
        .rst_n      (rst_n),
        .x          (px_x),
        .y          (px_y),
        .frame_tick (px_frame_tick),
        .mode_solid (1'b0),         // 纯色自检档已由"按键切图案"取代，关闭
        .r          (pat_r),
        .g          (pat_g),
        .b          (pat_b)
    );

    assign px_r = show_pattern ? pat_r : img_r;
    assign px_g = show_pattern ? pat_g : img_g;
    assign px_b = show_pattern ? pat_b : img_b;

    //=========================================================================
    // 四、LED 指示（跑在 27 MHz 域，独立于 PLL）
    //=========================================================================
    // pll_locked 是像素时钟域产生的信号，要拿到 27 MHz 域用，必须打两拍同步。
    // 它是一个缓慢变化的状态位，打两拍足够，不需要握手。
    reg lock_meta, lock_sync;

    always @(posedge clk_27m or negedge btn_rst_n) begin
        if (!btn_rst_n) begin
            lock_meta <= 1'b0;
            lock_sync <= 1'b0;
        end
        else begin
            lock_meta <= pll_locked;
            lock_sync <= lock_meta;
        end
    end

    // 注意这里用的是 btn_rst_n（只受按键控制），不是 rst_n（还含 pll_locked）。
    // 这正是本模块的用意：PLL 锁不锁，LED 都要能工作，才能替本项目把话说清楚。
    led_heartbeat #(
        .CLK_HZ (27000000)      // 27 MHz 板载晶振
    ) u_led (
        .clk      (clk_27m),
        .rst_n    (btn_rst_n),
        .led_lo_n (led[4:0])
    );

    // led[5]：PLL 锁定指示。LED 低电平点亮，所以锁定(1)时输出 1 = 灭；
    // 一旦失锁(0)就输出 0 = 亮，故障现象唯一可辨。
    //
    // 待核实：官方 IP 配置 gowin_rpll.ipc 里写着 LOCK_EN=false，
    //    即官方生成 IP 时没打算用 LOCK 输出（所以官方 wrapper 只有 2 个端口）。
    //    本设计直接从 rPLL 原语把 LOCK 引了出来。上板实测 led[5] 保持熄灭，
    //    与"已锁定"一致；但"LOCK 失效时它会不会亮"这件事**没有被验证过**。
    //    所以这颗灯当参考，别当保险。
    assign led[5] = lock_sync;

endmodule
