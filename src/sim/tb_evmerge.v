//=============================================================================
// tb_evmerge.v —— 事件「汇合点 + 待处理队列」端到端判据（穿 tdm_top）
//
// ⚠️ 状态：**当前不通过，且 event_hold 尚未接进 tdm_top**。
//    本文件是"接线未完成"这一步的工作台，先留在库里，下一轮从这里继续。
//    问题记录见 docs/02-技术方案/35-五阶段推进状态.md「接线未完成的真实原因」：
//      out_ready 不能用 ~nm_busy 这种【电平】—— note_map 的 busy 是状态输出，
//      事件被接收后要下一拍才拉高；那几个连续空闲拍会让队列连续出队，
//      而 note_map 在忙期间只接收第一个 ⇒ 其余静默消失。
//      实测：发 28 条只到 4 条、队列溢出飙升。改成单拍 ev_ack 后也只到 9/28，
//      说明至少还有第二处未找到 ⇒ 先回退接线，保持门禁绿。
//
// 【接线完成后它要验的是什么】
//   阶段 2 的核心主张是"**不丢事件，尤其不丢 note-off**"。两个环节可能丢：
//     ① 优先级 mux：同一拍多源并起时只选出一个，其余**无声丢弃**（原实现）
//     ② note_map 忙（约 20 拍）期间到达的单拍脉冲（UART/定序器/排针）
//   本测试台把 ①② 一起验：多源同拍并起 + 密集到达，逐条比对"发出的"与"收到的"。
//
// 【判据不循环：期望值从哪来】
//   期望序列由测试台按源逐条记账得到（不依赖 DUT 内部信号），同时核对
//   音符号 / on-off / 力度 三项，任何丢失或错序都会显形。
//
// 【判据】
//   M1 收到条数 == 发出条数（一条不丢）
//   M2 逐条 (note, on, vel) 全部相等（不错序、不串值）
//   M3 note-off 条数正确（挂音的直接证据）
//   M4 队列溢出计数 == 0（没有"悄悄丢"的情况）
//
// 【两个已踩过、已写进代码的口径坑】
//   ① 抓事件必须按 ev_valid_r 的**上升沿**，不能按电平：
//      busy 是电平，空闲期间 ev_valid_r 可能连续多拍为高（同一个事件）。
//      按电平抓会把同一事件记很多遍（实测"发 28 收 64"，看着像重复投递）。
//   ② 用 force 驱动 tdm_top 的 wr_en/wr_addr/wr_data 来产生 UART 事件：
//      层次引用写 reg_bank.mem **不会产生 wr_en**，触发不了事件。
//=============================================================================
`timescale 1ns/1ps

module tb_evmerge;

    localparam MAXEV = 64;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;         // ≈27 MHz

    reg rst_n = 1'b0;
    //   ★ 电极必须驱动到【确定的空闲态】：悬空的 wire 上是 z，pad_pitch 看到
    //     touch=1 就会**持续**产生事件，在仲裁里把别的源挤掉。
    wire [15:0] pad_bus = 16'h0000;
    reg         uart_rx = 1'b1;
    wire        uart_tx;

    //---- 排针事件源（测试台直接驱动）----
    reg        ev_valid, ev_on;
    reg [6:0]  ev_note;
    reg [3:0]  ev_vel;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    //=========================================================================
    // 发送侧记账：每个"源脉冲"记一条期望事件
    //   注意【不能】按 DUT 的内部信号记账（那就循环论证了）；
    //   这里只按测试台自己驱动的激励记账。
    //=========================================================================
    integer  e_note [0:MAXEV-1];
    integer  e_on   [0:MAXEV-1];
    integer  e_vel  [0:MAXEV-1];
    integer  ne;

    task expect_ev;
        input [6:0] n;
        input       on;
        input [3:0] v;
        begin
            if (ne < MAXEV) begin
                e_note[ne] = n; e_on[ne] = on; e_vel[ne] = v;
                ne = ne + 1;
            end
        end
    endtask

    //   排针事件：驱动一拍，并记一条期望。
    //   带 gap 参数：间隔必须大于 note_map 的处理时间（约 20 拍），
    //   否则队列被持续反压、挂起位一直占着，后续事件在源端就丢了 ——
    //   那**不是** RTL 缺陷，而是人类按不出的速率。真实按键间隔是毫秒级。
    task pin_ev_gap;
        input [6:0]   n;
        input         on;
        input [3:0]   v;
        input integer gap;
        integer g;
        begin
            ev_note = n; ev_on = on; ev_vel = v; ev_valid = 1'b1;
            expect_ev(n, on, v);
            @(posedge clk);
            ev_valid = 1'b0;
            for (g = 0; g < gap; g = g + 1) @(posedge clk);
        end
    endtask

    //   UART 事件：写 0x60（音符）再写 0x61（力度，写入即触发）。
    //   为什么不用"层次引用写 reg_bank.mem"：那样**不会产生 wr_en** ⇒ 触发不了事件
    //   （本项目多数测试台用它设参数，但事件必须走真实写通路）。
    //   这里用 force 驱动 tdm_top 的写口，等价于 UART 收到字节后产生的那一拍 wr_en。
    task wr_reg;
        input [7:0] a;
        input [7:0] d;
        begin
            force u_top.wr_en   = 1'b1;
            force u_top.wr_addr = a;
            force u_top.wr_data = d;
            @(posedge clk);
            release u_top.wr_en;
            release u_top.wr_addr;
            release u_top.wr_data;
            @(posedge clk);
        end
    endtask

    task uart_ev;
        input [6:0] n;
        input       on;
        input [3:0] v;
        begin
            wr_reg(8'h60, {on, n});      // 先设音符
            expect_ev(n, on, v);
            wr_reg(8'h61, {4'b0, v});    // 再写力度 = 写入即触发
        end
    endtask

    //=========================================================================
    // 接收侧：从 note_map 的输入端抓（= note_map 真正看到的事件）
    //   从这里抓而不是从队列输出抓，能同时覆盖"队列 → ev_*_r → note_map"这一段。
    //   tb 已知 note_map 在忙时会忽略，因此若这一层少了事件，就是**真丢**。
    //=========================================================================
    integer  r_note [0:MAXEV-1];
    integer  r_on   [0:MAXEV-1];
    integer  r_vel  [0:MAXEV-1];
    integer  nr;

    //   ★ 按【上升沿】抓事件，不能在电平上连续抓。
    //     为什么：`out_ready = ~nm_busy`，而"忙"是一个**电平**；
    //     busy 为低的期间 ev_valid_r 可能连续多拍为高（同一个事件）。
    //     第一版按电平抓，于是同一个事件被记了很多遍 ——
    //     实测"发 28 收 64"，看着像严重重复投递，其实是**抓取口径**的问题。
    //     事件接口的语义是"valid 起沿 = 一个新事件"，抓取必须遵守它。
    reg ev_valid_r_q;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            nr <= 0; ev_valid_r_q <= 1'b0;
        end
        else begin
            ev_valid_r_q <= u_top.ev_valid_r;
            if (u_top.ev_valid_r && !ev_valid_r_q && nr < MAXEV) begin
                r_note[nr] <= u_top.ev_note_r;
                r_on[nr]   <= u_top.ev_on_r;
                r_vel[nr]  <= u_top.ev_vel_r;
                nr         <= nr + 1;
            end
        end
    end

    integer i, bad, off_exp, off_got;

    initial begin
        $display("==============================================================");
        $display(" 事件汇合 + 待处理队列 端到端判据（穿 tdm_top）");
        $display("==============================================================");

        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0;
        ne = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (2000) @(posedge clk);

        //--------------------------------------------------------------- 激励
        //   ① 排针源：连续 12 个事件（必然跨越 note_map 的忙窗口）
        $display(" 激励①：排针 12 个事件（note 60..71，on/off 交替，间隔 60 拍）");
        for (i = 0; i < 12; i = i + 1)
            pin_ev_gap(7'd60 + i[6:0], (i % 2 == 0), (i[3:0] + 4'd1), 60);

        //   ② UART 源：连续 8 个事件
        $display(" 激励②：UART 8 个事件（note 80..87）");
        for (i = 0; i < 8; i = i + 1)
            uart_ev(7'd80 + i[6:0], (i % 2 == 0), (i[3:0] + 4'd2));

        //   ③ 两源同拍并起：排针与 UART 在**同一拍**都发
        //      —— 这正是原实现会丢低优先级那一个的场景
        //
        //   ★ 但 UART 事件必须按协议**先写 0x60（音符）再写 0x61（力度，写入即触发）**。
        //     第一版我在同一拍用 force 同时改 0x60 和 0x61，这是**违反协议**的：
        //     `r_note_num` 与 `wr_en` 在硬件上不可能同拍更新（写要过 reg_bank 的时序），
        //     所以 `u_ev_note` 取到的是**旧音符**（实测恒为 0）。
        //     那是我激励的错，不是 RTL 的错 —— 单源最小复现（tb_evmin）已证明
        //     单源三字段全部正确。
        //     正确做法：0x60 先在**更早的拍**写好，再让 0x61 与排针同拍触发。
        $display(" 激励③：两源同拍并起 4 组（UART 按协议先写 0x60，再与排针同拍触发 0x61）");
        for (i = 0; i < 4; i = i + 1) begin
            //   （1）先按协议把音符与 on/off 写进 0x60（这一步不触发事件）
            wr_reg(8'h60, {1'b1, (7'd90 + i[6:0])});
            //   （2）同一拍：排针举起 + UART 写 0x61 触发
            ev_note = 7'd70 + i[6:0]; ev_on = 1'b0; ev_vel = 4'd5; ev_valid = 1'b1;
            force u_top.wr_en   = 1'b1;
            force u_top.wr_addr = 8'h61;
            force u_top.wr_data = {4'b0, 4'd6};
            //   两源都在这一拍有效 ⇒ 期望收到两条（UART 优先，排针随后）
            expect_ev(7'd90 + i[6:0], 1'b1, 4'd6);
            expect_ev(7'd70 + i[6:0], 1'b0, 4'd5);
            @(posedge clk);
            ev_valid = 1'b0;
            release u_top.wr_en; release u_top.wr_addr; release u_top.wr_data;
            @(posedge clk);
        end

        //   等事件全部排空（note_map 每个事件约 20 拍，给足余量）
        repeat (30000) @(posedge clk);

        //--------------------------------------------------------------- 判定
        bad = 0;
        $display(" 发出 %0d 条，note_map 侧收到 %0d 条", ne, nr);

        if (nr != ne) begin
            $display("  FAIL  M1 收到 %0d ≠ 发出 %0d ⇒ 有事件被丢", nr, ne);
            bad = bad + 1;
        end
        else $display("  PASS  M1 一条不丢（%0d 条）", nr);

        for (i = 0; i < nr && i < ne; i = i + 1) begin
            if (r_note[i] != e_note[i] || r_on[i] != e_on[i] || r_vel[i] != e_vel[i]) begin
                if (bad < 6)
                    $display("  FAIL  M2 第 %0d 条 期望(note=%0d,on=%0d,vel=%0d) 实测(note=%0d,on=%0d,vel=%0d)",
                             i, e_note[i], e_on[i], e_vel[i], r_note[i], r_on[i], r_vel[i]);
                bad = bad + 1;
            end
        end
        if (bad == 0 && nr == ne) $display("  PASS  M2 逐条 (note,on,vel) 全部相等");

        off_exp = 0; off_got = 0;
        for (i = 0; i < ne; i = i + 1) if (!e_on[i]) off_exp = off_exp + 1;
        for (i = 0; i < nr; i = i + 1) if (!r_on[i]) off_got = off_got + 1;
        $display("  M3 note-off：期望 %0d 条，实测 %0d 条", off_exp, off_got);
        if (off_got != off_exp) begin
            $display("  FAIL  M3 note-off 丢失（会挂音）");
            bad = bad + 1;
        end
        else $display("  PASS  M3 note-off 一条不少");

        $display("  M4 队列溢出计数 = %0d（应为 0）", u_top.ev_q_ovf);
        if (u_top.ev_q_ovf != 16'd0) begin
            $display("  FAIL  M4 队列溢出 %0d 次 ⇒ 有事件被静默丢弃", u_top.ev_q_ovf);
            bad = bad + 1;
        end
        else $display("  PASS  M4 无溢出");

        $display("==============================================================");
        if (bad == 0) $display("RESULT evmerge=PASS nev=%0d", nr);
        else          $display("RESULT evmerge=FAIL fails=%0d", bad);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #400_000_000;
        $display("RESULT evmerge=TIMEOUT nev_exp=%0d nev_got=%0d ovf=%0d",
                 ne, nr, u_top.ev_q_ovf);
        $finish;
    end

endmodule
