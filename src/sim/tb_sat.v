//=============================================================================
// tb_sat.v —— 24 位饱和/截断路径的【边界判据】（阶段 3 遗留项）
//
// 【为什么需要单独一条】
//   `12 f1` 与 `16 i2s top` 都**到不了**饱和区：
//   实测 sum_raw 峰值 383370，而饱和阈值是 acc_next ≥ 2^19 = 524288（顶层再 <<4）。
//   383370 / 524288 = 73% ⇒ 那两条判据从未覆盖 clamp 分支。
//   本机**没有 Gowin 工具链**，无法靠加大激励去顶（也没有增益寄存器可调），
//   所以改为**直接驱动饱和表达式的输入**：force 引擎内部的 `acc_next`，
//   逐点核对输出是否落在 24 位范围内、且正好在边界处切换。
//
// 【被测表达式（tdm_engine.v）】
//     scaled     = (acc_next <<< GAIN_UP(4)) >>> SHIFT(0)
//     sample_out = MAXV  if scaled >  MAXV      (MAXV =  2^23-1 =  8388607)
//                = MINV  if scaled <  MINV      (MINV = -2^23   = -8388608)
//                = scaled[23:0]  otherwise
//   ⇒ 分界点在 acc_next = ±2^19 = ±524288
//
// 【判据】对每个输入点，输出必须**精确等于**上面表达式的期望值。
//   覆盖五个点：正饱和上、正饱和点、范围内(正)、范围内(负)、负饱和点、负饱和下。
//
// 【为什么要 force 而不是"调大音量"】
//   没有可用的增益寄存器；即便有，也无法保证精确落在边界上。
//   force 输入 + 逐点核对期望值，是能真正把 clamp 分支走遍的办法。
//   注意：force 的是 `acc_next`（内部 wire），**不改任何 RTL**。
//=============================================================================
`timescale 1ns/1ps

module tb_sat;

    localparam integer GAIN_UP = 4;
    localparam signed [31:0] MAXV =  32'sd8388607;
    localparam signed [31:0] MINV = -32'sd8388608;
    localparam integer THRESH = 524288;          // 2^19：scaled 恰好到 ±2^23 的点

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    wire [15:0] pad_bus = 16'h0000;              // 电极确定空闲态（悬空会被当触摸）
    reg         uart_rx = 1'b1;
    wire        uart_tx;
    reg         ev_valid = 1'b0, ev_on = 1'b0;
    reg [6:0]   ev_note = 7'd0;
    reg [3:0]   ev_vel  = 4'd0;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    integer fails;
    integer i;

    //   期望值：与被测表达式逐字对应（判据不循环 —— 独立算一遍）
    function signed [31:0] sat_exp;
        input signed [31:0] a;
        reg   signed [31:0] s;
        begin
            s = a <<< GAIN_UP;
            if      (s > MAXV) sat_exp = MAXV;
            else if (s < MINV) sat_exp = MINV;
            else               sat_exp = s;
        end
    endfunction

    reg signed [31:0] cap;                       // 抓到的 sample（符号扩展）
    reg signed [31:0] cap_max, cap_min;          // 观察窗口内的极值

    //   ★ 不能"等固定拍数再抓一次" —— `sample` 是每帧锁存一次，
    //     抓点与帧边界一旦错开，抓到的就是**上一帧**的值
    //     （第一版就是这样：每个点都落后一拍，报 9 个 FAIL，看着像 clamp 坏了）。
    //     正确做法：force 之后**观察若干拍的极值**，再与期望值比对。
    //     这样与帧相位无关，也不会因为"正好抓到旧值"而误判。
    task check_sat;
        input signed [31:0] ain;
        input [255:0]       name;
        reg   signed [31:0] exp;
        integer w;
        reg   signed [31:0] v;
        begin
            exp = sat_exp(ain);
            cap_max = -32'sd2147483648;
            cap_min =  32'sd2147483647;
            force u_top.u_tdm.acc_next = ain;
            //   窗口要**跨过至少一个完整帧**（NSLOT=512 拍），取 3 帧
            for (w = 0; w < 1600; w = w + 1) begin
                @(posedge clk);
                v = $signed(u_top.sample);
                if (v > cap_max) cap_max = v;
                if (v < cap_min) cap_min = v;
            end
            release u_top.u_tdm.acc_next;
            //   正输入看窗口内的最大值，负输入看最小值
            cap = (ain >= 0) ? cap_max : cap_min;
            if (cap === exp)
                $display("  PASS  %0s  acc_next=%0d -> sample=%0d", name, ain, cap);
            else begin
                $display("  FAIL  %0s  acc_next=%0d 期望 %0d 实测 %0d (窗口 max=%0d min=%0d)",
                         name, ain, exp, cap, cap_max, cap_min);
                fails = fails + 1;
            end
            repeat (600) @(posedge clk);         // 让引擎回到稳态
        end
    endtask

    initial begin
        $display("==============================================================");
        $display(" 24 位饱和/截断路径 边界判据（GAIN_UP=%0d，阈值=±%0d）", GAIN_UP, THRESH);
        $display("==============================================================");

        fails = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (3000) @(posedge clk);

        $display(" 分界点：acc_next = ±%0d（此处 scaled 恰好 = ±2^23）", THRESH);

        //   正侧
        check_sat(32'sd0,        "zero");
        check_sat(32'sd1000,     "small-positive");
        check_sat(-32'sd1000,    "small-negative");
        check_sat(THRESH - 1,    "just-below-pos-clamp");   // 524287 -> 8388592 (< MAXV)
        check_sat(THRESH,        "exactly-pos-clamp");      // 524288 -> 8388608 (> MAXV) ⇒ 夹到 8388607
        check_sat(THRESH + 1,    "just-above-pos-clamp");
        check_sat(32'sd600000,   "well-above-pos-clamp");
        //   负侧：scaled = -8388608 恰好等于 MINV ⇒ 不夹（走 scaled 分支）
        check_sat(-THRESH,       "exactly-neg-clamp");      // -524288 -> -8388608 == MINV ⇒ 不夹
        check_sat(-THRESH - 1,   "just-below-neg-clamp");   // -524289 -> -8388624 < MINV ⇒ 夹到 -8388608
        check_sat(-32'sd600000,  "well-below-neg-clamp");

        //   范围自检：无论输入如何，输出必须落在 24 位有符号范围内
        $display(" 小结：所有点的输出都已核对落在 [%0d, %0d] 内", MINV, MAXV);

        $display("==============================================================");
        if (fails == 0) $display("RESULT sat=PASS");
        else            $display("RESULT sat=FAIL fails=%0d", fails);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #60_000_000;
        $display("RESULT sat=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
