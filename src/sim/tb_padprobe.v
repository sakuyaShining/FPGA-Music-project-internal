//=============================================================================
// tb_padprobe.v —— 【快判据】pad 通路逐键排查：事件 / 声部 / 电平
//
// 【为什么要这一条（2026-10-07）】
//   在 `tb_show +show=0` 的产物里发现：按"键"分组的稳态电平相差约 25 倍
//   （偶位约 226k、奇位约 9k）。已排除：preset 表（全局）、包络参数（编译期常量）、
//   Nyquist、窗错位、音频连续。**仍未解释**，且这是**产品行为**问题（不是判据问题）。
//
//   为把"哪一步断了"定位到具体环节，本判据**直接观测 pad 通路内部信号**，
//   而不是只看输出音频：
//     · pad_pitch 的事件输出（pp_on_p / pp_off_p / pp_ev_note）
//     · note_map 的分配结果（gact 计数）
//     · 引擎输出 audio（写文件，交给 Python 算 RMS）
//
// 【用法】`+pad=N` 选要按的物理键（0..15，默认 0）；`+hold=<样本数>` 按住时长。
//   一次仿真只测一个键 ⇒ 分钟级。逐键跑 0..7 即得"每个键是否正常"的表。
//
// 【判据（由 Python 侧比对）】
//   P1 按下后必须出现**至少一个** note-on 事件（否则该键不通）
//   P2 事件音符号必须等于 48 + pad（BASE=48，通道 i → 音 i）
//   P3 按下期间必须有声部被分配（在响组数 > 0）
//   P4 按住段稳态 RMS 应与参考键同量级 —— 明显偏低即复现 25 倍不对称
//
//   注：RMS 不在本 tb 里算 —— 输出写 padprobe.txt，由 Python 判据算，
//       保持"tb 只采集、判据只分析"的分工。
//=============================================================================
`timescale 1ns/1ps

module tb_padprobe;

    localparam integer NCH = 16;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    wire [NCH-1:0] pad_bus;
    reg            uart_rx = 1'b1;
    wire           uart_tx;
    reg            ev_valid = 1'b0, ev_on = 1'b0;
    reg [6:0]      ev_note = 7'd0;
    reg [3:0]      ev_vel  = 4'd0;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    integer disch_time [0:NCH-1];
    integer drift = 0;
    integer i, ns;
    integer fout;
    integer pad_sel, hold_len;

    genvar gi;
    generate
        for (gi = 0; gi < NCH; gi = gi + 1) begin : gpad
            reg     charged;
            integer dcnt;
            initial begin charged = 1'b0; dcnt = 0; end
            always @(posedge clk) begin
                if (u_top.u_pad.dbg_phase == 2'd0) begin
                    charged <= 1'b1; dcnt <= 0;
                end
                else if (charged && dcnt < disch_time[gi] + drift) dcnt <= dcnt + 1;
                else charged <= 1'b0;
            end
            assign pad_bus[gi] = (u_top.u_pad.dbg_phase == 2'd0) ? 1'bz
                               : (charged ? 1'b1 : 1'b0);
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 事件探针：记下每次 pp_on_p / pp_off_p 及其音符号
    //-------------------------------------------------------------------------
    integer n_on, n_off;
    integer first_on_sample, first_on_note;
    always @(posedge clk) begin
        if (rst_n) begin
            if (u_top.pp_on_p) begin
                if (n_on == 0) begin
                    first_on_sample = ns;
                    first_on_note   = u_top.pp_ev_note;
                end
                n_on = n_on + 1;
                $display("   [event] note-on  样本=%0d note=%0d", ns, u_top.pp_ev_note);
            end
            if (u_top.pp_off_p) begin
                n_off = n_off + 1;
                $display("   [event] note-off 样本=%0d note=%0d", ns, u_top.pp_ev_note);
            end
        end
    end

    //-------------------------------------------------------------------------
    // 声部占用探针
    //-------------------------------------------------------------------------
    integer gact_cnt, k;
    task dump_groups;
        begin
            gact_cnt = 0;
            for (k = 0; k < 32; k = k + 1)
                if (u_top.u_nm.gact[k]) gact_cnt = gact_cnt + 1;
            $display("   [groups] 样本=%0d 在响组数=%0d", ns, gact_cnt);
        end
    endtask

    task rec(input integer n);
        integer q;
        begin
            for (q = 0; q < n; q = q + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
                $fdisplay(fout, "%0d %0d", ns, $signed(u_top.audio));
                ns = ns + 1;
            end
        end
    endtask

    initial begin
        if (!$value$plusargs("pad=%d", pad_sel))   pad_sel = 0;
        if (!$value$plusargs("hold=%d", hold_len)) hold_len = 30000;

        $display("==============================================================");
        $display(" pad 通路逐键排查：pad=%0d hold=%0d", pad_sel, hold_len);
        $display(" （期望音符号 = 48 + pad = %0d）", 48 + pad_sel);
        $display("==============================================================");

        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;
        ns = 0; n_on = 0; n_off = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (5000) @(posedge clk);

        fout = $fopen("padprobe.txt", "w");
        if (fout == 0) begin $display("无法创建 padprobe.txt"); $finish; end

        $display(" [1] 松开基线");
        rec(2000);
        dump_groups;

        $display(" [2] 按下 pad%0d", pad_sel);
        disch_time[pad_sel] = 95;
        rec(hold_len);
        dump_groups;

        $display(" [3] 松开 pad%0d", pad_sel);
        disch_time[pad_sel] = 30;
        rec(8000);
        dump_groups;

        $fclose(fout);
        $display("--------------------------------------------------------------");
        $display(" 统计：note-on %0d 次，note-off %0d 次", n_on, n_off);
        if (n_on > 0)
            $display("       首个 note-on：样本 %0d，note=%0d（期望 %0d）",
                     first_on_sample, first_on_note, 48 + pad_sel);
        else
            $display("       ** 没有收到任何 note-on ⇒ 该键不通 **");
        $display(" 已写 padprobe.txt（%0d 样本）", ns);
        $display("==============================================================");
        $display("RESULT padprobe=DONE pad=%0d on=%0d off=%0d", pad_sel, n_on, n_off);
        $finish;
    end

    initial begin
        #900_000_000;
        $display("RESULT padprobe=TIMEOUT pad=%0d on=%0d", pad_sel, n_on);
        $finish;
    end

endmodule
