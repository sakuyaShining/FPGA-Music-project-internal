//=============================================================================
// tb_padseq.v —— 【快判据】复现"切换按键"序列，定位"位置 1 起音不足"
//
// 【为什么要这一条（2026-10-07）】
//   `tb_show +show=0` 的产物里，同一段音频的相邻两次按键电平差约 25 倍
//   （位置 0 峰值 303k / 位置 1 峰值 92k）。
//   但 `tb_padprobe.v` 的**逐键隔离**测试表明：单独按 pad0 或单独按 pad1，
//   输出几乎逐位相同（稳态 RMS 163,334 vs 161,720）⇒ **不是键本身的缺陷**。
//   ⇒ 差异必然来自**"切换"这件事**（前一个键松开、紧接着按下一个键）。
//
//   本判据精确复现该序列，并把**事件时序**打出来：
//     t1: 按 pad0 → 保持 HOLD
//     t2: 松开 pad0（同时按 pad1）
//     t3: 保持 HOLD
//     t4: 松开 pad1
//   记录每次 note-on / note-off 的样本号与音符号，以及各阶段的在响组数。
//
// 【判据（Python 侧）】
//   S1 两次 note-on 都必须出现（note=48 → note=49）
//   S2 第二段（pad1 按住）的稳态 RMS 应与第一段**同量级**
//      —— 若显著偏低，即复现"切换导致起音不足"，并可用事件时序定位原因
//
// 【用法】`+hold=<样本数>`（默认 8000，越小跑得越快）
//=============================================================================
`timescale 1ns/1ps

module tb_padseq;

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
    integer hold_len;

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

    //   事件探针：把每一次 note-on / note-off 连同"当时的在响组数"记下来
    //   注：Icarus 不允许 `function` 无端口，故用 task + 全局变量。
    integer n_on, n_off;
    integer gact_cnt, k;
    task count_gact;
        begin
            gact_cnt = 0;
            for (k = 0; k < 32; k = k + 1)
                if (u_top.u_nm.gact[k]) gact_cnt = gact_cnt + 1;
        end
    endtask

    //   ★ 组状态快照：打出"哪个组在响、其音符号是什么"。
    //     本轮关键探针 —— 要回答"note 49 是否复用了 note 48 刚释放的那一组"。
    task dump_active_groups;
        begin
            $write("     [组状态] t=%0d 在响组:", ns);
            for (k = 0; k < 32; k = k + 1)
                if (u_top.u_nm.gact[k])
                    $write(" g%0d(note=%0d)", k, u_top.u_nm.gtab[k]);
            $write("\n");
        end
    endtask

    always @(posedge clk) begin
        if (rst_n) begin
            if (u_top.pp_on_p) begin
                n_on = n_on + 1;
                count_gact;
                $display("   [t=%6d] note-ON  note=%0d  在响组数=%0d",
                         ns, u_top.pp_ev_note, gact_cnt);
                dump_active_groups;
            end
            if (u_top.pp_off_p) begin
                n_off = n_off + 1;
                count_gact;
                $display("   [t=%6d] note-OFF note=%0d  在响组数=%0d",
                         ns, u_top.pp_ev_note, gact_cnt);
                dump_active_groups;
            end
        end
    end

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
        if (!$value$plusargs("hold=%d", hold_len)) hold_len = 8000;

        $display("==============================================================");
        $display(" 切换序列复现：pad0 按住 → 松开并同时按 pad1 → 松开");
        $display(" hold=%0d 样本", hold_len);
        $display("==============================================================");

        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;
        ns = 0; n_on = 0; n_off = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (5000) @(posedge clk);

        fout = $fopen("padseq.txt", "w");
        if (fout == 0) begin $display("无法创建 padseq.txt"); $finish; end

        $display(" [A] 静息基线");
        rec(1000);
        count_gact;
        $display("     在响组数=%0d", gact_cnt);
        dump_active_groups;

        $display(" [B] 按 pad0（期望 note=48）");
        disch_time[0] = 95;
        rec(hold_len);
        count_gact;
        $display("     在响组数=%0d", gact_cnt);
        dump_active_groups;

        $display(" [C] 松开 pad0，同时按 pad1（期望 note-off 48 / note-on 49）");
        disch_time[0] = 30;
        disch_time[1] = 95;
        rec(hold_len);
        count_gact;
        $display("     在响组数=%0d", gact_cnt);
        dump_active_groups;

        $display(" [D] 松开 pad1");
        disch_time[1] = 30;
        rec(4000);
        count_gact;
        $display("     在响组数=%0d", gact_cnt);
        dump_active_groups;

        $fclose(fout);
        $display("--------------------------------------------------------------");
        $display(" 统计：note-on %0d 次，note-off %0d 次", n_on, n_off);
        $display(" 已写 padseq.txt（%0d 样本）", ns);
        $display("==============================================================");
        $display("RESULT padseq=DONE hold=%0d on=%0d off=%0d", hold_len, n_on, n_off);
        $finish;
    end

    initial begin
        #900_000_000;
        $display("RESULT padseq=TIMEOUT on=%0d", n_on);
        $finish;
    end

endmodule
