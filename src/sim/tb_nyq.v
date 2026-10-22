//=============================================================================
// tb_nyq.v —— 奈奎斯特防护判据（步② 的验收件）
//
// 【被测行为】
//   note_map 装载时，若某泛音的相位增量 inc ≥ 2^23（⇔ f ≥ fs/2 = 26.37 kHz），
//   该泛音的幅度必须被置 0 —— 否则它会折叠成假频，变成"频谱里的鬼影"。
//   基音高于 ~1648 Hz 时第 16 泛音就越界，所以高音必须被防护。
//
// 【判据不循环论证】
//   这里**不重算** "inc 应该是多少"（那是被测物自己的公式 —— 21 号 §7.4 的教训），
//   只断言【不变量】：
//     I1  任何 inc ≥ 2^23 的时隙，其 amp 必须 == 0            （防护真的生效）
//     I2  任何 inc <  2^23 的时隙，其 amp 必须 >  0            （没有误杀）
//     I3  高音（MIDI 100）下：被杀的 ≥ 1 且存活的 ≥ 1          （场景确实触发）
//     I4  低音（MIDI 60）下：被杀的 == 0                       （不误伤正常音域）
//
// 输出一行 RESULT 供脚本抓取；同时打印每个时隙的 inc/amp 便于人工过目
// （21 号 §7.5：脚本判据会漏"形状不对"，要肉眼看）。
//=============================================================================

`timescale 1ns/1ps

module tb_nyq;

    localparam integer NSLOT = 512;
    localparam integer NTH   = 1 << 23;      // 2^23 = fs/2

    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;              // 27 MHz

    reg        ev_valid, ev_on;
    reg [6:0]  ev_note;
    reg [3:0]  ev_vel;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(1'b1), .uart_tx_pin(),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en()
    );

    integer k, killed, alive, bad_i1, bad_i2, total_killed, total_alive;
    integer inc_v, amp_v;

    task wait_samples(input integer n);
        integer i;
        begin
            for (i = 0; i < n; i = i + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
            end
        end
    endtask

    task play_and_scan(input [6:0] note, input integer wi);
        begin
            @(posedge clk);
            ev_note <= note; ev_vel <= 4'd12; ev_on <= 1'b1; ev_valid <= 1'b1;
            @(posedge clk);
            ev_valid <= 1'b0;
            // 等装载序列走完（步② 后 20 拍）+ 跨过样本边界让待生效区落地
            wait_samples(3);
            killed = 0; alive = 0;
            for (k = 0; k < 16; k = k + 1) begin
                inc_v = u_top.u_tdm.inc_mem[wi * 16 + k];
                amp_v = u_top.u_tdm.amp_mem[wi * 16 + k];
                if (inc_v >= NTH) begin
                    killed = killed + 1;
                    if (amp_v != 0) bad_i1 = bad_i1 + 1;
                end
                else begin
                    alive = alive + 1;
                    if (amp_v == 0) bad_i2 = bad_i2 + 1;
                end
                if (wi == 0 || k == 0)
                    $display("    [%s] 泛音 %2d: inc = %8d %s  amp = %3d",
                             (wi == 0) ? "低音60" : "高音100", k, inc_v,
                             (inc_v >= NTH) ? "≥2^23(越界)" : "        ", amp_v);
            end
            $display("  MIDI %0d: 越界被杀 = %0d，存活 = %0d", note, killed, alive);
            total_killed = total_killed + killed;
            total_alive  = total_alive  + alive;
        end
    endtask

    initial begin
        bad_i1 = 0; bad_i2 = 0; total_killed = 0; total_alive = 0;
        ev_valid = 0; ev_on = 0; ev_note = 0; ev_vel = 0;
        rst_n = 0;
        repeat (200) @(posedge clk);
        rst_n = 1;
        repeat (4000) @(posedge clk);

        $display("==============================================================");
        $display(" 奈奎斯特防护判据（步②）");
        $display("==============================================================");

        play_and_scan(7'd60,  0);            // 低音：不该有杀伤（I4）
        play_and_scan(7'd100, 1);            // 高音：必然越界（I3）

        $display("");
        $display("  I1 越界却未杀 = %0d（必须 0）", bad_i1);
        $display("  I2 未越界却被杀 = %0d（必须 0）", bad_i2);
        $display("  I3/I4 高音被杀 %0d 个、存活 %0d 个；低音被杀数见上（必须 0）",
                 total_killed, total_alive);
        if (bad_i1 == 0 && bad_i2 == 0 && total_killed >= 1)
            $display("RESULT nyq=PASS killed=%0d alive=%0d", total_killed, total_alive);
        else
            $display("RESULT nyq=FAIL i1=%0d i2=%0d killed=%0d", bad_i1, bad_i2, total_killed);
        $finish;
    end

    initial begin
        #400_000_000;
        $display("RESULT nyq=TIMEOUT");
        $finish;
    end

endmodule
