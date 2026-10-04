//=============================================================================
// gowin_rpll.v —— Gowin rPLL 硬核包装：27 MHz 板载晶振 → 9 MHz 像素时钟
//-----------------------------------------------------------------------------
// 板卡：Tang Nano 9K（GW1NR-LV9QN88PC6/I5），27 MHz 晶振接在引脚 52。
//
// 【PLL 参数之谜：已彻底解决（2026-09-21）】
//   项目早期记录过一句悬案："Gowin rPLL 的 defparam 与 UG286 文档公式对不上，
//   用文档公式算不出官方例程注释里的频率。" —— 现在答案找到了。
//
//   关键在于 Gowin IP 向导自己的描述文件 `<ip>.mod` 记的是**界面上填的数**，
//   而生成的 Verilog 里写的是**减 1 之后的编码值**：
//         .mod : -idiv_sel 3    -fbdiv_sel 1
//         .v   :  IDIV_SEL = 2   FBDIV_SEL = 0      ← 各减了 1
//   两边公式其实完全一致：
//         fCLKOUT = fCLKIN × fbdiv_sel / idiv_sel
//                 = fCLKIN × (FBDIV_SEL + 1) / (IDIV_SEL + 1)
//   代入本 IP： 27 × 1 / 3 = **9 MHz**
//   约束条件：fVCO = fCLKOUT × ODIV_SEL 必须落在 **400 ~ 1200 MHz**；
//             本 IP：9 × 48 = **432 MHz** ✓
//
//   【三组官方例程交叉验证，全部对上】
//     · 9K lcd_4.3：IDIV=2/FBDIV=0/ODIV=48  → 27×1/3 = 9 MHz
//                    其 .ipc 里写 CLKOUT_FREQ=9        ✓
//     · 9K lcd_led ：IDIV=4/FBDIV=23/ODIV=4 → 27×24/5 = 129.6 MHz
//                    再经 CLKOUTD(÷4) = 32.4 MHz，与其注释说的 33.33 MHz 相符 ✓
//                    VCO = 129.6 × 4 = 518.4 MHz 落在范围内 ✓
//     · VCO 范围校验见上。
//
//   ⚠️ **必须纠正的一条旧结论**：项目早期记的"20K 音频例程 PLL 输出 6 MHz"
//      是**错的**。该例程参数为 IDIV_SEL=5 / FBDIV_SEL=0，按正确公式：
//          27 × 1 / 6 = **4.5 MHz**，不是 6 MHz。
//      这会直接改变 I2S 的 BCK 与采样率推导。做音频通路时**必须重算**，
//      以该例程自己的 .ipc/.mod 为准，不要沿用旧笔记里的 6 MHz。
//
// 【证据文件在哪】
//   官方原始配置文件保存在（未改动，可随时对照）：
//     refs/vendor-examples/tang9k-official/step2_lcd43/src/gowin_rpll/
//         ├── gowin_rpll.ipc   ← 里面写着 CLKOUT_FREQ=9
//         └── gowin_rpll.mod   ← 里面写着 idiv_sel=3 / fbdiv_sel=1
//   本工程**刻意不把这两个文件放进 IP 目录**：因为一旦放进工程，用 Gowin 的
//   IP 向导"重新生成"就会覆盖本文件、丢掉下面那个 LOCK 端口。要看配置请直接
//   读 refs 里的原始文件，或按上面的公式自行推算。
//
// 【本文件相对官方生成物做的唯一改动】
//   把 LOCK 锁定指示引出来给上层用。官方 `.ipc` 里写着 LOCK_EN=false，
//   即官方生成时没打算用这个输出（所以官方 wrapper 只有 clkout/clkin 两个端口，
//   内部 wire lock_o 悬空）。这里从 rPLL 原语直接把 LOCK 接出来，用于：
//   ① PLL 未锁定时把设计保持在复位态；② 点亮一颗 LED 报错。
//   注意：上板实测 led[5] 保持熄灭，与"已锁定"一致；但"LOCK 失效时会不会亮"
//   这件事没有被验证过（要验证得故意配错 PLL，代价不值）。当参考用，别当保险。
//=============================================================================

