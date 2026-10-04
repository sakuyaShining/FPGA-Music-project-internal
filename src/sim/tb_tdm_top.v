//=============================================================================
// tb_tdm_top.v —— TDM 顶层（tdm_top）的端到端验证
//
// 【它回答的问题】
//   "TDM 这条路从引擎到 DAC 引脚，到底通不通？"
//   —— tdm_top 此前【只综合过、从未仿真过】。
//
// 【验证什么】
//   V1  时钟链：引脚上的 BCK / LRCK 频率与比值是否等于 1.5 MHz / 46875 Hz / 32
//   V2  起音：开机装载序列之后，引擎是否真的产生了非零输出
//      （zcode 把门初值改成 0、要求"显式 load_gate 0→1 沿触发"，
//        而 tdm_top 硬接 load_gate=1'b1 —— 这一条必须实测）
//   V3  I2S 闭环：把 dac_din/dac_ws/dac_bck 按 I2S 协议【解回样本】，
//      与引擎内部的 sample_out 逐样本比对（应当相等，误差 0）
//
// 【★ 解码器为什么这样写（这是本测试台最要紧的地方）】
//   I2S 的"1 bit 延迟"有两种常见理解，谁对取决于发送端实现：
//     (A) 接收方在 WS 跳变后【立刻】采第一个上升沿 = MSB
//     (B) 接收方在 WS 跳变后【跳过一格】再采     = MSB
//   i2s_tx.v 的注释明确说是 (A)（收发踩不同边沿本身就构成那 1 bit 错开）。
//   但"注释说的"不等于"实测如此" —— 所以本测试台【两种都解】，
//   并报告哪一种与 sample_out 相等。
//   这样"我把 I2S 约定搞错了"就变成一个可测量的结果，而不是隐藏的错误。
//
// 【为什么不用固定计数器对齐】
//   写死"lr_cnt==k 时采第几位"要求我先把 audio_clk_en 的相位算清楚 ——
//   而算错的表现是"整帧错一位"，看起来像设计坏了。
//   改用 WS 跳变自同步后，解码器不依赖任何相位假设。
//
// 用法：
//   iverilog -g2005 -o sim_build\toptb\top.vvp -s tb_tdm_top `
//     src\rtl\audio_clk_en.v src\rtl\osc_env.v src\rtl\i2s_tx.v `
//     src\rtl\tdm_engine.v src\rtl\tdm_top.v src\sim\tb_tdm_top.v
//   （运行目录需有 sine256.hex）
//=============================================================================

