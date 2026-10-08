// RC pad end-to-end acceptance: A single on, B adjacent off/on,
// C separated control, D three adjacent events. Check production, ordered
// note_map acknowledgements, allocation and zero source overflow.
// Original fe326ad fails B; do not infer FIFO correctness from that old probe.
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
    integer ack_note[0:63], ack_on[0:63];
    integer cyc;                 // 全局拍计数（代替原本的"样本号"）
    integer ev_log_note [0:31];
    integer ev_log_on   [0:31];
    integer ev_log_cyc  [0:31];
    integer ev_log_n;

    // Observe actual rejected source pulses; no assertions tied to old pending registers.
    integer pp_ev_cnt=0, drop_cnt=0;
    always @(posedge clk) if (rst_n && u_top.pp_ev_valid) begin
        pp_ev_cnt=pp_ev_cnt+1;
        if (!u_top.padq_in_ready) drop_cnt=drop_cnt+1;
    end

    always @(posedge clk) begin
        cyc = cyc + 1;
        if (rst_n) begin
            if (u_top.nm_ev_ack) begin
                if (ack_cnt < 64) begin
                    ack_note[ack_cnt]=u_top.ev_note_r;
                    ack_on[ack_cnt]=u_top.ev_on_r;
                end
                ack_cnt=ack_cnt+1;
            end
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
        pp_ev_cnt = 0; drop_cnt = 0;
        disch_time[0] = 30;
        disch_time[1] = 95;
        adv(20000);
        scan;
        $display("      事件数=%0d  ack 增量=%0d  在响组数=%0d  note49 组=%0d",
                 ev_log_n - i1, ack_cnt - before_ack, gact_cnt, find_note(49));
        $display("      [source] produced=%0d rejected=%0d", pp_ev_cnt, drop_cnt);
        dump_groups;
        before_note49 = find_note(49);
        check("B-order-off48", ack_note[before_ack],48);
        check("B-order-off", ack_on[before_ack],0);
        check("B-order-on49", ack_note[before_ack+1],49);
        check("B-order-on", ack_on[before_ack+1],1);

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
        check("B-src-produced-2-valid", pp_ev_cnt, 2);
        check("B-source-queue-drops", drop_cnt, 0);

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

        // D: three real pad events in consecutive scan slots: off49/on50/on51.
        $display(" D three adjacent events off49/on50/on51");
        before_ack=ack_cnt; i0=ev_log_n;
        disch_time[1]=30; disch_time[2]=95; disch_time[3]=95;
        adv(20000);
        check("D-three-produced",ev_log_n-i0,3);
        check("D-three-acked",ack_cnt-before_ack,3);
        check("D-off49-note",ack_note[before_ack],49);
        check("D-off49-on",ack_on[before_ack],0);
        check("D-on50-note",ack_note[before_ack+1],50);
        check("D-on50-on",ack_on[before_ack+1],1);
        check("D-on51-note",ack_note[before_ack+2],51);
        check("D-on51-on",ack_on[before_ack+2],1);
        check("D-note50-allocated",find_note(50)>=0,1);
        check("D-note51-allocated",find_note(51)>=0,1);
        check("D-no-pad-overflow",u_top.padq_ovf,0);

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
