//=============================================================================
// tb_evloss.v —— 事件丢失判据：pad_scan 的待发位图 + note_map 忙模型
//
// 【为什么单独做这一条】
//   tdm_top.v:425 自述"note_map 侧有 busy 门控，冲突时后到者被忽略"，
//   而 pad_scan 宣称自己用 8 位待发位图 + note_busy 反压来避免丢事件
//   （pad_scan.v:243/286/294）。两条说法必须用【实测】对齐 ——
//   本会话已经三次因为"读代码/看注释就下结论"而误判。
//
// 【实测结论（2026-10-06）：pad 路径不丢事件、不挂音】
//   8 键同时按下、之后同时松开 ⇒ 实测 16 条事件（8 on + 8 off），逐一对应。
//   ⇒ pad_scan 的待发位图 + note_busy 反压这一套是**有效**的；
//     "8 键同时按放不丢事件、不挂音"这一条由本测试台守住。
//
//   ★ 需要继续盯的是【汇合点】而不是 pad 路径：tdm_top 的优先级 mux
//     （UART > 定序器 > pads > 排针）在同一拍多源并起时会丢掉低优先级那一个；
//     其中 UART(0x61) 与定序器都**不受 note_busy 反压**，它们的事件仍是单拍脉冲。
//     那是比"pad 丢事件"窄得多、但真实存在的缺口，尚未有判据覆盖。
//
// 【怎么测】
//   DUT = pad_scan（真实模块），note_busy 由【忙模型】驱动：
//     忠实模仿 note_map 的时序 —— 收到有效事件后拉高 busy 约 20 拍再释放。
//   电极用 tb_pad.v 同款 RC 模型，且 disch_time 必须落在它标定的区间
//   （30 = 松开 / 90 = 按下）。**离开标定区间会造出假故障**：
//     第一版我写 0 / 4000，结果 state 永远回不到 0、一个 note-off 都没有 ——
//     看着像"挂音缺陷"，其实是我模型的问题。这类假故障必须先自己排除。
//
// 【判据】
//   E1 事件总数 == 16（8 次按下 + 8 次松开）——少一个就是丢事件
//   E2 8 个键都收到 note-on
//   E3 8 个 note-off 都发出（不挂音）
//=============================================================================
`timescale 1ns/1ps

module tb_evloss;

    localparam integer NCH  = 16;       // 与顶层一致
    localparam integer NKEY = 8;        // 同时按下的键数
    localparam integer BUSY_CYC = 20;   // 忙模型占用拍数（note_map 一次装载约 20 拍）

    reg clk, rst_n;
    initial clk = 1'b0;
    always #18.5185 clk = ~clk;         // ≈27 MHz

    wire [NCH-1:0] pad_bus;
    wire [NCH-1:0] state;
    wire [6:0]     ev_note;
    wire           ev_on, ev_valid;
    wire [11:0]    dbg_raw_sel, dbg_base_sel;

    //  ------- 电极模型（照抄 tb_pad.v 的做法：RC 放电，触摸 = 放电更慢） -------
    //   RTL 在 dbg_phase==0 期间推高电极；放电期由本模型决定它多快掉下来。
    //   disch_time[ch] 越大 = 手指压得越实 = 计数越大。
    integer disch_time [0:NCH-1];
    wire [1:0] dbg_phase;

    genvar gi;
    generate
        for (gi = 0; gi < NCH; gi = gi + 1) begin : gpad
            reg     charged;
            integer dcnt;
            initial begin charged = 1'b0; dcnt = 0; end
            always @(posedge clk) begin
                if (dbg_phase == 2'd0) begin          // 充电期：RTL 推高
                    charged <= 1'b1;
                    dcnt    <= 0;
                end
                else if (charged && dcnt < disch_time[gi]) begin
                    dcnt <= dcnt + 1;                 // 还在放电 ⇒ 维持 1
                end
                else begin
                    charged <= 1'b0;                  // 放完 ⇒ 变 0
                end
            end
            //   phase==0 让 RTL 驱动；其余时候本模型驱动（模拟电容保持/放电）
            assign pad_bus[gi] = (dbg_phase == 2'd0) ? 1'bz
                               : (charged ? 1'b1 : 1'b0);
        end
    endgenerate

    //  ------- 忙模型：模仿 note_map 一次装载约 20 拍 -------
    reg        busy;
    integer    busy_cnt;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            busy <= 1'b0; busy_cnt <= 0;
        end
        else if (busy) begin
            if (busy_cnt == 0) busy <= 1'b0;
            else               busy_cnt <= busy_cnt - 1;
        end
        else if (ev_valid) begin
            busy     <= 1'b1;
            busy_cnt <= BUSY_CYC;
        end
    end

    pad_scan #(.NCH(NCH)) u_pad (
        .clk(clk), .rst_n(rst_n),
        .pad(pad_bus),
        .note_busy(busy),
        .oct_up(1'b0),
        .state(state),
        .ev_note(ev_note), .ev_on(ev_on), .ev_valid(ev_valid),
        .dbg_raw0(), .dbg_base0(), .dbg_phase(dbg_phase),
        .dbg_sel(4'd0), .dbg_raw_sel(dbg_raw_sel), .dbg_base_sel(dbg_base_sel)
    );

    //  ------- 记录事件 -------
    localparam MAXEV = 64;
    integer  ev_n  [0:MAXEV-1];
    integer  ev_onr[0:MAXEV-1];
    integer  nev;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) nev <= 0;
        else if (ev_valid && nev < MAXEV) begin
            ev_n[nev]   <= ev_note;
            ev_onr[nev] <= ev_on;
            nev         <= nev + 1;
        end
    end

    //  ------- 主流程 -------
    //   注意：pad_scan 用的是【五声音阶】映射（tb_pad.v PS4 已验证），
    //   下排 8 个电极 → note 60/62/64/67/69/72/74/76，不是 48..55。
    //   disch_time 的可用区间也照抄 tb_pad.v：**30 = 松开、90 = 按下**。
    //   （第一版我写成 0 / 4000，远离标定区间 ⇒ state 永远回不到 0、
    //     于是"一个 note-off 都没有"——那是我模型的问题，不是 RTL 的。
    //     这类"模型不在标定区间"造成的假故障必须自己先排除，再谈 RTL。）
    integer i, k, fails, on_cnt, off_cnt;
    integer seen_on [0:7];
    integer exp_note[0:7];

    task wait_rounds(input integer n);
        integer j;
        begin
            for (j = 0; j < n; j = j + 1) begin
                @(posedge clk);
                while (dbg_phase != 2'd2) @(posedge clk);   // 等到锁存相
                @(posedge clk);
            end
        end
    endtask

    initial begin
        $display("==============================================================");
        $display(" 事件丢失判据：%0d 键同时按 / 同时放（带 note_map 忙模型）", NKEY);
        $display("==============================================================");

        rst_n = 1'b0;
        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;  // 30 = 松开（tb_pad.v 标定值）
        exp_note[0]=60; exp_note[1]=62; exp_note[2]=64; exp_note[3]=67;
        exp_note[4]=69; exp_note[5]=72; exp_note[6]=74; exp_note[7]=76;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        wait_rounds(20);                                     // 等标定完成

        //---- 8 个键【同时】按下（90 = 按下；8 个事件需要 8 个扫描轮才发完）
        for (i = 0; i < NKEY; i = i + 1) disch_time[i] = 90;
        wait_rounds(40);

        //---- 8 个键【同时】松开
        for (i = 0; i < NKEY; i = i + 1) disch_time[i] = 30;
        wait_rounds(40);
        repeat (2000) @(posedge clk);

        //---- 判定
        fails = 0;
        on_cnt = 0; off_cnt = 0;
        for (i = 0; i < 8; i = i + 1) seen_on[i] = 0;

        $display(" 实测事件序列（共 %0d 条，期望 %0d 条）：", nev, 2 * NKEY);
        for (i = 0; i < nev; i = i + 1) begin
            $display("   #%0d note=%0d on=%0d", i, ev_n[i], ev_onr[i]);
            if (ev_onr[i]) begin
                on_cnt = on_cnt + 1;
                for (k = 0; k < NKEY; k = k + 1)
                    if (ev_n[i] == exp_note[k]) seen_on[k] = 1;
            end
            else off_cnt = off_cnt + 1;
        end

        // E1 总数
        if (nev != 2 * NKEY) begin
            $display("  FAIL  E1 事件总数 %0d ≠ 期望 %0d ⇒ 有事件丢失", nev, 2 * NKEY);
            fails = fails + 1;
        end
        else $display("  PASS  E1 事件总数 = %0d（无丢失）", nev);

        // E2 每个键都有 on
        for (k = 0; k < NKEY; k = k + 1) begin
            if (!seen_on[k]) begin
                $display("  FAIL  E2 键 %0d（note %0d）从未收到 note-on", k, exp_note[k]);
                fails = fails + 1;
            end
        end
        if (on_cnt != NKEY) begin
            $display("  FAIL  E2 note-on 数 %0d ≠ %0d", on_cnt, NKEY);
            fails = fails + 1;
        end
        else $display("  PASS  E2 %0d 个键都收到了 note-on", NKEY);

        // E3 松手数
        if (off_cnt != NKEY) begin
            $display("  FAIL  E3 note-off 数 %0d ≠ %0d ⇒ 会挂音", off_cnt, NKEY);
            fails = fails + 1;
        end
        else $display("  PASS  E3 %0d 个 note-off 都发出（不挂音）", NKEY);

        $display("==============================================================");
        if (fails == 0) $display("RESULT evloss=PASS nev=%0d", nev);
        else            $display("RESULT evloss=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #400_000_000;
        $display("RESULT evloss=TIMEOUT nev=%0d", nev);
        $finish;
    end

endmodule
