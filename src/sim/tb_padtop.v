//=============================================================================
// tb_padtop.v —— PS4 的【inc 级】判据（pads 经 note_map 真装载）
//
// 21 号 §5-PS4 原文："8 个 pad 逐一触发 → note_map 装载的 inc 与期望音高逐一相等"
//
// 【为什么要在顶层做】
//   tb_pad.v 只验到 pad_scan 发出的【事件层】（note 号对吗）。这一条要验到
//   **note_map 真正装进引擎的 inc**，即整条"触摸 → 事件 → 分配 → 装载"链路。
//
// 【判据不循环】期望值来自 **输入表** `note_inc.hex`（不是 RTL 的公式）；
//   且预设的第 0 泛音比例恰为 256（1.0000×）⇒ 装载的 inc 必须【逐位等于】表值
//
// 【额外交叉验证】同一个音，分别经 **pads** 与经 **排针 ev_*** 送进去，
//   装载的 inc 必须完全一致 （这是"两条路径等价"的机械证明）
//=============================================================================

`timescale 1ns/1ps

module tb_padtop;

    localparam integer NCH = 16;
    localparam integer NTH = 16;

    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;

    wire [NCH-1:0] pad_bus;
    reg        ev_valid, ev_on;
    reg [6:0]  ev_note;
    reg [3:0]  ev_vel;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(1'b1), .uart_tx_pin(),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    // 期望表：五声音阶 pad0..7 = MIDI 60 62 64 67 69 72 74 76
    integer penta [0:7];
    reg [23:0] ni [0:127];                 // note_inc.hex（输入表）
    integer disch_time [0:NCH-1];
    integer drift;

    //-------------------------------------------------------------------------
    // 电极 RC 模型（借用 pad_scan 的 dbg_phase 判"谁在驱动"）
    //-------------------------------------------------------------------------
    genvar gi;
    generate
        for (gi = 0; gi < NCH; gi = gi + 1) begin : gpad
            reg     charged;
            integer dcnt;
            initial begin charged = 1'b0; dcnt = 0; end
            always @(posedge clk) begin
                if (u_top.u_pad.dbg_phase == 2'd0) begin
                    charged <= 1'b1;
                    dcnt    <= 0;
                end
                else if (charged && dcnt < disch_time[gi] + drift) dcnt <= dcnt + 1;
                else charged <= 1'b0;
            end
            assign pad_bus[gi] = (u_top.u_pad.dbg_phase == 2'd0) ? 1'bz
                               : (charged ? 1'b1 : 1'b0);
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 监视器：抓每次装载里【第 0 泛音】的 inc（slot % 16 == 0）
    //-------------------------------------------------------------------------
    integer got_inc;
    integer got_cnt;

    always @(posedge clk) begin
        if (u_top.nm_load_en && (u_top.nm_load_slot % 16 == 0)) begin
            if (got_cnt == 0) got_inc = u_top.nm_load_inc;
            got_cnt = got_cnt + 1;
        end
    end

    integer i, k, fails, exp_inc, pin_inc;
    integer pad_inc [0:7];

    task wait_rounds(input integer n);
        integer j;
        begin
            for (j = 0; j < n; j = j + 1) begin
                @(posedge clk);
                while (u_top.u_pad.dbg_phase != 2'd2) @(posedge clk);
                @(posedge clk);
            end
        end
    endtask

    // 等一次完整的装载序列（16 个时隙）
    task wait_one_load;
        integer guard;
        begin
            got_cnt = 0; got_inc = -1;
            guard = 0;
            while (got_cnt < 16 && guard < 2000) begin @(posedge clk); guard = guard + 1; end
        end
    endtask

    initial begin
        penta[0]=60; penta[1]=62; penta[2]=64; penta[3]=67;
        penta[4]=69; penta[5]=72; penta[6]=74; penta[7]=76;
        $readmemh("note_inc.hex", ni);
        fails = 0; drift = 0;
        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;
        ev_valid = 0; ev_on = 0; ev_note = 0; ev_vel = 0;

        $display("==============================================================");
        $display(" PS4（inc 级）：pads 经 note_map 真装载，与输入表 note_inc.hex 比对");
        $display("==============================================================");

        rst_n = 1'b0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        wait_rounds(40);                   // 让基线标定完成

        //---------------- pads 路径：8 键逐一 ----------------
        for (i = 0; i < 8; i = i + 1) begin
            disch_time[i] = 95;            // 按下
            wait_one_load();               // 抓到 note-on 的装载
            pad_inc[i] = got_inc;
            exp_inc    = ni[penta[i]];
            $display("  pad%0d 按下：装载 inc = %0d，输入表 note_inc[%0d] = %0d  %s",
                     i, pad_inc[i], penta[i], exp_inc,
                     (pad_inc[i] == exp_inc) ? "✓" : "✗");
            if (pad_inc[i] != exp_inc) fails = fails + 1;
            disch_time[i] = 30;            // 松开
            wait_one_load();
            wait_rounds(4);
        end

        // 单调性（五声音阶的自然顺序 ⇒ 装载 inc 必须严格递增）
        for (i = 1; i < 8; i = i + 1)
            if (pad_inc[i] <= pad_inc[i-1]) begin
                $display("  ✗ 单调性破坏：pad%0d(%0d) <= pad%0d(%0d)",
                         i, pad_inc[i], i-1, pad_inc[i-1]);
                fails = fails + 1;
            end
        if (fails == 0) $display("  ⇒ 8 键装载 inc 与输入表逐一相等、且严格递增 ✓");

        //---------------- 交叉验证：排针路径同一个音 ----------------
        wait_rounds(8);
        @(posedge clk);
        ev_note <= 7'd60; ev_vel <= 4'd12; ev_on <= 1'b1; ev_valid <= 1'b1;
        @(posedge clk);
        ev_valid <= 1'b0;
        wait_one_load();
        pin_inc = got_inc;
        $display("  交叉验证：排针送 MIDI 60 ⇒ 装载 inc = %0d；pad0 ⇒ %0d  %s",
                 pin_inc, pad_inc[0], (pin_inc == pad_inc[0]) ? "✓ 等价" : "✗ 不等");
        if (pin_inc != pad_inc[0]) fails = fails + 1;

        $display("");
        if (fails == 0) $display("RESULT ps4inc=PASS pads=8 cross=1");
        else            $display("RESULT ps4inc=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #600_000_000;
        $display("RESULT ps4inc=TIMEOUT");
        $finish;
    end

endmodule
