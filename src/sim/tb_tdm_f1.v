//=============================================================================
// tb_tdm_f1.v —— F1 现场验证证据：TDM 测试模式的"N 个独立谱峰"
//
// 【赛题原文】测试模式输出多路不同频率音频，频谱可观测【对应数量】独立谱峰。
// 【本台回答】512 个时隙各占一个频率格 → 频谱上是否真的有 512 个独立峰？
//
// 【为什么重做】旧的"32 谱峰"证据产生于全并行引擎 + fs=46875 时代；
//   现在是 TDM 512 时隙 + fs=52734.375（栅格 225Hz + slot×27.7Hz），
//   证据必须与实际固件一致，否则答辩时对不上。
//
// 【方法】复位后先经 UART 写 [0x40][0x01] 关掉全部效果器（A1：reg_bank 上电默认
//   0xDC = 延迟/合唱/混响全开+干声关，会污染谱形；此写顺带验证 UART 通路）→
//   等启动装载与包络进入延音 → 连续采 16384 个样本
//   （FFT 分辨率 3.2Hz，Hann 主瓣 ≈12.9Hz ≪ 栅格间距 27.7Hz → 无合并风险）
//   → Python 侧数峰并对照理论栅格（f1_check_tdm.py）。
//
// 【采样点】dut 内部 audio 总线（FX 默认干声 = 引擎输出）；
//   以 dac_ws 的【任一跳变】为采样事件——LRCK 每 512 拍跳一次 = 每样本一次。
//
// 用法（运行目录需 sine256/note_inc/preset_part/recip_inc 四个 hex，
//       从 src/gowin/tdm_synth/ 取）：
//   iverilog -g2005 -o f1.vvp -s tb_tdm_f1
//     src/rtl/{audio_clk_en,osc_env,pitch_mod,note_map,song_seq,reg_bank,
//              uart_rx,uart_tx,fx_delay,i2s_tx,tdm_engine,tdm_top}.v
//     src/sim/tb_tdm_f1.v
//   vvp f1.vvp  →  f1_samples.txt
//   python tools/scripts/f1_check_tdm.py --simdir <目录>
//=============================================================================

`timescale 1ns/1ps

module tb_tdm_f1;

    localparam NSAMP   = 16384;
    localparam BOOTWAIT = 2_100_000;   // ≈4100 个样本周期：等包络走完起音+衰减、进入延音段再采（旧值 6000 拍=11.7 样本，采在瞬态里 → 频谱被 AM 边带污染）

    reg clk = 1'b0;
    always #18.519 clk = ~clk;    // 27 MHz

    reg  rst_n = 1'b0;
    reg  ev_valid = 1'b0, ev_on = 1'b0;
    reg  [6:0] ev_note = 7'd0;
    reg  [3:0] ev_vel  = 4'd0;
    reg  [1:0] preset  = 2'd0;
    reg        test_mode = 1'b1;    // ★ 测试档（引脚直入；Power-on 也受 cst 上/下拉影响，
                                       //  仿真里显式给 1 不依赖引脚语义）
    reg  uart_rx_pin = 1'b1;         // 串口空闲高
    wire uart_tx_pin, dac_din, dac_ws, dac_bck, pa_en;
    wire [5:0] led;

    tdm_top dut (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(preset), .test_mode(test_mode),
        .uart_rx_pin(uart_rx_pin), .uart_tx_pin(uart_tx_pin),
        .led(led), .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck),
        .pa_en(pa_en)
    );

    integer fd, n;

    //-------------------------------------------------------------------------
    // UART BFM：115200 8N1，按 27MHz 时钟数拍（234.375 拍/bit，取 234，
    //   20 bit 帧累计漂移 ~9ns ≪ 半位 4.3µs，uart_rx 中点采样无碍）
    //-------------------------------------------------------------------------
    localparam BITCLK = 234;
    task send_byte(input [7:0] b);
        integer i;
        begin
            uart_rx_pin = 1'b0;                      // 起始位
            repeat (BITCLK) @(posedge clk);
            for (i = 0; i < 8; i = i + 1) begin      // LSB first
                uart_rx_pin = b[i];
                repeat (BITCLK) @(posedge clk);
            end
            uart_rx_pin = 1'b1;                      // 停止位
            repeat (BITCLK) @(posedge clk);
        end
    endtask

    task reg_write(input [7:0] addr, input [7:0] data);
        begin
            send_byte(addr);
            send_byte(data);
        end
    endtask

    initial begin
        $dumpoff;   // 不 dump 波形——8.4M 拍的 VCD 会撑爆磁盘
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (200) @(posedge clk);

        // ★ A1 对策：清掉上电垃圾参数（效果器全关 + 颤音/滑音清零）
        reg_write(8'h40, 8'h01);   // FX: 干声直通（bit1/2/6 全灭）
        reg_write(8'h30, 8'h00);   // VIB_INC 清零
        reg_write(8'h31, 8'h00);
        reg_write(8'h32, 8'h00);
        reg_write(8'h33, 8'h00);   // VIB_DEPTH 清零（默认 0x9E06=40454 → ±61% 调频！）
        reg_write(8'h34, 8'h00);
        reg_write(8'h35, 8'h00);   // GLIDE_STEP 清零
        reg_write(8'h36, 8'h00);
        $display("[PROBE] 写后 R[40]=%02x R[33]=%02x R[34]=%02x R[30]=%02x（期望 01/00/00/00）",
                 dut.u_reg.mem[8'h40], dut.u_reg.mem[8'h33], dut.u_reg.mem[8'h34], dut.u_reg.mem[8'h30]);

        // 等启动装载完成 + 全部时隙包络进入延音段 + 流水排空
        repeat (BOOTWAIT) @(posedge clk);   // 等待以拍计，但时长按样本周期设计

        fd = $fopen("f1_samples.txt", "w");
        if (fd == 0) begin
            $display("[ERROR] 打不开 f1_samples.txt");
            $finish;
        end

        for (n = 0; n < NSAMP; n = n + 1) begin
            @(posedge dac_ws);  // ★ LRCK 上升沿 = 每帧一次（半帧翻转一次，两个沿都采会把时间轴拉长一倍、频率全部减半——上一轮 55.79% 谱外能量的真因）
            #1;
            $fdisplay(fd, "%0d", $signed(dut.audio));
        end
        $fclose(fd);

        $display("==============================================");
        $display(" F1 采样完成：%0d 样本（fs=52734.375 Hz）", NSAMP);
        $display(" 栅格预期：f = 225 Hz + slot × 27.7 Hz，slot=0..511");
        $display("==============================================");
        $finish;
    end

    // 硬超时兜底
    initial begin
        #4_000_000_000;   // 4 s 仿真时间
        $display("[TIMEOUT] 强制结束（采样不足则判据脚本会报缺数据）");
        $finish;
    end

endmodule
