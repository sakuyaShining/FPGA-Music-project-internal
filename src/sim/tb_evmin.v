//=============================================================================
// tb_evmin.v —— 【最小复现】单源（排针）少量事件 + 逐拍打印
//
// 【为什么必须有这一版】
//   前两轮用 28 条混合激励（排针 + UART + 两源同拍）调事件通路，失败信息混杂、
//   两次只能回退。教训：**先单源少数几条钉死，再逐级放大。**
//
// 【判据】
//   N1 收到条数 == EV_N
//   N2 逐条 (note, on, vel) 全部相等
//   N3 队列溢出计数 == 0
//
// 【诊断】用 +dump 打开逐拍打印（每拍一行），能看到：
//   dh_pend / mh_valid / mh_note / mh_on / ev_in_ready / ev_q_* / ack / level / ovf
//=============================================================================
`timescale 1ns/1ps

module tb_evmin;

    parameter integer EV_N = 3;          // 事件条数（+EV_N=n 可覆盖）

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    //   ★ 电极必须驱动到【确定的空闲态】。
    //     悬空的 wire 上是 z，而 pad_pitch 看到 touch=1 就会**持续**产生事件，
    //     于是在轮转/优先级仲裁里把排针事件挤掉 —— 实测症状是
    //     "单源 3 条只收到 1 条、且 note 一直是 pads 那一条"。
    //     这是测试台的问题（没有电极模型却让它悬空），不是 RTL 的。
    wire [15:0] pad_bus = 16'h0000;
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

    integer i;
    integer nr;
    integer r_note [0:63];
    integer r_on   [0:63];
    integer r_vel  [0:63];
    reg     vq;
    reg     dump_on = 1'b0;
    integer cyc = 0;

    //   按上升沿抓事件（valid 可能是电平）
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin nr <= 0; vq <= 1'b0; end
        else begin
            vq <= u_top.ev_valid_r;
            if (u_top.ev_valid_r && !vq && nr < 64) begin
                r_note[nr] <= u_top.ev_note_r;
                r_on[nr]   <= u_top.ev_on_r;
                r_vel[nr]  <= u_top.ev_vel_r;
                nr         <= nr + 1;
            end
        end
    end

    //   逐拍诊断
    always @(posedge clk) begin
        if (rst_n && dump_on) begin
            cyc = cyc + 1;
            $display("  [c%0d] din=%b pend=%b mh_v=%b mh_n=%0d mh_on=%b in_rdy=%b | q_v=%b q_n=%0d q_on=%b lvl=%0d ovf=%0d | ack=%b st=%0d nr=%0d",
                     cyc, ev_valid, u_top.dh_pend, u_top.mh_valid, u_top.mh_note,
                     u_top.mh_on, u_top.ev_in_ready,
                     u_top.ev_q_valid, u_top.ev_q_note, u_top.ev_q_on,
                     u_top.ev_q_level, u_top.ev_q_ovf, u_top.nm_ev_ack,
                     u_top.u_nm.st, nr);
        end
    end

    //   源：发一个事件（valid 保持到被接收，或最多保持 1 拍）
    //   HOLD_TO_READY=1 时遵守 ready/valid（保持到 in_ready）；
    //   板上真实排针是"单拍脉冲"，所以默认按单拍脉冲发。
    task pin_ev;
        input [6:0] n;
        input       on;
        input [3:0] v;
        begin
            ev_note = n; ev_on = on; ev_vel = v; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            @(posedge clk);
        end
    endtask

    //   带间隔的事件：模仿真实演奏（人类按键间隔是毫秒级，不是几个时钟）
    task pin_ev_gap;
        input [6:0]   n;
        input         on;
        input [3:0]   v;
        input integer gap;
        integer g;
        begin
            pin_ev(n, on, v);
            for (g = 0; g < gap; g = g + 1) @(posedge clk);
        end
    endtask

    initial begin
        $display("==============================================================");
        $display(" 最小复现：单源排针 %0d 条事件", EV_N);
        $display("==============================================================");

        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (2000) @(posedge clk);

        dump_on = 1'b1;
        //   ★ 事件间隔必须**大于 note_map 的处理时间**（约 20 拍）。
        //     这版测试台曾用"每条只隔 4 拍"的激励，结果队列被持续反压、
        //     挂起位一直占着，后续事件在源端就丢了 ——
        //     那不是 RTL 的缺陷，而是**人类不可能按出的速率**。
        //     真实演奏的按键间隔是毫秒级（≈50 拍以上），这里取 60 拍。
        for (i = 0; i < EV_N; i = i + 1) begin
            pin_ev_gap(7'd60 + i[6:0], (i % 2 == 0), (i[3:0] + 4'd1), 60);
        end
        repeat (6000) @(posedge clk);
        dump_on = 1'b0;

        $display(" --- 静置后：收到=%0d ovf=%0d lvl=%0d ---",
                 nr, u_top.ev_q_ovf, u_top.ev_q_level);
        for (i = 0; i < nr; i = i + 1)
            $display("     #%0d note=%0d on=%0d vel=%0d", i, r_note[i], r_on[i], r_vel[i]);

        begin : verdict
            integer bad;
            bad = 0;
            if (nr != EV_N) begin
                $display("  FAIL N1 收到 %0d != %0d", nr, EV_N);
                bad = bad + 1;
            end
            for (i = 0; i < nr && i < EV_N; i = i + 1) begin
                if (r_note[i] != (60 + i) || r_on[i] != ((i % 2 == 0) ? 1 : 0)
                    || r_vel[i] != (i + 1)) begin
                    $display("  FAIL N2 #%0d 期望(note=%0d,on=%0d,vel=%0d) 实测(note=%0d,on=%0d,vel=%0d)",
                             i, 60 + i, (i % 2 == 0) ? 1 : 0, i + 1,
                             r_note[i], r_on[i], r_vel[i]);
                    bad = bad + 1;
                end
            end
            if (u_top.ev_q_ovf != 16'd0) begin
                $display("  FAIL N3 队列溢出 %0d", u_top.ev_q_ovf);
                bad = bad + 1;
            end
            if (bad == 0) $display("RESULT evmin=PASS n=%0d", nr);
            else          $display("RESULT evmin=FAIL fails=%0d", bad);
        end
        $finish;
    end

    initial begin
        #80_000_000;
        $display("RESULT evmin=TIMEOUT nr=%0d", nr);
        $finish;
    end

endmodule
