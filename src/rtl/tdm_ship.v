//=============================================================================
// tdm_ship.v —— 【出货顶层】包装
//
// 【为什么需要它】（2026-10-02 加的，针对"电脑能跑、上板跑不了"的一类风险）
//
//   仿真时 `tdm_top` 上的 `ev_*` / `preset` / `test_mode` 是**测试/调试口**
//   （A6 冻结条款：不上引脚）。但综合时它们仍是**顶层输入端口** ⇒
//   PnR 会把它们**自动分配到板上某个物理引脚** ：
//     实测（③ 完成后那次 PnR）它们落到了 pin 84/82/52/49/48/26/83/25/63/10/86/85/11/13/53/57
//   ⇒ 若其中任何一根在板上被别的器件**驱动为高** ，`ev_valid` 或 `ev_on`
//     就会读到 1 ⇒ **幽灵音符事件** —— 而仿真里完全看不出
//     （这正是"PC 能跑、FPGA 上板跑不了"的典型形态）
//
//   工程文件（.gprj）不支持 Verilog 宏定义 ，所以用**包装模块**解决：
//   出货顶层 = 本模块，它把那些端口**在 RTL 里接成常量**
//   ⇒ 综合出来的网表**根本没有这些端口** ⇒ 不会占用任何引脚
//
// 【代价与一致性】
//   · `test_mode` 固定 0（A2：上电不进测试模式）；测试模式改由寄存器 CTRL[0] 进入
//   · `preset` 固定 0（音色改由寄存器 0x37 + CTRL[3]=preset_src ，见 A4）
//   · `ev_*` 固定 0（音符一律走 pads / UART 0x60-0x61 / 定序器）
//   · **19 个测试台仍然例化 `tdm_top`** 一行都不用改
//     而 `tdm_top` 在这条路径上的行为，与"这些输入恒为 0"完全一致
//     （闸口 28/28 已经覆盖了那条路径）
//=============================================================================

`timescale 1ns/1ps

module tdm_ship (
    input  wire        clk,
    input  wire        rst_n,

    //---- 运行时参数通道（UART）----
    input  wire        uart_rx_pin,
    output wire        uart_tx_pin,

    //---- 状态与音频 ----
    output wire [5:0]  led,
    output wire        dac_din,
    output wire        dac_ws,
    output wire        dac_bck,
    output wire        pa_en,

    //---- 16 路电容触摸电极 ----
    inout  wire [15:0] pad
);

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        // 测试/调试口在这里【接成常量】—— 它们不再出现在顶层 ⇒ 不占引脚
        .ev_valid(1'b0),
        .ev_on(1'b0),
        .ev_note(7'd0),
        .ev_vel(4'd0),
        .preset(2'd0),
        .test_mode(1'b0),
        .uart_rx_pin(uart_rx_pin),
        .uart_tx_pin(uart_tx_pin),
        .led(led),
        .dac_din(dac_din),
        .dac_ws(dac_ws),
        .dac_bck(dac_bck),
        .pa_en(pa_en),
        .pad(pad),
        .finger_valid(1'b0), .finger_cmd(2'd0),
        .finger_id(5'd0), .finger_group(5'd0), .finger_position(12'sd0),
        .voice_valid(), .voice_on(), .voice_group(), .voice_note()
    );

endmodule
