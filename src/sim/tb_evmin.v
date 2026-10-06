//=============================================================================
// tb_evmin.v —— 【最小复现】单源 3 条事件，逐步打印
//
// 【为什么单独做这一版】
//   前两轮用 28 条混合激励（排针 + UART + 两源同拍）去调事件通路，
//   每次失败信息都混杂，反复回退。教训是：**先把单源三条钉死，再引入第二个源。**
//
// 【本轮要回答的唯一问题】
//   三个字段（note / on / vel）在单源下是否**同时**正确？
//   上一轮的观测是同一条事件里 vel 对而 note 恒为 0 ——
//   若单源下三字段全对，说明问题出在"多源并存时的 mh_note 优先级链"；
//   若单源下 note 仍为 0，说明问题在锁存或队列的 note 通路本身。
//
// 【打印内容】事件被锁存的那一拍与出队的那一拍，逐拍可见：
//   dh_pend / mh_valid / mh_note / mh_on / ev_in_ready / ev_q_valid / ev_q_note
//=============================================================================
`timescale 1ns/1ps

module tb_evmin;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    wire [15:0] pad_bus;
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
    integer r_note [0:15];
    integer r_on   [0:15];
    integer r_vel  [0:15];
    reg     vq;

    //   按上升沿抓事件（valid 可能是电平，见 tb_evmerge 的注释）
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin nr <= 0; vq <= 1'b0; end
        else begin
            vq <= u_top.ev_valid_r;
            if (u_top.ev_valid_r && !vq && nr < 16) begin
                r_note[nr] <= u_top.ev_note_r;
                r_on[nr]   <= u_top.ev_on_r;
                r_vel[nr]  <= u_top.ev_vel_r;
                nr         <= nr + 1;
            end
        end
    end

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

    initial begin
        $display("==============================================================");
        $display(" 最小复现：单源（排针）3 条事件，逐拍打印");
        $display("==============================================================");

        ev_valid = 1'b0; ev_on = 1'b0; ev_note = 7'd0; ev_vel = 4'd0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (2000) @(posedge clk);

        //--------------------------------------------------------------- 事件 1
        $display(" --- 事件1：note=61 on=0 vel=2 ---");
        ev_note = 7'd61; ev_on = 1'b0; ev_vel = 4'd2; ev_valid = 1'b1;
        for (i = 0; i < 6; i = i + 1) begin
            $display("   [t%0d] dh_pend=%b mh_valid=%b mh_note=%0d mh_on=%b mh_vel=%0d in_ready=%b q_valid=%b q_note=%0d q_on=%b q_vel=%0d ack=%b level=%0d ovf=%0d",
                     i, u_top.dh_pend, u_top.mh_valid, u_top.mh_note, u_top.mh_on, u_top.mh_vel,
                     u_top.ev_in_ready, u_top.ev_q_valid, u_top.ev_q_note, u_top.ev_q_on,
                     u_top.ev_q_vel, u_top.nm_ev_ack, u_top.ev_q_level, u_top.ev_q_ovf);
            @(posedge clk);
        end
        ev_valid = 1'b0;
        repeat (200) @(posedge clk);
        $display("   [静置] dh_pend=%b q_valid=%b level=%0d ovf=%0d 收到=%0d",
                 u_top.dh_pend, u_top.ev_q_valid, u_top.ev_q_level, u_top.ev_q_ovf, nr);
        for (i = 0; i < nr; i = i + 1)
            $display("     #%0d note=%0d on=%0d vel=%0d", i, r_note[i], r_on[i], r_vel[i]);

        //--------------------------------------------------------------- 事件 2
        $display(" --- 事件2：note=62 on=1 vel=3 ---");
        pin_ev(7'd62, 1'b1, 4'd3);
        repeat (200) @(posedge clk);
        $display("   [静置] 收到=%0d", nr);
        for (i = 0; i < nr; i = i + 1)
            $display("     #%0d note=%0d on=%0d vel=%0d", i, r_note[i], r_on[i], r_vel[i]);

        //--------------------------------------------------------------- 事件 3
        $display(" --- 事件3：note=63 on=0 vel=4 ---");
        pin_ev(7'd63, 1'b0, 4'd4);
        repeat (200) @(posedge clk);
        $display("   [静置] 收到=%0d", nr);
        for (i = 0; i < nr; i = i + 1)
            $display("     #%0d note=%0d on=%0d vel=%0d", i, r_note[i], r_on[i], r_vel[i]);

        if (nr == 3 && r_note[0] == 61 && r_note[1] == 62 && r_note[2] == 63 &&
            r_on[0] == 0 && r_on[1] == 1 && r_on[2] == 0 &&
            r_vel[0] == 2 && r_vel[1] == 3 && r_vel[2] == 4)
            $display("RESULT evmin=PASS");
        else
            $display("RESULT evmin=FAIL nr=%0d", nr);
        $finish;
    end

    initial begin
        #50_000_000;
        $display("RESULT evmin=TIMEOUT nr=%0d", nr);
        $finish;
    end

endmodule