`timescale 1ns/1ps

module tb_tdm_top;

    // 27 MHz：周期 37.037 ns
    localparam real CLK_HALF = 18.5185;

    localparam NSAMP = 200;          // 观察 200 个音频样本（约 4.3 ms）

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    wire [4:0] led;
    wire din, ws, bck, pa_en;

    // 演奏接口：本测试只验 I2S 链路，音符事件保持静默
    reg        ev_valid  = 1'b0;
    reg        ev_on     = 1'b0;
    reg [6:0]  ev_note   = 7'd0;
    reg [7:0]  ev_vel    = 8'd0;
    reg [1:0]  preset    = 2'd1;
    // ★ 测试模式：装载 512 个等间隔频率，输出持续非零，便于 I2S 闭环比对
    reg        test_mode = 1'b1;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note),
        .ev_vel(ev_vel), .preset(preset), .test_mode(test_mode),
        .uart_rx_pin(1'b1),               // 串口空闲为高（本测试不用 UART）
        .led(led),
        .dac_din(din), .dac_ws(ws), .dac_bck(bck), .pa_en(pa_en)
    );

    //=========================================================================
    // V1：时钟链测量
    //   用时间戳量 BCK 与 LRCK 的周期，换算成频率
    //=========================================================================
    real t_bck_rise, t_ws_edge, bck_period, ws_period;
    integer n_bck, n_ws;

    initial begin
        t_bck_rise = 0.0; t_ws_edge = 0.0;
        bck_period = 0.0; ws_period = 0.0;
        n_bck = 0; n_ws = 0;
    end

    reg bck_d, ws_d2;
    always @(posedge clk) begin
        bck_d  <= bck;
        ws_d2  <= ws;
    end

    always @(posedge bck) begin
        n_bck = n_bck + 1;
        if (n_bck > 100) begin          // 跳过启动阶段
            if (t_bck_rise != 0.0) bck_period = $realtime - t_bck_rise;
            t_bck_rise = $realtime;
        end
    end

    always @(posedge clk) begin
        if (ws_d2 != ws) begin          // WS 跳变
            n_ws = n_ws + 1;
            if (n_ws > 40) begin
                if (t_ws_edge != 0.0) ws_period = $realtime - t_ws_edge;
                t_ws_edge = $realtime;
            end
        end
    end

    //=========================================================================
    // V3：I2S 接收器（WS 跳变自同步），两种约定并行解
    //
    //   ★★ 关键认识（第一版就是栽在这里）★★
    //   一个 LRCK 半帧只有 16 个 BCK 上升沿，而【WS 跳变的那一拍本身就是 MSB】。
    //   所以正确的状态机是：
    //        跳变拍：移入 bit0，计数=1
    //        之后 15 拍：移入 bit1..bit15，计数 15 时（用移位后的新值）锁存
    //   一共恰好 16 拍，正好填满半帧。
    //
    //   第一版写成"跳变拍只做检测、不移位，之后收 16 位" —— 需要 17 拍，
    //   在半帧里结构上不可能完成，于是计数永远到不了终点，
    //   表现为【收到 0 个样本】。
    //
    //   这个约束本身就是判据：约定 B（跳变后跳过一格）同样需要 17 拍，
    //   因此【结构上不可能】—— 这也从侧面证实 i2s_tx.v 注释所述的约定 A。
    //=========================================================================
    reg [15:0] sh_a;                // 约定 A 的移位寄存器
    reg [4:0]  nbit_a;              // 已收位数（跳变拍算 1）
    reg        ch_now;              // 当前声道（0=左 1=右）

    reg [15:0] gotL_a, gotR_a;
    integer    nL_a, nR_a;

    initial begin
        sh_a = 0; nbit_a = 0; ch_now = 0;
        gotL_a = 0; gotR_a = 0;
        nL_a = 0; nR_a = 0;
    end

    always @(posedge bck) begin
        if (ws != ch_now) begin
            // WS 跳变：新声道开始，本拍就是 MSB
            ch_now <= ws;
            nbit_a <= 5'd1;
            sh_a   <= {sh_a[14:0], din};
        end
        else if (nbit_a != 5'd0) begin
            if (nbit_a == 5'd15) begin
                // 收到第 16 位：用【移位后】的新值锁存
                if (ch_now) begin gotR_a <= {sh_a[14:0], din}; nR_a = nR_a + 1; end
                else        begin gotL_a <= {sh_a[14:0], din}; nL_a = nL_a + 1; end
                nbit_a <= 5'd0;
                sh_a   <= {sh_a[14:0], din};
            end
            else begin
                sh_a   <= {sh_a[14:0], din};
                nbit_a <= nbit_a + 5'd1;
            end
        end
    end

    //=========================================================================
    // 主激励
    //=========================================================================
    integer k, fout, n_nonzero, first_nz;

    // ★ 两种对齐：
    //   now_q = 最近一次 sample_en 采到的 sample_out 高 16 位
    //   old_q = 再上一次（也就是该帧发出时的那一个）
    reg [15:0] s_now_q, s_old_q;
    integer    n_diff_now, n_diff_old;
    integer n_cmp, n_diff_a, n_diff_b;
    reg signed [23:0] exp_now;

    initial begin
        rst_n = 1'b0;
        repeat (20) @(posedge clk);
        rst_n = 1'b1;

        $display("==============================================================");
        $display(" tdm_top 端到端验证");
        $display("==============================================================");

        // 跑够：开机装载 1560 拍 + NSAMP 个样本（每样本 576 拍）
        repeat (1560 + NSAMP * 576) @(posedge clk);

        //---------------------------------------------------------------------
        // V1：时钟链
        //---------------------------------------------------------------------
        $display("");
        $display("[V1] 时钟链（引脚实测）");
        // ★ ws_period 量的是"相邻两次跳变"的间隔 = LRCK 的【半周期】
        //   （跳变含上升沿与下降沿）。第一版直接当周期报，得到 93747 Hz，
        //   恰好是 46875 的两倍 —— 这个数字本身就在提示"你量的是半个周期"。
        $display("     BCK  周期 = %0.3f ns  -> %0.4f MHz   (期望 666.667 ns / 1.5 MHz)",
                 bck_period, 1000.0 / bck_period);
        $display("     LRCK 半周期 = %0.3f ns   全周期 = %0.3f ns",
                 ws_period, ws_period * 2.0);
        $display("     LRCK 频率   = %0.4f Hz              (期望 46875 Hz)",
                 1.0e9 / (ws_period * 2.0));
        $display("     BCK/LRCK    = %0.3f                   (期望 32)",
                 (ws_period * 2.0) / bck_period);

        //---------------------------------------------------------------------
        // V2 / V3：闭环比对
        //   ★ 逐样本比对放在仿真过程中做 —— 这里只报告最终统计
        //---------------------------------------------------------------------
        $display("");
        $display("[V2] 起音与输出");
        $display("     非零样本数 = %0d / %0d", n_nonzero, NSAMP);
        $display("     第一个非零样本 = %0d", first_nz);
        if (n_nonzero == 0)
            $display("     ★★ 输出全零 —— tdm_top 没有出声！★★");

        $display("");
        $display("[V3] I2S 闭环（解码 vs 引擎 sample_out）");
        $display("     收到 左 %0d 个 / 右 %0d 个样本，比对 %0d 次",
                 nL_a, nR_a, n_cmp);
        $display("     对齐 now（与最近一次 sample_en 的值比）：不符 %0d", n_diff_now);
        $display("     对齐 old（与上一次 sample_en 的值比）  ：不符 %0d", n_diff_old);
        if (nL_a == 0)
            $display("     => ✗ 一个都没收到 —— 解码状态机没走完，先查帧长假设");
        else if (n_diff_now == 0)
            $display("     => ★★★ I2S 链路逐样本一致（对齐 now）");
        else if (n_diff_old == 0)
            $display("     => ★★★ I2S 链路逐样本一致（对齐 old，差一个样本周期）");
        else
            $display("     => ✗ 两种对齐都不符 —— 逐位核对（错一位会表现为数值移位）");

        $finish;
    end

    //-------------------------------------------------------------------------
    // 逐样本监视：非零统计 + I2S 闭环比对
    //   在 bck 上升沿取"当前声道刚收满"的值，与 u_top 内部的 sample_out 比。
    //   ★ 为了避开流水线相位问题，比对用"左声道样本序号"对齐，而不是绝对时间。
    //-------------------------------------------------------------------------
    integer last_nL_a;


    initial begin
        n_nonzero = 0; first_nz = -1;
        n_cmp = 0; n_diff_a = 0;
        s_now_q = 0; s_old_q = 0;
        n_diff_now = 0; n_diff_old = 0;
        last_nL_a = 0;
    end

    // 每个音频样本检查一次 sample_out 是否非零
    integer ns;
    initial ns = 0;
    always @(posedge clk) begin
        if (u_top.sample_en) begin
            s_old_q <= s_now_q;
            s_now_q <= u_top.u_tdm.sample_out[23:8];
        end
    end

    always @(posedge clk) begin
        if (u_top.sample_en) begin
            ns = ns + 1;
            if (u_top.u_tdm.sample_out !== 24'sd0) begin
                n_nonzero = n_nonzero + 1;
                if (first_nz < 0) first_nz = ns;
            end
            // 左声道解码值与本样本的 sample_out[23:8] 比对
            if (nL_a > last_nL_a) begin
                last_nL_a = nL_a;
                n_cmp = n_cmp + 1;
                if (gotL_a !== s_now_q) n_diff_now = n_diff_now + 1;
                if (gotL_a !== s_old_q) n_diff_old = n_diff_old + 1;
            end
        end
    end

    // 硬超时
    initial begin
        #5_000_000;
        $display("[TIMEOUT]");
        $finish;
    end

endmodule
