//=============================================================================
// tb_show.v —— 交互层音频演示（把"模拟什么输入"渲染成"听到什么音频"）
//
// 三个场景，各自由 +show=N 选择，各自 dump 一个文件（再由 render_wav.py 出 48 kHz WAV）：
//
//   +show=0  左手音高键弹旋律
//            输入：**模拟手指依次触摸 pad0..pad7**（RC 模型的放电时间被拉长）
//            输出：五声音阶旋律（C4 D4 E4 G4 A4 C5 D5 E5…）
//
//   +show=1  右手泛音键塑谱（**在响变形**，替换模式）
//            输入：先按住 pad0（C4）+ 立刻摸右手第 1 根泛音键（只响基音）
//                  → 之后每 0.35 s 多摸一根（叠加更多泛音）
//            输出：一个持续音，音色从"纯基音"逐步变成"全泛音"
//
//   +show=2  替换 vs 叠加 的 A/B 对比（同一只手势、同一个音）
//            输入：同样的音 + 同样的右手掩码，先"叠加"再"替换"
//            输出：第一段 = 预设底谱 + 加强；第二段 = 只有被摸到的泛音
//
// 所有输入都是**电极的 RC 放电时间**（与真实手指等价：手指 ⇒ 电容变大 ⇒ 放电变慢）
//   —— 不是直接灌音符事件，所以这条链路与上板一致
//=============================================================================

`timescale 1ns/1ps

module tb_show;

    localparam integer NCH = 16;
    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;

    wire [NCH-1:0] pad_bus;
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
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    localparam integer DIV = 234;
    integer disch_time [0:NCH-1];
    integer drift;
    integer which;
    integer fout, ns;

    //-------------------------------------------------------------------------
    // 电极 RC 模型（与 tb_padtop 同一套：用 pad_scan 的 dbg_phase 判"谁在驱动"）
    //   手指按下 ⇒ 放电时间 30 → 95 拍
    //-------------------------------------------------------------------------
    genvar gi;
    generate
        for (gi = 0; gi < NCH; gi = gi + 1) begin : gpad
            reg     charged;
            integer dcnt;
            initial begin charged = 1'b0; dcnt = 0; end
            always @(posedge clk) begin
                if (u_top.u_pad.dbg_phase == 2'd0) begin
                    charged <= 1'b1; dcnt <= 0;
                end
                else if (charged && dcnt < disch_time[gi] + drift) dcnt <= dcnt + 1;
                else charged <= 1'b0;
            end
            assign pad_bus[gi] = (u_top.u_pad.dbg_phase == 2'd0) ? 1'bz
                               : (charged ? 1'b1 : 1'b0);
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 串口写寄存器（用于切塑谱模式）
    //-------------------------------------------------------------------------
    task send_byte(input [7:0] b);
        integer j;
        begin
            uart_rx = 1'b0; repeat (DIV) @(posedge clk);
            for (j = 0; j < 8; j = j + 1) begin uart_rx = b[j]; repeat (DIV) @(posedge clk); end
            uart_rx = 1'b1; repeat (DIV) @(posedge clk);
        end
    endtask
    task wr(input [7:0] a, input [7:0] d); begin send_byte(a); send_byte(d); end endtask

    task set_mode(input [7:0] m); begin wr(8'h5A, m); end endtask

    // 录制 n 个样本
    task rec(input integer n);
        integer q;
        begin
            for (q = 0; q < n; q = q + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
                $fdisplay(fout, "%0d %0d", ns, $signed(u_top.audio));
                ns = ns + 1;
            end
        end
    endtask

    // 触摸/松开某根电极（手指模型：放电时间 30 ↔ 95 拍）
    task tch(input integer p, input integer on);
        begin
            if (on) disch_time[p] = 95;
            else    disch_time[p] = 30;
        end
    endtask

    integer i;

    initial begin
        if (!$value$plusargs("show=%d", which)) which = 0;
        drift = 0; ns = 0;
        ev_valid = 0; ev_on = 0; ev_note = 0; ev_vel = 0;
        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;

        rst_n = 1'b0; repeat (200) @(posedge clk);
        rst_n = 1'b1; repeat (20000) @(posedge clk);   // 等基线标定 + 引导写完

        if (which == 0) begin
            //===========================================================
            // 场景 0：左手音高键弹旋律（C D E G A C5 D5 E5 上行 + 回落）
            //===========================================================
            fout = $fopen("show_pads.txt", "w");
            $display("[show=0] 输入=依次触摸 pad0..pad7（电极放电变慢）→ 输出=五声音阶旋律");
            for (i = 0; i < 8; i = i + 1) begin
                tch(i, 1);  rec(12000);          // ≈0.23 s
                tch(i, 0);  rec(1500);
            end
            for (i = 6; i >= 0; i = i - 1) begin
                tch(i, 1);  rec(12000);
                tch(i, 0);  rec(1500);
            end
            $fclose(fout);
        end
        else if (which == 1) begin
            //===========================================================
            // 场景 1：右手泛音键塑谱（替换模式 ⇒ 只响被摸到的泛音）
            //===========================================================
            fout = $fopen("show_spec.txt", "w");
            set_mode(8'h03);                     // bit0=1 替换 + bit1=1 自动刷新
            repeat (4000) @(posedge clk);
            $display("[show=1] 输入=按住 pad0(C4) + 逐根摸右手泛音键 → 输出=纯基音逐步长成全泛音");
            tch(0, 1);                           // 左手按住 C4
            tch(8, 1);                           // 右手第 1 根 ⇒ 只有基音
            rec(20000);
            tch(9, 1);  rec(18000);              // +第 2 泛音
            tch(10, 1); rec(18000);              // +第 3
            tch(11, 1); rec(18000);              // +第 4
            tch(12, 1); rec(18000);              // +第 5
            tch(13, 1); rec(18000);              // +第 6
            tch(15, 1); rec(18000);              // +第 8
            tch(8, 0); tch(9, 0); tch(10, 0); tch(11, 0);
            tch(12, 0); tch(13, 0); tch(15, 0);
            rec(18000);                          // 只剩被摸着的最后一个（已松）⇒ 静音
            tch(0, 0);  rec(6000);
            $fclose(fout);
        end
        else begin
            //===========================================================
            // 场景 2：替换 vs 叠加 A/B
            //===========================================================
            fout = $fopen("show_ab.txt", "w");
            $display("[show=2] 输入=同一个音+同一组右手掩码，先叠加后替换 → 输出=两段音色对比");
            // ——— 第一段：叠加（预设底谱 + 加强）———
            set_mode(8'h02); repeat (4000) @(posedge clk);
            tch(0, 1); tch(8, 1); tch(9, 1); tch(11, 1);
            rec(48000);                          // ≈0.9 s
            tch(0, 0); tch(8, 0); tch(9, 0); tch(11, 0);
            rec(8000);
            // ——— 第二段：替换（只有被摸到的泛音）———
            set_mode(8'h03); repeat (4000) @(posedge clk);
            tch(0, 1); tch(8, 1); tch(9, 1); tch(11, 1);
            rec(48000);
            tch(0, 0); tch(8, 0); tch(9, 0); tch(11, 0);
            rec(8000);
            $fclose(fout);
        end
        $display("  → dump 完成");
        $finish;
    end

    initial begin
        #5_000_000_000;
        $display("RESULT show=TIMEOUT");
        $finish;
    end

endmodule