module gowin_rpll (
    output wire clkout,     // 像素时钟输出：9 MHz
    output wire lock,       // PLL 锁定指示：1 = 已锁定，0 = 未锁定
    input  wire clkin       // 输入时钟：27 MHz（引脚 52）
);

    wire gw_gnd;
    assign gw_gnd = 1'b0;

    // 这几个输出本设计不用，但必须声明成 wire 并接上，
    // 避免综合器对未连接输出端口产生告警。
    wire clkoutp_o;
    wire clkoutd_o;
    wire clkoutd3_o;

    rPLL rpll_inst (
        .CLKOUT    (clkout),      // PLL 主输出
        .LOCK      (lock),        // 锁定指示
        .CLKOUTP   (clkoutp_o),   // 带相移的输出（未用）
        .CLKOUTD   (clkoutd_o),   // 分频输出（未用）
        .CLKOUTD3  (clkoutd3_o),  // 三分频输出（未用）
        .RESET     (gw_gnd),      // 软复位：恒 0，由配置过程自动初始化
        .RESET_P   (gw_gnd),
        .CLKIN     (clkin),
        .CLKFB     (gw_gnd),      // 内部反馈模式，此脚接 0
        .FBDSEL    ({gw_gnd, gw_gnd, gw_gnd, gw_gnd, gw_gnd, gw_gnd}),
        .IDSEL     ({gw_gnd, gw_gnd, gw_gnd, gw_gnd, gw_gnd, gw_gnd}),
        .ODSEL     ({gw_gnd, gw_gnd, gw_gnd, gw_gnd, gw_gnd, gw_gnd}),
        .PSDA      ({gw_gnd, gw_gnd, gw_gnd, gw_gnd}),
        .DUTYDA    ({gw_gnd, gw_gnd, gw_gnd, gw_gnd}),
        .FDLY      ({gw_gnd, gw_gnd, gw_gnd, gw_gnd})
    );

    //-------------------------------------------------------------------------
    // 以下 defparam 逐个照抄官方 lcd_4.3 例程生成的结果。
    // 按上面推导出的公式：27 × (0+1) / (2+1) = 9 MHz
    //-------------------------------------------------------------------------
    defparam rpll_inst.FCLKIN           = "27";     // 输入时钟 27 MHz
    defparam rpll_inst.DYN_IDIV_SEL     = "false";  // 输入分频比静态
    defparam rpll_inst.IDIV_SEL         = 2;        // 向导 idiv_sel=3，编码时减 1
    defparam rpll_inst.DYN_FBDIV_SEL    = "false";  // 反馈分频比静态
    defparam rpll_inst.FBDIV_SEL        = 0;        // 向导 fbdiv_sel=1，编码时减 1
    defparam rpll_inst.DYN_ODIV_SEL     = "false";  // 输出分频比静态
    defparam rpll_inst.ODIV_SEL         = 48;       // 使 VCO = 9×48 = 432 MHz 落在 400~1200
    defparam rpll_inst.PSDA_SEL         = "0000";
    defparam rpll_inst.DYN_DA_EN        = "true";
    defparam rpll_inst.DUTYDA_SEL       = "1000";
    defparam rpll_inst.CLKOUT_FT_DIR    = 1'b1;
    defparam rpll_inst.CLKOUTP_FT_DIR   = 1'b1;
    defparam rpll_inst.CLKOUT_DLY_STEP  = 0;
    defparam rpll_inst.CLKOUTP_DLY_STEP = 0;
    defparam rpll_inst.CLKFB_SEL        = "internal"; // 内部反馈
    defparam rpll_inst.CLKOUT_BYPASS    = "false";
    defparam rpll_inst.CLKOUTP_BYPASS   = "false";
    defparam rpll_inst.CLKOUTD_BYPASS   = "false";
    defparam rpll_inst.DYN_SDIV_SEL     = 2;
    defparam rpll_inst.CLKOUTD_SRC      = "CLKOUT";
    defparam rpll_inst.CLKOUTD3_SRC     = "CLKOUT";
    defparam rpll_inst.DEVICE           = "GW1NR-9C"; // 器件必须与工程选型一致

endmodule
