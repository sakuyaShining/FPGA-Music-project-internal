//=============================================================================
// tb_pad.v —— pad 扫描判据（21 号 §5 的 PS1 / PS2 / PS4 + PS3 机制检查）
//
// 【电极模型】电极 = 电容。RTL 充电期（dbg_phase==0）由 RTL 推高；
//   其余时间由本模型驱动：先维持 1 共 disch_time[i] 拍（= 放电时间），然后变 0。
//   手指靠近 ⇒ 电容变大 ⇒ disch_time 变大 ⇒ RTL 数到的计数变大
//   用 dbg_phase 判"谁在驱动"，避免 inout 上的驱动争用
//
// PS1 单调性：disch_time 20/40/60 ⇒ 裸计数严格递增
// PS2 滞回：计数在阈值附近抖动 ⇒ 输出翻转 ≤ 1 次
// PS4 五声音阶：8 个音高 pad 逐一触发 ⇒ 发出的 note 与期望 MIDI 逐一相等
// PS3 机制：标定后给所有 pad 叠加慢漂移 ⇒ 无假触发（注：完整"1 秒"未跑，见报告）
//=============================================================================

`timescale 1ns/1ps

module tb_pad;

    localparam integer NCH = 16;
    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;              // 27 MHz

    wire [NCH-1:0] pad_bus;
    wire [NCH-1:0] state;
    wire [6:0]     ev_note;
    wire           ev_on, ev_valid;
    wire [11:0]    dbg_raw0, dbg_base0;
    wire [1:0]     dbg_phase;

    integer disch_time [0:NCH-1];            // 每路放电时间（拍）—— 手指模型
    integer drift;                           // 全局慢漂移

    pad_scan #(.NCH(NCH)) u_pad (
        .clk(clk), .rst_n(rst_n),
        .pad(pad_bus),
        .note_busy(1'b0),
        .oct_up(1'b0),
        .state(state),
        .ev_note(ev_note), .ev_on(ev_on), .ev_valid(ev_valid),
        .dbg_raw0(dbg_raw0), .dbg_base0(dbg_base0), .dbg_phase(dbg_phase)
    );

    //-------------------------------------------------------------------------
    // 电极 RC 模型（16 路）
    //-------------------------------------------------------------------------
    genvar gi;
    generate
        for (gi = 0; gi < NCH; gi = gi + 1) begin : gpad
            reg        charged;
            integer    dcnt;
            initial begin charged = 1'b0; dcnt = 0; end
            always @(posedge clk) begin
                if (dbg_phase == 2'd0) begin          // 充电期：RTL 推高
                    charged <= 1'b1;
                    dcnt    <= 0;
                end
                else if (charged && dcnt < disch_time[gi] + drift) begin
                    dcnt <= dcnt + 1;                 // 还在放电 ⇒ 维持 1
                end
                else begin
                    charged <= 1'b0;                  // 放完 ⇒ 变 0
                end
            end
            assign pad_bus[gi] = (dbg_phase == 2'd0) ? 1'bz
                               : (charged ? 1'b1 : 1'b0);
        end
    endgenerate

    integer i, k, r;
    integer raw_a, raw_b, raw_c;
    integer flip_cnt, prev_state0;
    integer got_note [0:15];
    integer got_on   [0:15];
    integer nev;
    integer fails;
    integer expct;
    integer cap_store;

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

    // 监视事件脉冲
    always @(posedge clk) begin
        if (ev_valid && nev < 16) begin
            got_note[nev] = ev_note;
            got_on[nev]   = ev_on;
            nev = nev + 1;
        end
    end

    initial begin
        fails = 0; nev = 0; drift = 0; flip_cnt = 0; prev_state0 = 0;
        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;
        rst_n = 1'b0;
        repeat (100) @(posedge clk);
        rst_n = 1'b1;

        $display("==============================================================");
        $display(" pad 扫描判据（PS1 单调 / PS2 滞回 / PS4 五声音阶 / PS3 机制）");
        $display("==============================================================");

        //---------------- PS1：计数单调随电容增大 ----------------
        wait_rounds(40);                          // 标定 32 轮 + 余量
        disch_time[0] = 20; wait_rounds(3); raw_a = dbg_raw0;
        disch_time[0] = 40; wait_rounds(3); raw_b = dbg_raw0;
        disch_time[0] = 60; wait_rounds(3); raw_c = dbg_raw0;
        $display("  [PS1] 放电 20/40/60 拍 ⇒ 裸计数 %0d / %0d / %0d，基线 %0d",
                 raw_a, raw_b, raw_c, dbg_base0);
        if (raw_a < raw_b && raw_b < raw_c) $display("        ⇒ 单调递增 ✓");
        else begin $display("        ⇒ ✗ 非单调"); fails = fails + 1; end

        //---------------- PS2：阈值附近抖动 ⇒ 翻转 ≤1 次 ----------------
        // 先让 pad0 稳定触摸（计数远高于阈值），再把计数在阈值附近来回抖
        disch_time[0] = 80; wait_rounds(8);        // 稳定触摸
        prev_state0 = state[0]; flip_cnt = 0;
        for (k = 0; k < 40; k = k + 1) begin
            disch_time[0] = (k % 2 == 0) ? 46 : 44; // 阈值附近抖动
            wait_rounds(1);
            if (state[0] != prev_state0) flip_cnt = flip_cnt + 1;
            prev_state0 = state[0];
        end
        $display("  [PS2] 阈值附近抖动 40 轮 ⇒ 输出翻转 %0d 次（期望 ≤1）", flip_cnt);
        if (flip_cnt <= 1) $display("        ⇒ 滞回/去抖生效 ✓");
        else begin $display("        ⇒ ✗ 振荡"); fails = fails + 1; end
        disch_time[0] = 30; wait_rounds(10);       // 松开、回基线

        //---------------- PS4：五声音阶逐一触发 ----------------
        // 期望 C4 D4 E4 G4 A4 C5 D5 E5 = 60 62 64 67 69 72 74 76
        nev = 0;
        for (i = 0; i < 8; i = i + 1) begin
            disch_time[i] = 90;                    // 按下第 i 键
            wait_rounds(6);
            disch_time[i] = 30;                    // 松开
            wait_rounds(6);
        end
        $display("  [PS4] 发出事件 %0d 个（期望 16 = 8 按 + 8 放）", nev);
        for (i = 0; i < 8; i = i + 1) begin
            case (i)
                0: expct = 60; 1: expct = 62; 2: expct = 64; 3: expct = 67;
                4: expct = 69; 5: expct = 72; 6: expct = 74; default: expct = 76;
            endcase
            if (i * 2 + 1 < nev) begin
                $display("        pad%0d: 按下 note=%0d（期望 %0d）on=%0d / 松开 note=%0d on=%0d",
                         i, got_note[i*2], expct, got_on[i*2],
                            got_note[i*2+1], got_on[i*2+1]);
                if (got_note[i*2] != expct || got_on[i*2] != 1 ||
                    got_note[i*2+1] != expct || got_on[i*2+1] != 0) begin
                    $display("        ✗ pad%0d 不符", i); fails = fails + 1;
                end
            end
            else begin $display("        ✗ pad%0d 事件缺失", i); fails = fails + 1; end
        end
        if (fails == 0) $display("        ⇒ 五声音阶逐键正确 ✓");

        //---------------- PS3：漂移与基线跟踪 ----------------
        // 跟踪器能力（实测）：1 计数 / 64 轮 ≈ 4400 计数/秒
        //   规格书要求应对 0.5%/s（基线 ~31 ⇒ 0.155 计数/秒）⇒ 余量约 28000 倍
        // PS3a：漂移速率取能力的 **1/4**（1 计数 / 256 轮）⇒ 必须不假触发
        //   完整的"1 秒 @ 规格书速率"没有跑（27M 拍太慢）；机制由此验证，
        //     速率由 PS3b 定量给出
        flip_cnt = 0; drift = 0;
        for (k = 0; k < 1024; k = k + 1) begin
            drift = k / 256;                       // 1 计数 / 256 轮（能力的 1/4）
            wait_rounds(1);
            if (state != {NCH{1'b0}}) flip_cnt = flip_cnt + 1;
        end
        $display("  [PS3a] 漂移 1024 轮（+%0d 计数，能力的 1/4）⇒ 非零状态轮数 = %0d（期望 0）",
                 drift, flip_cnt);
        if (flip_cnt == 0) $display("        ⇒ 基线跟踪住了漂移 ✓");
        else begin $display("        ⇒ ✗ 有假触发"); fails = fails + 1; end

        // PS3b 跟踪速率：给一个【带内】+2 计数偏移（不触发），量吸收所需轮数
        drift = 0;
        wait_rounds(300);                          // 让基线回到干净值
        cap_store = dbg_base0;
        drift = 2;                                 // 滞回带内 ⇒ 不触发、且空闲 ⇒ 可跟踪
        for (k = 0; k < 400; k = k + 1) begin
            wait_rounds(1);
            if (dbg_base0 >= cap_store + 2) begin
                $display("  [PS3b] 基线吸收 +2 计数用了 %0d 轮（基线 %0d→%0d）",
                         k + 1, cap_store, dbg_base0);
                k = 400;                           // 提前结束
            end
        end
        drift = 0;
        if (dbg_base0 < cap_store + 2) begin
            $display("        ⇒ ✗ 400 轮内没吸收 +2 计数（跟踪太慢？）"); fails = fails + 1;
        end
        else $display("        ⇒ 跟踪速率合理（规格书 0.5%%/s = 0.155 计数/秒，本实现快数千倍）✓");

        $display("");
        if (fails == 0) $display("RESULT pad=PASS ps1=1 ps2=1 ps4=1 ps3=1");
        else            $display("RESULT pad=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #400_000_000;
        $display("RESULT pad=TIMEOUT");
        $finish;
    end

endmodule
