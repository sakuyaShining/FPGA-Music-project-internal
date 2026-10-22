//=============================================================================
// tb_latency.v —— 控制信号 → 音频输出【总延迟】实测（拓展 E5）
//
// 【为什么要测而不是算】
//   报告里写"延迟 ≤5 ms"必须有依据。这里在仿真里逐拍量出来，
//   并且证明它是【确定性的】—— 这正是 E5 的要求："≤5 ms 且确定性无抖动延迟"。
//
// 【测两个点】
//   t_smp：ev_valid 上升沿 → 引擎 sample_out 首次非零（合成完成）
//   t_pin：ev_valid 上升沿 → I2S 串行流里【解码出】首个非零左声道样本
//          （= DAC 输入端，物理上最有意义的那一端）
//
// 【为什么要扫"事件落在样本周期内的位置"】
//   控制事件是异步的，装载必须等到【下一个样本边界】才生效，
//   所以延迟必然含一个"相位项"（0 ~ 一个样本周期 = 576 拍 = 21.3 µs）。
//   这不是抖动（无随机、无仲裁、无软件），而是【可解析预测的确定量】。
//
// 【为什么必须"每个相位跑一次全新仿真"，而不是一次跑 6 个相位】
//   引擎的时隙状态（BSRAM）【没有复位分支】—— 这是设计的自觉选择：
//   "BSRAM 上电本来就是 0，根本不需要清零这个动作"（见 tdm_engine.v 注释）。
//   因此在仿真中途拉 rst_n 并不会让上一音消失，于是"首次非零"根本无法定义。
//   第一版就在这儿栽了两次：6 次测量里 5 次 t_smp = 1 拍（假值）。
//   ⇒ 每个相位一次上电冷启动，用 +phase=N 传给测试台。
//
// 【时间基准】clk = 27 MHz（37.037 ns），fs = 46875 Hz，每样本 576 拍
//=============================================================================

