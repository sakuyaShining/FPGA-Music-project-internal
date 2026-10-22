//=============================================================================
// tb_alloc.v —— 声部分配/回收判据（阶段 3）
//
// 【要验的是什么】
//   `note_map` 的分配优先级是：同音重触发 > 空闲组 > round-robin 抢占。
//   但**"空闲"的判据是 `gtab[n] == FREE`**，而 note-off 分支只清 `gact`、
//   **从不把 `gtab` 写回 FREE** ⇒ 一旦 32 组都被用过，空闲搜索就永远不再命中，
//   之后每个 note-on 都走抢占（会把正在按住的音抢掉）。
//
// 【判据】
//   A1 连续按 N 个不同音（N < 32）后全部松开，再按第 N+1 个音：
//      该音应落在【新声部】，而**不是**抢占第一个声部。
//      —— 实测旧实现：slot0 会从 note0 变成 noteN（抢占）。
//   A2 正在按住的音不被抢：按住 note0 不放，再按 N 个音（N < 32），
//      note0 所在的组必须【始终在响】。
//   A3 回收后不挂音：松开后再按同一个音，它仍能被分配并发声。
//
// 【怎么读内部状态】
//   直接观察 `u_top.u_nm.gtab[]` 与 `gact[]`（层次引用）。
//   判据不依赖"猜到"哪个组，而是看**被按的那个组号有没有变**。
//=============================================================================
`timescale 1ns/1ps

module tb_alloc;

    localparam integer NG  = 32;
    //   ★ 必须**填满全部 32 组**才能暴露回收缺陷。
    //     缺陷是"note-off 不把 gtab 写回 FREE"；若只用了 20 组，
    //     剩下 12 组的 gtab 本来就是 FREE，空闲搜索照样命中 ⇒ 判据假绿。
    //     第一版取 NN=20，结果 A1 直接 PASS（掩盖了缺陷）—— 这是"激励强度不够"
    //     造成的假绿，和前面几轮踩过的坑同类。
    localparam integer NN  = 32;         // 填满全部组

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    wire [15:0] pad_bus = 16'h0000;      // 电极驱动到确定空闲态（悬空会被当触摸）
    reg         uart_rx = 1'b1;
    wire        uart_tx;
    reg         ev_valid, ev_on;
    reg [6:0]   ev_note;
    reg [3:0]   ev_vel;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    integer i, g;
    integer fails;
    integer note0_grp;
    integer note0_grp_after;
    integer new_grp;

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

    //   发一个事件并等它被处理完（note_map 一次约 20 拍，给足 80 拍）
    task ev;
        input [6:0] n;
        input       on;
        begin
            ev_note = n; ev_on = on; ev_vel = 4'd10; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            repeat (80) @(posedge clk);
        end
    endtask

    //   查某个音当前落在哪个组（返回 -1 表示没找到）
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

    //   有几个组处于"在响"（gact=1）
    //   注：写成 task 而不是 function —— iverilog 要求 function 至少有一个输入端口，
    //   而这里不需要参数。
    integer act_cnt;
    task count_active;
        integer k;
        begin
            act_cnt = 0;
            for (k = 0; k < NG; k = k + 1) if (u_top.u_nm.gact[k]) act_cnt = act_cnt + 1;
        end
    endtask

    initial begin
        $display("==============================================================");
        $display(" 声部分配/回收判据（阶段 3）");
        $display("==============================================================");

        fails = 0;
        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (3000) @(posedge clk);

        //--------------------------------------------------------------- A1
        $display(" A1 先按 %0d 个音再全部松开，然后按一个新音：应落在新声部", NN);
        ev(7'd40, 1'b1);
        note0_grp = grp_of(7'd40);
        $display("      note40 落在组 %0d", note0_grp);

        for (i = 1; i < NN; i = i + 1)
            ev(7'd40 + i[6:0], 1'b1);
        count_active;
        $display("      已按 %0d 个音，在响组数 = %0d", NN, act_cnt);

        //   全部松开（note0 留到最后单独看，所以先松 1..NN-1）
        for (i = 1; i < NN; i = i + 1)
            ev(7'd40 + i[6:0], 1'b0);
        count_active;
        $display("      松开 %0d 个后，在响组数 = %0d", NN - 1, act_cnt);

        //   此时若回收生效，应有大量组回到 FREE；打印 FREE 组数便于定位
        begin : freecnt
            integer k, f;
            f = 0;
            for (k = 0; k < NG; k = k + 1)
                if (u_top.u_nm.gtab[k] == 7'd127) f = f + 1;
            $display("      gtab==FREE 的组数 = %0d（回收生效的话应 >= %0d）", f, NN - 1);
        end

        //   此时 1..NN-1 已释放，若回收生效，空闲搜索应命中它们
        ev(7'd100, 1'b1);
        new_grp = grp_of(7'd100);
        $display("      新音 note100 落在组 %0d（note40 在组 %0d）", new_grp, note0_grp);
        if (new_grp == note0_grp) begin
            $display("  FAIL  A1 新音抢占了仍在按住的 note40 所在组 ⇒ 空闲搜索没命中（回收缺失）");
            fails = fails + 1;
        end
        else $display("  PASS  A1 新音落在别的组（未抢占按住的音）");

        //--------------------------------------------------------------- A2
        $display(" A2 正在按住的音不被抢");
        note0_grp_after = grp_of(7'd40);
        check("A2-held-note-still-active", note0_grp_after, note0_grp);

        //--------------------------------------------------------------- A3
        $display(" A3 松开后重按同一个音仍能发声");
        ev(7'd40, 1'b0);
        repeat (200) @(posedge clk);
        ev(7'd40, 1'b1);
        g = grp_of(7'd40);
        $display("      重按 note40 落在组 %0d", g);
        if (g < 0) begin
            $display("  FAIL  A3 重按后找不到在响的组（挂音或分配失败）");
            fails = fails + 1;
        end
        else $display("  PASS  A3 重按可正常分配（组 %0d）", g);

        $display("==============================================================");
        if (fails == 0) $display("RESULT alloc=PASS");
        else            $display("RESULT alloc=FAIL fails=%0d", fails);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #200_000_000;
        $display("RESULT alloc=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
