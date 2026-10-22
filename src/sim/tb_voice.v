//=============================================================================
// tb_voice.v —— 逐声部"力度/音色"是否需要独立存储？（阶段 3 判据）
//
// 【要回答的问题（把假设变成事实）】
//   阶段 3 计划里写着"保存每声部力度/音色/状态"。但读代码得到的印象是：
//   note_map 在**装载时**就把力度算进每个泛音的幅度里
//   （vel_shape → amp_shaped → amp_cal = amp_shaped*vel_cur>>8 → load_amp），
//   引擎把它逐槽写进 pa_mem ⇒ 力度已经**烘进每个泛音的幅度**，不需要运行时再查。
//
//   若这个印象成立，那么"逐声部保存力度"就不是缺口 —— 而是一条需要被
//   **判据固定住**的性质（否则将来有人"顺手优化"就可能破坏它）。
//
// 【判据】
//   V1 同一个音、不同力度 ⇒ 落进 pa_mem 的幅度**不同**（力度确实进了幅度）
//   V2 装载别的声部、别的力度之后，**已装载声部的幅度一个都不变**
//      （这是"烘进幅度"的直接证据：不需要逐声部保存力度）
//   V3 全局 `vel_vscale`(0x6E) 中途改变，**不影响已发声的声部**
//      （只对之后的装载生效 —— 与"装载时求值"一致）
//
// 【怎么读】层次引用引擎的待生效影子内存 `u_top.u_tdm.pa_mem[slot]`：
//   load_en 写的就是它，而它是"待生效"，观察它不会有采样竞争。
//   槽位 = 组号*P + 泛音号（P=16）。
//=============================================================================
`timescale 1ns/1ps

module tb_voice;

    localparam integer P = 16;                    // 每组泛音数
    localparam integer NSLOT = 512;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    wire [15:0] pad_bus = 16'h0000;
    reg         uart_rx = 1'b1;
    wire        uart_tx;
    reg         ev_valid = 1'b0, ev_on = 1'b0;
    reg [6:0]   ev_note = 7'd0;
    reg [3:0]   ev_vel  = 4'd0;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    integer fails;
    integer i, k;

    //   一组（16 个泛音）的幅度快照
    reg [15:0] snapA [0:P-1];
    reg [15:0] snapB [0:P-1];

    task snap;
        input integer grp;
        input integer which;      // 0 -> snapA, 1 -> snapB
        integer kk;
        begin
            for (kk = 0; kk < P; kk = kk + 1) begin
                if (which == 0) snapA[kk] = u_top.u_tdm.pa_mem[grp*P + kk];
                else            snapB[kk] = u_top.u_tdm.pa_mem[grp*P + kk];
            end
        end
    endtask

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

    task ev;
        input [6:0] n;
        input       on;
        input [3:0] v;
        begin
            ev_note = n; ev_on = on; ev_vel = v; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            repeat (120) @(posedge clk);        // 装载 16 个泛音（每组约 20 拍）+ 余量
        end
    endtask

    function integer grp_of;
        input [6:0] n;
        integer kk;
        begin
            grp_of = -1;
            for (kk = 0; kk < 32; kk = kk + 1)
                if (u_top.u_nm.gtab[kk] == n[6:0] && u_top.u_nm.gact[kk])
                    grp_of = kk;
        end
    endfunction

    integer g1, g2, g3;
    integer diff_12, diff_after;
    integer n_changed;
    integer commit_fr [0:P-1];
    integer n_committed, fr_min, fr_max;

    initial begin
        $display("==============================================================");
        $display(" 逐声部力度/音色是否需要独立存储？（阶段 3）");
        $display("==============================================================");

        fails = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (3000) @(posedge clk);

        //---- 声部1：note 48，满力度
        ev(7'd48, 1'b1, 4'd15);
        g1 = grp_of(7'd48);
        $display(" note48(vel=15) 落在组 %0d", g1);
        snap(g1, 0);

        //---- 声部2：note 55，小力度
        ev(7'd55, 1'b1, 4'd3);
        g2 = grp_of(7'd55);
        $display(" note55(vel=3)  落在组 %0d", g2);
        snap(g2, 1);

        //--------------------------------------------------------------- V1
        $display(" V1 不同力度 ⇒ 落进 pa_mem 的幅度不同");
        diff_12 = 0;
        for (k = 0; k < P; k = k + 1)
            if (snapA[k] != snapB[k]) diff_12 = diff_12 + 1;
        $display("      两组的 16 个泛音中有 %0d 个幅度不同", diff_12);
        if (diff_12 == 0) begin
            $display("  FAIL  V1 力度没有进入幅度 ⇒ 力度确实需要另行保存");
            fails = fails + 1;
        end
        else $display("  PASS  V1 力度已烘进每个泛音的幅度");

        //--------------------------------------------------------------- V2
        $display(" V2 装载第三个声部后，前两个声部的幅度必须一个都不变");
        ev(7'd62, 1'b1, 4'd10);
        g3 = grp_of(7'd62);
        $display(" note62(vel=10) 落在组 %0d", g3);
        //   重新读组1、组2，逐项与快照比对
        diff_after = 0;
        for (k = 0; k < P; k = k + 1) begin
            if (u_top.u_tdm.pa_mem[g1*P + k] !== snapA[k]) begin
                $display("  FAIL  V2 组%0d 泛音%0d 从 %0d 变成了 %0d",
                         g1, k, snapA[k], u_top.u_tdm.pa_mem[g1*P + k]);
                diff_after = diff_after + 1;
            end
            if (u_top.u_tdm.pa_mem[g2*P + k] !== snapB[k]) begin
                $display("  FAIL  V2 组%0d 泛音%0d 从 %0d 变成了 %0d",
                         g2, k, snapB[k], u_top.u_tdm.pa_mem[g2*P + k]);
                diff_after = diff_after + 1;
            end
        end
        check("V2-other-voice-must-not-change", diff_after, 0);

        //--------------------------------------------------------------- V3
        $display(" V3 中途改全局 vel_vscale(0x6E)，已发声声部的幅度不受影响");
        //   ★ R 是 reg_bank 的输出**线网**，不能当 l-value 赋值；
        //     要改寄存器得写 reg_bank 内部的存储 `mem`（本项目其它测试台同款做法）。
        u_top.u_reg.mem[8'h6E] = 8'h00;     // vscale = 0（关掉力度灵敏度）
        repeat (200) @(posedge clk);
        diff_after = 0;
        for (k = 0; k < P; k = k + 1) begin
            if (u_top.u_tdm.pa_mem[g1*P + k] !== snapA[k]) diff_after = diff_after + 1;
            if (u_top.u_tdm.pa_mem[g2*P + k] !== snapB[k]) diff_after = diff_after + 1;
        end
        check("V3-global-change-must-not-touch-sounding", diff_after, 0);

        //--------------------------------------------------------------- V4
        $display(" V4 整组提交：一个组的 16 个泛音是否【同一次生效】（不出现半新半旧）");
        //   背景（读 tdm_engine 得到的事实）：
        //     待生效区是**逐时隙**的：pv_mem/pa_mem 每槽一份，
        //     消费条件是 `consume = pv1 & (pp1 != ppr1)`（该槽被访问、且奇偶标签变了）
        //     ⇒ 装载会在**每个槽被下一次访问时**分别生效，**不是整组一次生效**。
        //   本项用仿真确认这一点，并把"半新半旧"的窗口量化出来。
        //
        //   做法：对每个样本帧采一次"该组 16 槽当前生效的幅度"快照（读 amp_mem），
        //   看它从【全旧】到【全新】之间，是否存在**既含旧值又含新值**的中间帧。
        begin : v4
            integer fr, s, mixed_frames, partial_frames;
            integer n_old, n_new;
            reg [15:0] cur [0:P-1];

            //   新音：note48 再次按下，但用**不同力度**（让 16 个泛音的新值都不同于旧值）
            //   先记录旧快照（V2 之前的 snapA 是 vel=15 时的；这里重新读一次）
            snap(g1, 0);
            for (s = 0; s < P; s = s + 1) cur[s] = snapA[s];

            //   判据口径（本轮重做）：**不再**用"与旧快照比较"，
            //   因为部分槽两次幅度本来就相同（vel_wtab 不缩放它们），
            //   无法区分「该槽未变化」与「该槽尚未提交」。
            //
            //   改为**直接测每个槽的提交时刻**：
            //     待生效区每槽有独立标志 pv_mem 与数据 pa_mem；
            //     消费条件 `consume = pv1 & (pp1 != ppr1)` 成立时
            //     `amp_mem[slot] <= pa_mem[slot]` 且 `pv_mem[slot] <= 0`。
            //     ⇒ 于是 `amp_mem[slot] == pa_mem[slot] && pv_mem[slot]==0`
            //       正是"该槽已提交"的**充分条件**（与"是否变化"无关）。
            //
            //   做法：先等到待生效区**全空**（所有 pv_mem=0）作为起点，
            //         再发事件触发重装，然后逐帧记录每个槽首次满足上述条件的帧号。
            //   判据：
            //     A 若 16 个槽的提交帧号**全相同** ⇒ 整组一次生效（原子）
            //     B 否则 ⇒ **确证**逐槽分别生效，并给出跨度（最大帧号 - 最小帧号）
            begin : wait_drain
                integer dw, allz;
                dw = 0;
                allz = 0;
                while (allz == 0 && dw < 200) begin
                    repeat (512) @(posedge clk);
                    allz = 1;
                    for (s = 0; s < P; s = s + 1)
                        if (u_top.u_tdm.pv_mem[g1*P + s] != 1'b0) allz = 0;
                    dw = dw + 1;
                end
                $display("      待生效区排空用 %0d 帧（allz=%0d）", dw, allz);
            end

            //   重新装载：用**与上次不同的力度**，让尽量多的槽真的换值
            ev_note = 7'd48; ev_on = 1'b1; ev_vel = 4'd1; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;

            //   记录每个槽的提交帧号（-1 = 观察窗口内未提交）
            for (s = 0; s < P; s = s + 1) commit_fr[s] = -1;
            n_committed = 0;
            for (fr = 0; fr < 60; fr = fr + 1) begin
                repeat (512) @(posedge clk);
                for (s = 0; s < P; s = s + 1) begin
                    if (commit_fr[s] < 0
                        && u_top.u_tdm.pv_mem[g1*P + s] == 1'b0
                        && u_top.u_tdm.amp_mem[g1*P + s] === u_top.u_tdm.pa_mem[g1*P + s]) begin
                        commit_fr[s] = fr;
                        n_committed = n_committed + 1;
                    end
                end
            end

            fr_min = 9999; fr_max = -1;
            for (s = 0; s < P; s = s + 1) begin
                if (commit_fr[s] >= 0) begin
                    if (commit_fr[s] < fr_min) fr_min = commit_fr[s];
                    if (commit_fr[s] > fr_max) fr_max = commit_fr[s];
                end
            end
            $display("      已提交 %0d/%0d 个槽；提交帧号 最小=%0d 最大=%0d 跨度=%0d",
                     n_committed, P, fr_min, fr_max,
                     (fr_max >= fr_min) ? (fr_max - fr_min) : -1);
            for (s = 0; s < P; s = s + 1)
                if (s < 8) $display("        槽%0d 提交帧=%0d", s, commit_fr[s]);

            if (n_committed == P && fr_max == fr_min)
                $display("  PASS  V4 整组在同一帧生效（原子提交）");
            else if (n_committed == P) begin
                $display("  NOTE  V4 **确证非原子**：16 个槽分散在 %0d 个帧内生效（跨度 %0d 帧）",
                         fr_max - fr_min + 1, fr_max - fr_min);
                $display("       这与 consume = pv1 & (pp1 != ppr1) 的逐时隙语义一致；");
                $display("       是否可听取决于跨度与包络，需另行评估（已记入状态表）。");
            end
            else begin
                $display("  FAIL  V4 仅 %0d/%0d 个槽在 60 帧内提交（待生效可能卡住）",
                         n_committed, P);
                fails = fails + 1;
            end
        end

        $display("==============================================================");
        if (fails == 0) $display("RESULT voice=PASS");
        else            $display("RESULT voice=FAIL fails=%0d", fails);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #200_000_000;
        $display("RESULT voice=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