`timescale 1ns/1ps

module tb_latency;

    localparam real CLK_HALF = 18.5185;      // 37.037 ns -> 27 MHz
    localparam integer PERIOD = 576;

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    reg        ev_valid = 1'b0;
    reg        ev_on    = 1'b0;
    reg [6:0]  ev_note  = 7'd0;
    reg [3:0]  ev_vel   = 4'd0;
    reg [1:0]  preset   = 2'd1;
    reg        test_mode = 1'b0;

    wire [5:0] led;
    wire       dac_din, dac_ws, dac_bck, pa_en;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note),
        .ev_vel(ev_vel), .preset(preset), .test_mode(test_mode),
        .uart_rx_pin(1'b1),               // 串口空闲为高（本测试不用 UART）
        .led(led), .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck), .pa_en(pa_en)
    );

    // 目标音的基频 inc（直接从 note_map 的表里取，避免手写常量过期）
    //   必须声明在使用之前（Verilog 对 wire 的"先用后声明"会报
    //     "Unable to bind" —— 本项目已经栽过两次，记在这里）
    wire [23:0] u_nm_inc69 = u_top.u_nm.note_rom[69];

    //-------------------------------------------------------------------------
    // I2S 接收（与 tb_tdm_top 同一套约定：WS 跳变那一拍就是 MSB，半帧 16 拍）
    //-------------------------------------------------------------------------
    reg [15:0] sh;
    reg [4:0]  nbit;
    reg        ch_now;
    reg [15:0] gotL;
    reg        gotL_v;

    initial begin sh = 0; nbit = 0; ch_now = 0; gotL = 0; gotL_v = 0; end

    always @(posedge dac_bck) begin
        if (dac_ws != ch_now) begin
            ch_now <= dac_ws;
            nbit   <= 5'd1;
            sh     <= {sh[14:0], dac_din};
        end
        else if (nbit != 5'd0) begin
            if (nbit == 5'd15) begin
                if (!ch_now) begin
                    gotL   <= {sh[14:0], dac_din};
                    gotL_v <= 1'b1;
                end
                nbit <= 5'd0;
                sh   <= {sh[14:0], dac_din};
            end
            else begin
                sh   <= {sh[14:0], dac_din};
                nbit <= nbit + 5'd1;
            end
        end
    end

    //-------------------------------------------------------------------------
    // 判"非零"必须用【双向数值比较】，不能用 `!== 0`：
    //   仿真里未初始化的 x 满足 `x !== 0`，会在第 1 拍就误触发。
    //   而 `>0` / `<0` 在 x 上求值为 x → if 视为假
    //-------------------------------------------------------------------------
    function busy_smp;
        input dummy;
        begin
            busy_smp = (u_top.u_tdm.sample_out > 24'sd0) ||
                       (u_top.u_tdm.sample_out < 24'sd0);
        end
    endfunction

    function nonzero_l;
        input [15:0] v;
        begin
            nonzero_l = ($signed(v) > 16'sd0) || ($signed(v) < 16'sd0);
        end
    endfunction

    integer ph, cnt, t_smp, t_pin;
    integer prefill, i2;
    reg     done_s, done_p;
    real    clk_ns;
    integer t_load;                     // 事件 → 目标组 inc 生效（组号依赖项）
    reg     done_l;

    initial begin
        clk_ns = 2.0 * CLK_HALF;
        ph = 0; prefill = 0;
        if (!$value$plusargs("phase=%d", ph))       ph = 0;
        if (!$value$plusargs("prefill=%d", prefill)) prefill = 0;

        rst_n = 1'b0;
        repeat (40) @(posedge clk);
        rst_n = 1'b1;

        // 冷启动后先确认输出确实是 0（不是 x）
        cnt = 0;
        while ((u_top.u_tdm.sample_out !== 24'sd0) && cnt < 5000) begin
            @(posedge clk);
            cnt = cnt + 1;
        end
        if (u_top.u_tdm.sample_out !== 24'sd0)
            $display("     [警告] 冷启动后输出仍非 0（可能是 x），测量不可信");

        //---- 预填 prefill 个音（把目标音挤到 prefill 号组）----
        //   用于量"组号依赖项"：组号决定该组的时隙在本样本周期里被访问的早晚
        for (i2 = 0; i2 < prefill; i2 = i2 + 1) begin
            @(posedge clk);
            // 预填音必须避开被测的 69 号音：否则 note_map 判成"同音重触发"，
            //   会复用已有组而不是占用新组，组号扫描就白做了（第一版栽在这）。
            ev_note  <= 20 + i2;
            ev_vel   <= 4'd10;
            ev_on    <= 1'b1;
            ev_valid <= 1'b1;
            repeat (64) @(posedge clk);
            ev_valid <= 1'b0;
            repeat (200) @(posedge clk);
        end
        if (prefill > 0) repeat (200) @(posedge clk);   // 让它们进入稳态

        // 对齐到样本边界 + 相位偏移
        @(posedge clk);
        while (!u_top.sample_en) @(posedge clk);
        repeat (ph) @(posedge clk);

        // 发事件（2 拍宽）
        @(posedge clk);
        ev_note  <= 7'd69;                 // A4 = 440 Hz
        ev_vel   <= 4'd10;
        ev_on    <= 1'b1;
        ev_valid <= 1'b1;

        cnt = 0; done_s = 0; done_p = 0; done_l = 0;
        t_smp = -1; t_pin = -1; t_load = -1;
        while ((!done_s || !done_p || !done_l) && cnt < 4000) begin
            @(posedge clk);
            cnt = cnt + 1;
            if (cnt == 2) ev_valid <= 1'b0;
            if (!done_s && busy_smp(1'b0)) begin
                done_s = 1; t_smp = cnt;
            end
            if (!done_p && gotL_v && nonzero_l(gotL)) begin
                done_p = 1; t_pin = cnt;
            end
            // 目标组的基频 inc 变成新音的值 = 这次装载"生效"的时刻
            if (!done_l && (u_top.u_tdm.inc_mem[prefill * 16] === u_nm_inc69)) begin
                done_l = 1; t_load = cnt;
            end
        end

        $display("  相位 %4d 拍 / 预填 %2d 个音：t_smp = %4d (%7.2f us)  t_pin = %4d (%7.2f us)  t_load[组%0d] = %4d (%7.2f us)",
                 ph, prefill, t_smp, t_smp * clk_ns / 1000.0,
                 t_pin, t_pin * clk_ns / 1000.0,
                 prefill, t_load, t_load * clk_ns / 1000.0);
        $display("  RESULT phase=%0d prefill=%0d t_smp=%0d t_pin=%0d t_load=%0d",
                 ph, prefill, t_smp, t_pin, t_load);
        $finish;
    end

    // 硬超时
    initial begin
        #400_000;                          // 400 us 仿真时间（一个样本 21.3 us）
        $display("[TIMEOUT] phase=%0d", ph);
        $finish;
    end

endmodule
