//=============================================================================
// tb_evseq.v —— 【快判据】紧邻事件序列：note-off 与 note-on 相邻时是否丢失
//
// 【背景（2026-10-07）】
//   `tb_padseq.v` 复现出：松开 pad0 的同时按 pad1 时，**pad1 的 note-on 没有落地**
//   （组状态始终为空，听到的只是 note0 的释放尾音）。
//   根因候选已缩小到事件的**接收确认**：
//     `note_map.v:350`  `assign ev_ack = (st == ST_IDLE) && ev_valid;`
//     而 `note_map` 处理一个事件要经过 ST_ALLOC → ST_LOAD（**每拍一个时隙，16 拍**），
//     在这期间 `st != ST_IDLE` ⇒ **不 ack**。
//   ⇒ 若上游只在单拍上给 valid（脉冲），**这一拍不在 ST_IDLE 就永远丢了**。
//
//   本判据**绕开 pad 通路**，直接在 `ev_valid/ev_on/ev_note` 上打事件，
//   把条件压到最小、跑得最快（秒级），用来分离"是哪一级丢的"。
//
// 【三个子测例】
//   T1 单事件：note 48 on → 必须分配到组（基线，应通过）
//   T2 紧邻：note 48 on，间隔 1 拍 note 48 off，再间隔 1 拍 note 49 on
//           ⇒ 检查 note 49 是否被分配（**预期暴露丢失**）
//   T3 宽松：同样的三个事件，但每个之间留足间隔（各 200 拍）
//           ⇒ 若 T3 通过而 T2 失败，则**确证是"紧邻"导致的丢失**
//
// 【判据】每个子测例后统计"在响组数"以及是否有组的 gtab == 期望音符号。
//=============================================================================
`timescale 1ns/1ps

module tb_evseq;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    wire [15:0] pad_bus = 16'h0000;
    reg         uart_rx = 1'b1;
    wire        uart_tx;
    reg         ev_valid = 1'b0, ev_on = 1'b0;
    reg [6:0]   ev_note = 7'd0;
    reg [3:0]   ev_vel  = 4'd12;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    integer fails;
    integer k, gact_cnt, has_note;
    integer ack_cnt;          // 记下 note_map 一共 ack 了几次

    always @(posedge clk)
        if (rst_n && u_top.nm_ev_ack) ack_cnt = ack_cnt + 1;

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
                $display("  FAIL  %0s got %0d expected %0d", name, got, exp);
                fails = fails + 1;
            end
        end
    endtask

    //   打一个单拍事件
    task pulse_ev;
        input       on;
        input [6:0] n;
        begin
            ev_on = on; ev_note = n; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
        end
    endtask

    task wait_n;
        input integer n;
        integer i;
        begin
            for (i = 0; i < n; i = i + 1) @(posedge clk);
        end
    endtask

    integer a0, a1, a2;

    initial begin
        $display("==============================================================");
        $display(" 紧邻事件序列：note-off 与 note-on 相邻时是否丢失");
        $display("==============================================================");

        fails = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (3000) @(posedge clk);

        //------------------------------------------------------------ T1 基线
        $display(" T1 单事件基线：note 48 on（间隔充足）");
        a0 = ack_cnt;
        pulse_ev(1'b1, 7'd48);
        wait_n(2000);
        scan; has_note = find_note(48);
        $display("      ack 次数增量=%0d  在响组数=%0d  note48 所在组=%0d",
                 ack_cnt - a0, gact_cnt, has_note);
        check("T1-note48-allocated", (has_note >= 0) ? 1 : 0, 1);

        //   清干净
        pulse_ev(1'b0, 7'd48);
        wait_n(4000);
        scan;
        $display("      清理后在响组数=%0d（应 0）", gact_cnt);
        check("T1-clean", gact_cnt, 0);

        //------------------------------------------------------------ T2 紧邻
        $display(" T2 紧邻：48 on → 1 拍后 48 off → 1 拍后 49 on");
        a1 = ack_cnt;
        pulse_ev(1'b1, 7'd48);
        @(posedge clk);
        pulse_ev(1'b0, 7'd48);
        @(posedge clk);
        pulse_ev(1'b1, 7'd49);
        wait_n(3000);
        scan; has_note = find_note(49);
        $display("      ack 次数增量=%0d（3 个事件应 ack 3 次）  在响组数=%0d  note49 所在组=%0d",
                 ack_cnt - a1, gact_cnt, has_note);
        $display("      ⇒ 若 ack 次数 < 3，说明有事件被 ack 掉却没执行，或压根没被接收");
        check("T2-note49-allocated", (has_note >= 0) ? 1 : 0, 1);

        //   清干净
        pulse_ev(1'b0, 7'd49);
        wait_n(4000);
        scan;
        check("T2-clean", gact_cnt, 0);

        //------------------------------------------------------------ T3 宽松
        $display(" T3 宽松：同样三个事件，但每个之间留 300 拍");
        a2 = ack_cnt;
        pulse_ev(1'b1, 7'd48);
        wait_n(300);
        pulse_ev(1'b0, 7'd48);
        wait_n(300);
        pulse_ev(1'b1, 7'd49);
        wait_n(3000);
        scan; has_note = find_note(49);
        $display("      ack 次数增量=%0d  在响组数=%0d  note49 所在组=%0d",
                 ack_cnt - a2, gact_cnt, has_note);
        check("T3-note49-allocated", (has_note >= 0) ? 1 : 0, 1);

        $display("==============================================================");
        $display(" ★ 判读：");
        $display("   T1 通过 + T3 通过 + T2 失败 ⇒ 确证是『紧邻事件』导致的丢失");
        $display("   T2 的 ack 次数是定位关键：");
        $display("     · ack=3 且 note49 未分配 ⇒ 事件被 ack 了却没执行（ack 时序问题）");
        $display("     · ack<3                ⇒ 事件压根没被接收（队列/valid 脉冲问题）");
        $display("==============================================================");
        if (fails == 0) $display("RESULT evseq=PASS");
        else            $display("RESULT evseq=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #200_000_000;
        $display("RESULT evseq=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
