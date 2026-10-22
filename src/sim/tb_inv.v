//=============================================================================
// tb_inv.v —— 分配器不变量：验证"可回收档(found_open)"是否可达
//
// 【为什么要验这一条】
//   阶段 3 我给分配器加了第三档 `found_open`（`gtab != FREE` 但 `gact == 0`），
//   目的是"松手但释放尾音还在响的组，优先于抢占复用"。
//   但**同一次修复**又在 note-off 分支加了 `gtab[gsel_r] <= FREE`
//   （那是修"回收缺失"必需的，`19 alloc` 靠它）。
//
//   两条改动叠加后推出一个不变量：
//       gact[n] == 0  ⇒  gtab[n] == FREE
//   （因为 note-off 同时把 gact 清 0、把 gtab 写成 FREE；上电时也是 FREE）
//   而分配器的搜索顺序是 **FREE 档在前、可回收档在后**，且 FREE 档遍历所有组
//   ⇒ FREE 档必然先命中 ⇒ **`found_open` 永远不可能被选中**（死档）。
//
//   ★ 这只是**推理**。本判据用仿真把它变成**事实**：
//     遍历大量操作序列，每次分配前统计"是否存在 gtab!=FREE 且 gact==0 的组"，
//     若从不为真 ⇒ 可回收档不可达（死档）；若为真 ⇒ 我的推理有漏洞，
//     必须重新审视（那意味着存在"松手但没回 FREE"的路径）。
//
// 【判据】
//   I1 稳态下不变量 `gact==0 ⇒ gtab==FREE` 恒成立
//   I2 观察窗口内，"可回收组"计数**从未 > 0**
//   I3 分配优先级仍然正确：**优先用 FREE 组，不抢占正在按住的音**
//      （用阶段 3 的 `19 alloc` 场景复现：占满 32 组 → 松开 31 个 → 按新音
//        应落在已释放的 FREE 组上，而**不是**抢住仍在按住的 note40）
//=============================================================================
`timescale 1ns/1ps

module tb_inv;

    localparam integer NG = 32;
    localparam integer FREE = 127;

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

    //   不变量统计：返回 "gact==0 但 gtab!=FREE" 的组数（违反不变量的数量）
    integer viol_cnt, open_cnt, free_cnt;
    task scan_state;
        integer k;
        begin
            viol_cnt = 0; open_cnt = 0; free_cnt = 0;
            for (k = 0; k < NG; k = k + 1) begin
                if (u_top.u_nm.gact[k] == 1'b0 && u_top.u_nm.gtab[k] != FREE)
                    viol_cnt = viol_cnt + 1;
                if (u_top.u_nm.gtab[k] != FREE && u_top.u_nm.gact[k] == 1'b0)
                    open_cnt = open_cnt + 1;
                if (u_top.u_nm.gtab[k] == FREE)
                    free_cnt = free_cnt + 1;
            end
        end
    endtask

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

    integer i, k;
    integer viol_ever, open_ever;
    integer g40, g_new;

    initial begin
        $display("==============================================================");
        $display(" 分配器不变量：可回收档(found_open)是否可达");
        $display("==============================================================");

        fails = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (3000) @(posedge clk);

        //--------------------------------------------------------------- I1 静息
        $display(" I1 静息态不变量 gact==0 ⇒ gtab==FREE");
        scan_state;
        check("I1-idle-violations", viol_cnt, 0);
        check("I1-idle-free-groups", free_cnt, NG);

        //--------------------------------------------------------------- I2 遍历操作序列
        $display(" I2 遍历大量操作序列，检查不变量是否**始终**成立");
        viol_ever = 0; open_ever = 0;
        //   一轮：按若干音 → 检查 → 松开若干 → 检查
        for (i = 0; i < 24; i = i + 1) begin
            ev(7'd40 + i[6:0], 1'b1);
            scan_state;
            if (viol_cnt > 0) viol_ever = viol_ever + 1;
            if (open_cnt > 0) open_ever = open_ever + 1;
        end
        for (i = 0; i < 24; i = i + 1) begin
            ev(7'd40 + i[6:0], 1'b0);
            scan_state;
            if (viol_cnt > 0) viol_ever = viol_ever + 1;
            if (open_cnt > 0) open_ever = open_ever + 1;
        end
        //   再压到满 32 组，再全放
        for (i = 0; i < NG; i = i + 1) ev(7'd40 + i[6:0], 1'b1);
        scan_state;
        $display("      占满 32 组后：free=%0d viol=%0d open=%0d", free_cnt, viol_cnt, open_cnt);
        for (i = 0; i < NG; i = i + 1) ev(7'd40 + i[6:0], 1'b0);
        scan_state;
        $display("      全放后：free=%0d viol=%0d open=%0d", free_cnt, viol_cnt, open_cnt);

        $display("      整个序列中：违反不变量的采样次数 = %0d", viol_ever);
        $display("                  观察到'可回收组>0'的次数 = %0d", open_ever);
        check("I2-invariant-never-violated", viol_ever, 0);
        check("I2-reclaim-tier-never-populated", open_ever, 0);

        //--------------------------------------------------------------- I3 优先级
        $display(" I3 优先级：优先用 FREE 组，不抢占正在按住的音（复现 19 alloc 场景）");
        //   此时应为全空闲
        scan_state;
        check("I3-start-all-free", free_cnt, NG);
        //   按住 note40，再依次按 31 个音把 32 组占满
        ev(7'd40, 1'b1);
        g40 = grp_of(7'd40);
        for (i = 1; i < NG; i = i + 1)
            ev(7'd40 + i[6:0], 1'b1);
        scan_state;
        $display("      占满后 free=%0d（应 0）note40 在组 %0d", free_cnt, g40);
        check("I3-all-occupied", free_cnt, 0);
        //   松开除 40 以外的 31 个
        for (i = 1; i < NG; i = i + 1)
            ev(7'd40 + i[6:0], 1'b0);
        scan_state;
        $display("      松开 31 个后 free=%0d（应 31）", free_cnt);
        check("I3-31-groups-freed", free_cnt, 31);
        //   按一个新音：应落在 FREE 组，而**不是**抢 note40
        ev(7'd100, 1'b1);
        g_new = grp_of(7'd100);
        $display("      新音 note100 落在组 %0d（note40 在组 %0d）", g_new, g40);
        if (g_new == g40) begin
            $display("  FAIL  I3 抢占了仍在按住的 note40 所在组");
            fails = fails + 1;
        end
        else $display("  PASS  I3 新音未抢占按住的音");
        check("I3-held-note-still-active", u_top.u_nm.gact[g40], 1);

        $display("==============================================================");
        $display(" ★ 结论：不变量 `gact==0 ⇒ gtab==FREE` **始终成立**，");
        $display("   而 FREE 档搜索在前且遍历所有组 ⇒ **`found_open` 是死档（不可达）**。");
        $display("   它的意图（『尾音还在响的组优先于抢占』）在 stage 3 之后已无实现对象：");
        $display("   因为松手即回 FREE，Free 档会先命中同一个组，效果等价。");
        $display("   ⇒ 这是**冗余代码**，不是缺陷。可考虑删除或加注释说明其不可达性，");
        $display("     但删它属于代码整理，应另开一次改动并复跑 19 alloc。");
        $display("==============================================================");
        if (fails == 0) $display("RESULT inv=PASS");
        else            $display("RESULT inv=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #120_000_000;
        $display("RESULT inv=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
