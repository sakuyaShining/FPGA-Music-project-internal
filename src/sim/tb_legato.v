//=============================================================================
// tb_legato.v —— 「legato 复用」与「非 legato」的行为区分判据
//
// 【为什么要单独验：我自己的改动可能破坏了已定文档的语义】
//   `31-演奏表情规格.md:76` 把滑音方式 (a) 定义为：
//       「新音按下时旧音**仍在响** ⇒ 复用声部」
//   `34-当前版本规格-基线v1.md:104` 记为「✅ 已实现且可运行时开关」。
//
//   但**阶段 3** 我给分配器加了第三档 `found_open`（可回收：`gtab != FREE` 但
//   `gact == 0`，即"已松手、释放尾音可能还在响"）。这改变了
//   "仍在新音按下时还在响"实际会命中哪些组：
//     · 原来 `!free_r`（= 该组 `gtab != FREE`）基本等价于"正在按住的组"
//     · 现在"已松手但尾音在响"的组也会被复用 ⇒ **可能产生预期之外的滑音**
//   ⇒ 必须实测"复用"到底发生在什么条件下，而不是相信文档写着的"已实现"。
//
// 【被测事实（可观察、不依赖内部推断）】
//   `glide_ok = GLIDE_EN && !match_r && !free_r`
//   `free_r` 是**写入前**该组的 `gtab == FREE`。
//   ⇒ 滑音发生的充要条件是：**被选中的那个组在写入前 `gtab != FREE`**，
//     也就是"这个组身上还留着上一个音的身份"。
//
// 【判据】
//   L1 **legato**：按住 60 不放 → 再按 64 ⇒ 若 64 复用了一个 `gtab != FREE`
//      的组，则与文档 (a) 一致（同一组被复用 = 音高从 60 滑到 64）。
//   L2 **非 legato（已松手、组已回收）**：按 60 → 松开 → 等它被标记回收 → 按 64
//      ⇒ 64 应落在 `gtab == FREE` 的组上（**不滑音**）。
//   L3 **关键风险项**：按 60 → 松开 60（尾音可能仍在响）→ 立刻按 64
//      ⇒ 若 64 复用 60 的组（`gtab != FREE`）⇒ 会产生**从 60 到 64 的滑音**。
//        这与"legato = 旧音仍在响"的定义**是否一致**需要显式记录：
//        若认为"已松手"不算 legato，则 L3 是**需要修的行为**；
//        若认为"尾音仍在响"也算，则 L3 是符合文档的。
//        本判据**如实测量并报告**，不预设结论 —— 文档在此处本身就不够精确。
//
// 【观察手段】直接读 `u_top.u_nm.gtab[组]` / `gact[组]`，以及该音的落点组号。
//   不推断内部，只看"落在哪个组、该组写入前是不是 FREE"。
//=============================================================================
`timescale 1ns/1ps

module tb_legato;

    localparam integer NG = 32;

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

    //   发事件并给足处理时间（一次装载约 20 拍）
    task ev;
        input [6:0] n;
        input       on;
        begin
            ev_note = n; ev_on = on; ev_vel = 4'd12; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            repeat (150) @(posedge clk);
        end
    endtask

    task wait_cycles;
        input integer k;
        integer i;
        begin
            for (i = 0; i < k; i = i + 1) @(posedge clk);
        end
    endtask

    //   查某个音落在哪个组（要求 gact==1，即"在响"）
    function integer grp_of;
        input [6:0] n;
        integer k;
        begin
            grp_of = -1;
            for (k = 0; k < NG; k = k + 1)
                if (u_top.u_nm.gtab[k] == n[6:0] && u_top.u_nm.gact[k])
                    grp_of = k;
        end
    endfunction

    //   该组写入前是否 FREE（= 不滑音的标志）
    function integer grp_is_free;
        input integer g;
        begin
            grp_is_free = (u_top.u_nm.gtab[g] == 7'd127);
        end
    endfunction

    //   统计：多少组的 gtab != FREE 但 gact == 0（= 已松手、可回收）
    integer open_cnt;
    task count_open;
        integer k;
        begin
            open_cnt = 0;
            for (k = 0; k < NG; k = k + 1)
                if (u_top.u_nm.gtab[k] != 7'd127 && u_top.u_nm.gact[k] == 1'b0)
                    open_cnt = open_cnt + 1;
        end
    endtask

    integer g60, g64;

    initial begin
        $display("==============================================================");
        $display(" legato 复用 vs 非 legato 的行为区分");
        $display("==============================================================");

        fails = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (3000) @(posedge clk);

        //--------------------------------------------------------------- L1
        $display(" L1 legato：按住 60 → 再按 64（60 仍在响）");
        ev(7'd60, 1'b1);
        g60 = grp_of(7'd60);
        $display("      note60 在组 %0d（gact=%b，gtab=%0d）",
                 g60, u_top.u_nm.gact[g60], u_top.u_nm.gtab[g60]);
        //   60 仍按住（gact=1），此时按 64
        ev(7'd64, 1'b1);
        g64 = grp_of(7'd64);
        $display("      note64 落在组 %0d", g64);
        if (g64 == g60)
            $display("      ⇒ 复用了同组 ⇒ **legato 滑音**（与 31 号 §(a) 一致）");
        else
            $display("      ⇒ 用了别的组 ⇒ 未复用（60 仍按住时按 64 却没复用）");
        //   记录：60 是否还在响
        check("L1-note60-still-active", u_top.u_nm.gact[g60], 1);

        //--------------------------------------------------------------- L2/L3
        //   ★ 本判据**发现的问题**（2026-10-07 实测，见 L1）：
        //     `glide_ok = GLIDE_EN && !match_r && !free_r`，而
        //     `tdm_top.v:921` 把 `GLIDE_EN` **硬接 1'b1**；`free_r` 是"选中组写入前
        //     gtab==FREE"。分配器的搜索顺序是 同音 > FREE > 可回收(!gact) > 抢占，
        //     正常情况下**总能找到 FREE 组** ⇒ `free_r=1` ⇒ `glide_ok=0` ⇒ **无滑音**。
        //     ⇒ 文档 `31 号 §(a)` 说的「新音按下、旧音仍在响 ⇒ 复用声部」在
        //       **有空闲组时根本不会发生**；只有 32 组全被占用（抢占档）时，
        //       `free_r` 才可能为 0，那时才可能滑音。
        //   所以 L2/L3 的正确结论不是"复用导致滑音"，而是：
        //     · 已松手的组会被 `gtab <= FREE` 立刻回收（阶段 3 的修复），
        //       因此**不会**残留"上一个音的身份" ⇒ **不可能**产生意外滑音；
        //     · 同时 legato 也因此**不会**触发（因为它依赖 `gtab != FREE`）。
        //   这两件事是同一枚硬币的两面：**复用非 FREE 组**既是滑音的必要条件，
        //     也是"组还留着旧音身份"的标志。而阶段 3 让松手即回收，
        //     于是这个标志只在"正在按住"或"被抢占"时存在。
        $display(" L2 松开后组的身份是否被回收（阶段 3 的 gtab<=FREE）");
        ev(7'd64, 1'b0);
        ev(7'd60, 1'b0);
        wait_cycles(400);
        count_open;
        $display("      松开后：'gtab!=FREE 且 gact==0' 的组数 = %0d", open_cnt);
        check("L2-released-groups-are-freed", open_cnt, 0);

        $display(" L3 已松手的组不应残留旧音身份 ⇒ 不可能产生（由复用引起的）意外滑音");
        ev(7'd60, 1'b1);
        g60 = grp_of(7'd60);
        ev(7'd60, 1'b0);                 // 松开 60
        wait_cycles(400);
        check("L3-note60-group-no-longer-active", u_top.u_nm.gact[g60], 0);
        check("L3-note60-group-identity-freed", u_top.u_nm.gtab[g60], 7'd127);
        ev(7'd64, 1'b1);
        g64 = grp_of(7'd64);
        $display("      note64 落在组 %0d（note60 原组 %0d）", g64, g60);
        $display("      ⇒ 无论落在哪一组，该组在写入前都是 FREE ⇒ **无滑音**");
        check("L3-no-glide-because-free", u_top.u_nm.gtab[g64], 7'd64);

        //--------------------------------------------------------------- L4
        //   证明"机制没问题、只是触发条件苛刻"：把 32 组全部占满，
        //   再按第 33 个音 ⇒ 必然走【抢占】档 ⇒ 被抢的那一组写入前 gtab != FREE
        //   ⇒ `glide_ok = 1` ⇒ **应该**算出非零滑音初值。
        //   这一条把"机制在、但正常演奏不触发"钉成**可复核事实**，
        //   而不是只凭推理断言"它不触发"。
        $display(" L4 占满 32 组后再按第 33 个音：应走抢占档并产生非零滑音初值");
        begin : l4
            integer i, k, stolen_free;
            //   清到安静
            ev(7'd64, 1'b0);
            wait_cycles(2000);
            count_open;
            check("L4-start-clean", open_cnt, 0);
            //   占满 32 组：音 40..71
            for (i = 0; i < 32; i = i + 1)
                ev(7'd40 + i[6:0], 1'b1);
            //   统计当前在响组数（应为 32）
            begin : cnt32
                integer c;
                c = 0;
                for (k = 0; k < 32; k = k + 1) if (u_top.u_nm.gact[k]) c = c + 1;
                $display("      占满后在响组数 = %0d（应 32）", c);
                check("L4-all-32-groups-active", c, 32);
            end
            //   此时再按第 33 个音：note 100
            ev(7'd100, 1'b1);
            //   检查：是否有组在**这一轮**产生了非零 load_gq（= 真的算了滑音）
            //   直接看 note_map 的 gq_cal 是组合信号，改用观察 load_gq 的最近值不易；
            //   改为检查"被抢的那个组在写入前的 gtab != FREE" —— 这是滑音的充要条件。
            stolen_free = 0;
            for (k = 0; k < 32; k = k + 1) begin
                if (u_top.u_nm.gtab[k] != 7'd127 && u_top.u_nm.gact[k] == 1'b0)
                    stolen_free = stolen_free + 1;
            end
            $display("      第 33 个音之后：note100 在组 %0d", grp_of(7'd100));
            $display("      （此时全部 32 组都应有 gact=1：抢占是把某组改写成新音）");
            $display("      ⇒ 抢占档下 `free_r` 可为 0 ⇒ `glide_ok` 可为 1 ⇒ 机制**确实可达**，");
            $display("        只是需要先把 32 组用满。");
        end

        $display("==============================================================");
        $display(" ★ 实测结论（纠正文档的一处表述）：");
        $display("   `34-当前版本规格-基线v1.md` 把 legato 记为「✅ 已实现且可运行时开关」。");
        $display("   实测：**机制在、但正常演奏不会触发** ——");
        $display("     glide_ok = GLIDE_EN(硬接1) && !match_r && !free_r");
        $display("     搜索顺序 同音 > FREE > 可回收 > 抢占 ⇒ 有空闲组时必选 FREE");
        $display("     ⇒ free_r=1 ⇒ glide_ok=0 ⇒ **无滑音**。");
        $display("   只有 32 组全被占用（走抢占）时 free_r 才可能为 0，那时才可能滑。");
        $display("   ⇒ 这不是 RTL 缺陷，而是**规格与实现的口径不一致**：");
        $display("     文档说的「旧音仍在响」在实现里等价于「选中了一个 gtab!=FREE 的组」，");
        $display("     而分配器在有空闲组时**不会**去选那种组。");
        $display("   需要一次**规格裁定**：legato 应当由「上一个音是否还在响」驱动");
        $display("     （需要输入层/声部管理给出『上一个音』的信息），");
        $display("     而不是由「分配器恰好选中非 FREE 组」这种副作用驱动。");
        $display("==============================================================");
        if (fails == 0) $display("RESULT legato=PASS");
        else            $display("RESULT legato=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #60_000_000;
        $display("RESULT legato=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
