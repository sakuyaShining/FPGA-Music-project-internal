//=============================================================================
// tb_padfast.v —— 【快判据】pad 通路"切换丢事件"定位（不录音，秒级）
//
// 【背景（2026-10-07）】
//   · `tb_padseq.v`（含录音）复现出：松开 pad0 的同时按 pad1 ⇒ **pad1 的 note-on 没落地**。
//     但它要录 21000 个样本，**446 秒**才能跑完，不适合迭代。
//   · `tb_evseq.v`（直接在外部事件口打脉冲）**2 秒通过** ⇒
//     **事件队列与 note_map 本身没问题**，丢失是 **pad 通路特有**的。
//
//   本判据保留 pad 通路的完整逻辑（pad_scan 的 RC 模型 + pad_pitch 的扫查仲裁），
//   但**完全不录音**（录音正是那 446 秒的来源 —— 每样本要等 sample_en，
//   512 拍才一个样本）。改为按拍推进，并统计：
//     · 每次 note-on / note-off（音符号、拍号）
//     · note_map 的 ev_ack 次数
//     · 每次事件后"在响组数"与各组的 gtab
//
// 【子测例】
//   A 只按 pad0 → 应出现 note-on 48 并被分配
//   B 松开 pad0、同时按 pad1 → 应出现 note-off 48 + note-on 49
//     **并检查 note 49 是否真的被分配**（这是 `tb_padseq` 里失败的环节）
//   C 对照：松开 pad0、等一段、再按 pad1（不重叠）⇒ 应正常分配 49
//
// 【判据】把 B 与 C 的"note49 是否分配"对比：
//   B 失败 + C 通过 ⇒ 确证"重叠切换"导致丢失，且问题在 pad 通路的事件产生侧。
//=============================================================================
`timescale 1ns/1ps

module tb_padfast;

    localparam integer NCH = 16;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    wire [NCH-1:0] pad_bus;
    reg            uart_rx = 1'b1;
    wire           uart_tx;
    reg            ev_valid = 1'b0, ev_on = 1'b0;
    reg [6:0]      ev_note = 7'd0;
    reg [3:0]      ev_vel  = 4'd12;

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
    integer i, k;
    integer fails;

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
    // 探针
    //-------------------------------------------------------------------------
    integer n_on, n_off, ack_cnt;
    integer cyc;                 // 全局拍计数（代替原本的"样本号"）
    integer ev_log_note [0:31];
    integer ev_log_on   [0:31];
    integer ev_log_cyc  [0:31];
    integer ev_log_n;

    //   ★ 本轮新增：源侧探针 —— 证明"第二个事件被挂起位挡掉"
    //     这是根因所在：`tdm_top.v:817`
    //         if (pp_ev_valid && !pp_pend) begin ... pp_pend <= 1'b1; end
    //     单槽挂起寄存器 ⇒ pp_pend=1 期间到来的事件被**直接忽略**。
    integer pend_set_cnt;        // pp_pend 被置 1 的次数
    integer pp_ev_cnt;           // pad_pitch 侧 valid 的拍数（新事件产生次数）
    integer drop_cnt;            // **被挂起位挡掉的次数** = valid 且 pp_pend 已为 1
    integer pend_prev;
    always @(posedge clk) begin
        if (rst_n) begin
            if (u_top.pp_pend && !pend_prev) pend_set_cnt = pend_set_cnt + 1;
            pend_prev = u_top.pp_pend;
            if (u_top.pp_ev_valid) begin
                pp_ev_cnt = pp_ev_cnt + 1;
                if (u_top.pp_pend) drop_cnt = drop_cnt + 1;
            end
        end
    end

    always @(posedge clk) begin
        cyc = cyc + 1;
        if (rst_n) begin
            if (u_top.nm_ev_ack) ack_cnt = ack_cnt + 1;
            if (u_top.pp_on_p || u_top.pp_off_p) begin
                if (ev_log_n < 32) begin
                    ev_log_note[ev_log_n] = u_top.pp_ev_note;
                    ev_log_on  [ev_log_n] = u_top.pp_on_p;
                    ev_log_cyc [ev_log_n] = cyc;
                    ev_log_n = ev_log_n + 1;
                end
                if (u_top.pp_on_p)  n_on  = n_on  + 1;
                if (u_top.pp_off_p) n_off = n_off + 1;
            end
        end
    end

    integer gact_cnt;
    task scan;
        begin
            gact_cnt = 0;
            for (k = 0; k < 32; k = k + 1)
                if (u_top.u_nm.gact[k]) gact_cnt = gact_cnt + 1;
        end
    endtask

    function integer find_note;
        input integer want;
        integer kk;
        begin
            find_note = -1;
            for (kk = 0; kk < 32; kk = kk + 1)
                if (u_top.u_nm.gact[kk] && (u_top.u_nm.gtab[kk] == want[6:0]))
                    find_note = kk;
        end
    endfunction

    task check;
        input [255:0] name;
        input integer got;
        input integer exp;
        begin
            if (got === exp) $display("  PASS  %0s (%0d)", name, got);
            else begin
                $display("  FAIL  %0s got %0d exp %0d", name, got, exp);
                fails = fails + 1;
            end
        end
    endtask

    task dump_groups;
        begin
            $write("      [组状态] 拍=%0d 在响组:", cyc);
            for (k = 0; k < 32; k = k + 1)
                if (u_top.u_nm.gact[k]) $write(" g%0d(note=%0d)", k, u_top.u_nm.gtab[k]);
            $write("\n");
        end
    endtask

    task adv;
        input integer n;
        integer q;
        begin
            for (q = 0; q < n; q = q + 1) @(posedge clk);
        end
    endtask

    integer before_note49, before_ack;
    integer i0, i1;

    initial begin
        $display("==============================================================");
        $display(" pad 通路『切换丢事件』定位（不录音，秒级）");
        $display("==============================================================");

        fails = 0; cyc = 0; n_on = 0; n_off = 0; ack_cnt = 0; ev_log_n = 0;
        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        adv(40000);                       // 等自举 + pad_scan 基线稳定

        //-------------------------------------------------------------- A
        $display(" A 只按 pad0（期望 note-on 48 且被分配）");
        i0 = ev_log_n;
        disch_time[0] = 95;
        adv(20000);
        scan;
        $display("      事件数=%0d 在响组数=%0d note48 组=%0d", ev_log_n - i0, gact_cnt, find_note(48));
        check("A-note48-allocated", (find_note(48) >= 0) ? 1 : 0, 1);

        //-------------------------------------------------------------- B
        $display(" B 松开 pad0、**同一拍**按 pad1（期望 off48 + on49，且 49 被分配）");
        i1 = ev_log_n; before_ack = ack_cnt;
        pend_set_cnt = 0; pp_ev_cnt = 0; drop_cnt = 0;
        disch_time[0] = 30;
        disch_time[1] = 95;
        adv(20000);
        scan;
        $display("      事件数=%0d  ack 增量=%0d  在响组数=%0d  note49 组=%0d",
                 ev_log_n - i1, ack_cnt - before_ack, gact_cnt, find_note(49));
        $display("      [源侧] pad_ev_valid 拍数=%0d  挂起位置 1 次数=%0d  **被挂起位挡掉=%0d**",
                 pp_ev_cnt, pend_set_cnt, drop_cnt);
        dump_groups;
        before_note49 = find_note(49);

        //   打印 B 段事件明细
        for (k = i1; k < ev_log_n && k < i1 + 8; k = k + 1)
            $display("        [事件] 拍=%0d %s note=%0d",
                     ev_log_cyc[k], ev_log_on[k] ? "ON " : "OFF", ev_log_note[k]);

        //   ★ 这里才是本判据的**核心断言**（先前版本漏了，只打印不断言 —— 
        //     于是出现了"FAIL 的测量结果却打印 RESULT=PASS"的自相矛盾输出）。
        //   B 段：事件产生了 2 条，就必须被 ack 2 次，且 note49 必须被分配。
        check("B-two-events-produced", ev_log_n - i1, 2);
        check("B-both-events-acked",   ack_cnt - before_ack, 2);
        check("B-note49-allocated",    (before_note49 >= 0) ? 1 : 0, 1);
        //   ★ 根因断言：源侧确实产生了 2 次 valid，但**恰有 1 次被挂起位挡掉**。
        //     这证明丢失点在 `tdm_top.v:817` 的单槽挂起判断
        //         if (pp_ev_valid && !pp_pend)
        //     而不是队列或 note_map。
        check("B-src-produced-2-valid", pp_ev_cnt, 2);
        check("B-dropped-by-pending-slot", drop_cnt, 1);

        //-------------------------------------------------------------- C
        $display(" C 对照：先把 pad1 松开，静置后**单独**按 pad1");
        disch_time[1] = 30;
        adv(40000);
        scan;
        $display("      静置后在响组数=%0d", gact_cnt);
        i0 = ev_log_n; before_ack = ack_cnt;
        disch_time[1] = 95;
        adv(20000);
        scan;
        $display("      事件数=%0d  ack 增量=%0d  在响组数=%0d  note49 组=%0d",
                 ev_log_n - i0, ack_cnt - before_ack, gact_cnt, find_note(49));
        check("C-note49-alone-allocated", (find_note(49) >= 0) ? 1 : 0, 1);

        $display("==============================================================");
        $display(" ★ 判读：");
        $display("   B 段事件日志中若出现 OFF48 与 ON49 两条 ⇒ 事件**产生了**；");
        $display("   再看 note49 组是否为 -1：");
        $display("     · 事件产生但未分配 ⇒ 丢失在 pad 通路 → note_map 之间");
        $display("     · 事件压根没产生   ⇒ 丢失在 pad_scan/pad_pitch 的扫查仲裁里");
        $display("   C 段通过而 B 段失败 ⇒ 确证是『重叠切换』触发。");
        $display("   本判据**不录音频**，因此秒级可反复迭代（对比 tb_padseq 的 446 秒）。");
        $display("==============================================================");
        if (fails == 0) $display("RESULT padfast=PASS");
        else            $display("RESULT padfast=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #400_000_000;
        $display("RESULT padfast=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
