//=============================================================================
// tb_padmon.v —— ⑤ 电极遥测寄存器的判据（第 7 轮）
//
// 目的：证明"上板第一件事"（量 RC 绝对量程）在**不接仿真探针**的情况下也能做 ——
//       即主机能通过 A3 冻结协议从寄存器里把电极的基线/裸计数读出来 ✓✓
//
// 协议（19 号 §5 的 0x64+ 预留区）：
//   0x66 PAD_SEL [3:0] 选通道（主机写）
//   0x64/0x65 PAD_BASE 低/高（只读遥测，12 位）
//   0x67/0x68 PAD_RAW  低/高（只读遥测，12 位）
//   0x69/0x6A PAD_ST   低/高（16 路触摸位图）
// 读法（A3）：写 [0x0F][addr] ⇒ FPGA 回 [addr][value] 两字节
//
// 判据（四条，全部可证伪）：
//   M1 选通道后能**经 UART 回读**拿到数值（不是靠层次探针 ✓）
//   M2 摸该电极 ⇒ PAD_RAW 明显变大，而 PAD_BASE 基本不变
//   M3 松手后 PAD_RAW 回落
//   M4 换 PAD_SEL ⇒ 读到的是**另一根电极**的数（两根电极的裸计数不同 ✓）
//=============================================================================

`timescale 1ns/1ps

module tb_padmon;

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
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    localparam integer DIV = 234;
    integer disch_time [0:NCH-1];
    integer drift;
    genvar gi;

    // 电极 RC 模型：自己产生"充 64 拍 → 按 disch_time 放电"的整条波形
    //   （RTL 也在同一个充电相驱高 ⇒ 两者一致，不冲突 ✓）
    generate
        for (gi = 0; gi < NCH; gi = gi + 1) begin : gpad
            reg     hot;
            integer dcnt;
            initial begin hot = 1'b0; dcnt = 0; end
            always @(posedge clk) begin
                if (u_top.u_pad.dbg_phase == 2'd0) begin
                    hot  <= 1'b1;
                    dcnt <= 0;
                end
                else if (hot && dcnt < disch_time[gi] + drift) dcnt <= dcnt + 1;
                else hot <= 1'b0;
            end
            assign pad_bus[gi] = hot ? 1'b1 : 1'b0;
        end
    endgenerate

    //-------------------------------------------------------------------------
    // UART 发送 + 接收（解析 A3 回读的两字节应答）
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

    // 收一个字节（在 tx 线上等起始位，然后按 234 拍采样）
    task recv_byte(output [7:0] b);
        integer j;
        begin
            @(posedge clk);
            while (uart_tx !== 1'b0) @(posedge clk);   // 等起始位
            repeat (DIV + DIV/2) @(posedge clk);       // 对齐到第 0 位中心
            for (j = 0; j < 8; j = j + 1) begin
                b[j] = uart_tx;
                repeat (DIV) @(posedge clk);
            end
        end
    endtask

    // A3 回读：写 [0x0F][addr] ⇒ 收 [addr][value]
    task rd_reg(input [7:0] addr, output [7:0] val);
        reg [7:0] ra, rv;
        begin
            wr(8'h0F, addr);
            recv_byte(ra);
            recv_byte(rv);
            val = rv;
        end
    endtask

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

    integer i, fails;
    integer b0_lo, b0_hi, r0_lo, r0_hi;
    integer b3_lo, b3_hi, r3_lo, r3_hi;
    reg [7:0] v;

    // 读某通道的 (base, raw)：先写 SEL，等遥测刷新，再经 A3 回读 4 个字节
    task read_ch(input [3:0] ch, output integer base_v, output integer raw_v);
        integer bl, bh, rl, rh;
        reg [7:0] t;
        begin
            wr(8'h66, {4'd0, ch});
            wait_rounds(40);                      // 等遥测节流窗口（4096 拍 ≈ 25 轮）+ 扫描
            rd_reg(8'h64, t); bl = t;
            rd_reg(8'h65, t); bh = t;
            rd_reg(8'h67, t); rl = t;
            rd_reg(8'h68, t); rh = t;
            base_v = bh * 256 + bl;
            raw_v  = rh * 256 + rl;
        end
    endtask

    initial begin
        fails = 0; drift = 0;
        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;
        ev_valid = 0; ev_on = 0; ev_note = 0; ev_vel = 0;

        $display("==============================================================");
        $display(" ⑤ 电极遥测寄存器判据（经 UART 回读，不用层次探针）");
        $display("==============================================================");

        rst_n = 1'b0; repeat (300) @(posedge clk);
        rst_n = 1'b1; repeat (20000) @(posedge clk);   // 等标定完成 + 引导写完

        //---------------- M1 + M2 前置：摸 3 号电极 ----------------
        disch_time[3] = 95;
        read_ch(4'd3, b3_lo, r3_lo);
        $display("  [M1] 经 A3 回读通道 3（已摸）：base=%0d raw=%0d", b3_lo, r3_lo);
        if (b3_lo == 0 && r3_lo == 0) begin
            $display("        => FAIL 回读拿到的全是 0（遥测没生效？）"); fails = fails + 1;
        end
        else $display("        ⇒ UART 回读通路可用 ✓");

        //---------------- M2：摸着的 raw 应该明显大于基线 ----------------
        $display("  [M2] 摸住通道 3：raw=%0d vs base=%0d（应 raw > base × 1.3）", r3_lo, b3_lo);
        if (r3_lo * 10 < b3_lo * 13) begin
            $display("        => FAIL 触摸时裸计数没有明显变大"); fails = fails + 1;
        end
        else $display("        ⇒ 触摸时裸计数明显变大 ✓");

        //---------------- M3：松手后回落 ----------------
        disch_time[3] = 30;
        wait_rounds(40);
        read_ch(4'd3, b3_hi, r3_hi);
        $display("  [M3] 松手后：raw=%0d（应为 %0d 附近，明显小于 %0d）", r3_hi, b3_hi, r3_lo);
        if (r3_hi > (b3_hi + r3_lo) / 2) begin
            $display("        => FAIL 松手后裸计数没回落"); fails = fails + 1;
        end
        else $display("        ⇒ 松手后回落 ✓");

        //---------------- M4：换通道读到不同的数 ----------------
        disch_time[7] = 70;                        // 7 号电极用不同的 RC
        wait_rounds(40);
        read_ch(4'd7, b0_lo, r0_lo);
        $display("  [M4] 换到通道 7（disch=70）：raw=%0d；通道 3（disch=30）：raw=%0d", r0_lo, r3_hi);
        if (r0_lo == r3_hi) begin
            $display("        => FAIL 两个通道读到同一个数 ⇒ SEL 没生效"); fails = fails + 1;
        end
        else $display("        ⇒ PAD_SEL 切换到不同电极、读数不同 ✓");

        //---------------- 附加：位图寄存器也能读 ----------------
        rd_reg(8'h69, v);
        $display("  [附加] PAD_ST_LO = 0x%02X（7 号电极应被点亮：bit7=1）", v);
        if (v[7] !== 1'b1) begin
            $display("        => FAIL 位图里 7 号电极没置位"); fails = fails + 1;
        end
        else $display("        ⇒ 触摸位图寄存器可用 ✓");

        $display("");
        if (fails == 0) $display("RESULT padmon=PASS raw3=%0d base3=%0d raw7=%0d", r3_lo, b3_lo, r0_lo);
        else            $display("RESULT padmon=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #2_000_000_000;
        $display("RESULT padmon=TIMEOUT");
        $finish;
    end

endmodule
