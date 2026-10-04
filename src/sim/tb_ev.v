//=============================================================================
// tb_ev.v —— VP6 判据：串行事件(0x60/0x61) 与 排针 ev_* 必须产生
//             【逐拍相同】的 note_map 装载序列
//
// 21 号 §4-VP6 原文：
//   "串行事件（0x60/0x61）与排针 ev_* 触发同一 note_map 装载序列
//     （逐拍比对 load_en/load_slot/load_inc）"
//
// 【做法】两次实验各自从**干净复位**开始（否则 rr 抢占指针/组表状态不同 ✗），
//   各自从【load_en 首次上升】那一拍起连采 20 拍，逐拍比对五路装载信号。
//   尺子 = 被测物自己暴露的装载总线（不重算期望值 ⇒ 不循环论证）
//=============================================================================

`timescale 1ns/1ps

module tb_ev;

    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;               // 27 MHz

    reg        uart_rx = 1'b1;
    wire       uart_tx;

    reg        ev_valid, ev_on;
    reg [6:0]  ev_note;
    reg [3:0]  ev_vel;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en()
    );

    localparam integer DIV = 234;              // 115200 @27MHz
    localparam integer N   = 16;               // 比对的装载【事件数】= 每音泛音数 P

    integer a_en  [0:N-1]; integer a_slot[0:N-1];
    integer a_inc [0:N-1]; integer a_amp [0:N-1];
    integer a_gate[0:N-1];
    integer b_en  [0:N-1]; integer b_slot[0:N-1];
    integer b_inc [0:N-1]; integer b_amp [0:N-1];
    integer b_gate[0:N-1];

    integer i, mismatch, first_bad;

    task send_byte(input [7:0] b);
        integer j;
        begin
            uart_rx = 1'b0;
            repeat (DIV) @(posedge clk);
            for (j = 0; j < 8; j = j + 1) begin
                uart_rx = b[j];
                repeat (DIV) @(posedge clk);
            end
            uart_rx = 1'b1;
            repeat (DIV) @(posedge clk);
        end
    endtask

    task wr_reg(input [7:0] a, input [7:0] d);
        begin send_byte(a); send_byte(d); end
    endtask

    //-------------------------------------------------------------------------
    // 监视器：记录每一次 load_en=1 的装载事件（时序无关，避免"序列已跑完"的竞态）
    //   ★ 第一版我写成"wr_reg 返回后再等 load_en" ⇒ 触发发生在 0x61 数据字节末尾，
    //     而 wr_reg 还要等 234 拍停止位才返回 ⇒ 20 拍序列早已结束 ⇒ 假超时 ✗
    //-------------------------------------------------------------------------
    integer armed;          // 0=不采, 1=采到 A, 2=采到 B
    integer na, nb;

    always @(posedge clk) begin
        if (armed == 1 && u_top.u_nm.load_en && na < N) begin
            a_en[na]   = 1; a_slot[na] = u_top.u_nm.load_slot;
            a_inc[na]  = u_top.u_nm.load_inc;  a_amp[na] = u_top.u_nm.load_amp;
            a_gate[na] = u_top.u_nm.load_gate;
            na = na + 1;
        end
        else if (armed == 2 && u_top.u_nm.load_en && nb < N) begin
            b_en[nb]   = 1; b_slot[nb] = u_top.u_nm.load_slot;
            b_inc[nb]  = u_top.u_nm.load_inc;  b_amp[nb] = u_top.u_nm.load_amp;
            b_gate[nb] = u_top.u_nm.load_gate;
            nb = nb + 1;
        end
    end

    integer guard;

    initial begin
        mismatch = 0; first_bad = -1; na = 0; nb = 0; armed = 0;
        ev_valid = 0; ev_on = 0; ev_note = 0; ev_vel = 0;

        $display("==============================================================");
        $display(" VP6：串行事件(0x60/0x61) vs 排针 ev_* —— 装载序列逐拍比对");
        $display("==============================================================");

        //---------------- 实验 A：排针 ev_* ----------------
        rst_n = 1'b0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (4000) @(posedge clk);
        armed = 1;
        @(posedge clk);
        ev_note <= 7'd64; ev_vel <= 4'd12; ev_on <= 1'b1; ev_valid <= 1'b1;
        @(posedge clk);
        ev_valid <= 1'b0;
        guard = 0;
        while (na < N && guard < 200) begin @(posedge clk); guard = guard + 1; end
        armed = 0;
        $display("  A(排针)   装载事件 %0d 次，首件: slot=%0d inc=%0d amp=%0d gate=%0d",
                 na, a_slot[0], a_inc[0], a_amp[0], a_gate[0]);

        //---------------- 实验 B：UART 0x60/0x61 ----------------
        rst_n = 1'b0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (4000) @(posedge clk);
        armed = 2;                              // ★ 先武装监视器，再发帧
        wr_reg(8'h60, 8'hC0);                  // NOTE_NUM: on + MIDI 64
        wr_reg(8'h61, 8'h0C);                  // NOTE_TRIG: 力度 12 → 触发
        guard = 0;
        while (nb < N && guard < 400) begin @(posedge clk); guard = guard + 1; end
        armed = 0;
        $display("  B(串口)   装载事件 %0d 次，首件: slot=%0d inc=%0d amp=%0d gate=%0d",
                 nb, b_slot[0], b_inc[0], b_amp[0], b_gate[0]);

        //---------------- 比对 ----------------
        for (i = 0; i < N; i = i + 1) begin
            if (a_en[i] != b_en[i] || a_slot[i] != b_slot[i] || a_inc[i] != b_inc[i]
             || a_amp[i] != b_amp[i] || a_gate[i] != b_gate[i]) begin
                mismatch = mismatch + 1;
                if (first_bad < 0) begin
                    first_bad = i;
                    $display("  ✗ 第 %0d 件不同: A(slot=%0d inc=%0d amp=%0d gate=%0d) vs B(slot=%0d inc=%0d amp=%0d gate=%0d)",
                             i, a_slot[i], a_inc[i], a_amp[i], a_gate[i],
                                b_slot[i], b_inc[i], b_amp[i], b_gate[i]);
                end
            end
        end
        $display("  逐件比对 %0d 件：不符 %0d 件", N, mismatch);
        if (mismatch == 0 && na == N && nb == N && a_inc[0] != 0)
            $display("RESULT vp6=PASS events=%0d inc0=%0d slot0=%0d", na, a_inc[0], a_slot[0]);
        else
            $display("RESULT vp6=FAIL mismatch=%0d na=%0d nb=%0d inc0=%0d",
                     mismatch, na, nb, a_inc[0]);
        $finish;
    end

    initial begin
        #200_000_000;
        $display("RESULT vp6=TIMEOUT");
        $finish;
    end

endmodule
