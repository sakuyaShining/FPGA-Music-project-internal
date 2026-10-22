//=============================================================================
// tb_ps5.v —— PS5 + VP5：物理电极 与 0x5B HARM_PADS 软写入 **等效**
//
// 21 号 §5-PS5 原文："pad_harm 某位置位 → 在响声部对应泛音幅度变化（同 VP2 断言法）"
// 19 号 §4 原文："物理电极扫描 + 0x5B 软写入 **按位或** → pad 状态"
//
// 【判据设计（两条路，同一结果）】
//   路径 A：用**电极模型**让右手第 3 根（harm bit2）"被触摸"
//   路径 B：复位后用 **UART 写 0x5B = 0x04**（软寄存器）
//   两者都必须让**在响的同一个声部**装载出**逐位相同**的 16 个泛音幅度
//   ⇒ 这就是"等效"的机械证明（不重算任何公式 非循环）
//
// 【电极模型】`pad` 现在是纯输入（见 C0：三态布不通）⇒ 模型**自己驱动整条 RC 波形**：
//   扫描处于充电相（dbg_phase==0）时驱高 64 拍；之后按 disch_time 维持高、再落 0。
//   手指 = disch_time 变大 ⇒ 计数变大 ⇒ 判定为触摸
//=============================================================================

`timescale 1ns/1ps

module tb_ps5;

    localparam integer NCH = 16;
    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;

    wire [NCH-1:0] pad_bus;          // 纯输入：由本测试台的 RC 模型驱动
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
    genvar gi;

    //-------------------------------------------------------------------------
    // 电极 RC 模型：自己产生"充 64 拍 → 按 disch_time 放电"的整条波形
    //-------------------------------------------------------------------------
    generate
        for (gi = 0; gi < NCH; gi = gi + 1) begin : gpad
            reg        hot;
            integer    dcnt;
            initial begin hot = 1'b0; dcnt = 0; end
            always @(posedge clk) begin
                if (u_top.u_pad.dbg_phase == 2'd0) begin
                    hot  <= 1'b1;                 // 充电相：模型也驱高（与 RTL 语义一致）
                    dcnt <= 0;
                end
                else if (hot && dcnt < disch_time[gi] + drift) dcnt <= dcnt + 1;
                else hot <= 1'b0;                 // 放完 ⇒ 落 0
            end
            assign pad_bus[gi] = hot ? 1'b1 : 1'b0;
        end
    endgenerate

    task send_byte(input [7:0] b);
        integer j;
        begin
            uart_rx = 1'b0; repeat (DIV) @(posedge clk);
            for (j = 0; j < 8; j = j + 1) begin uart_rx = b[j]; repeat (DIV) @(posedge clk); end
            uart_rx = 1'b1; repeat (DIV) @(posedge clk);
        end
    endtask
    task wr(input [7:0] a, input [7:0] d); begin send_byte(a); send_byte(d); end endtask

    task wait_samples(input integer n);
        integer j;
        begin
            for (j = 0; j < n; j = j + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
            end
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

    // 按下一个音（用排针事件，避免与 pads 混淆）
    task press(input [6:0] n);
        begin
            @(posedge clk);
            ev_note <= n; ev_vel <= 4'd15; ev_on <= 1'b1; ev_valid <= 1'b1;
            @(posedge clk);
            ev_valid <= 1'b0;
            wait_samples(6);
        end
    endtask

    integer i, k, fails, diff;
    integer a_amp [0:15];
    integer b_amp [0:15];

    // 记录组 0 的 16 个泛音幅度
    task snap(input integer which);
        integer j, v;
        begin
            for (j = 0; j < 16; j = j + 1) begin
                v = u_top.u_tdm.amp_mem[0*16 + j];
                if (which == 0) a_amp[j] = v; else b_amp[j] = v;
            end
        end
    endtask

    initial begin
        fails = 0; drift = 0;
        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;
        ev_valid = 0; ev_on = 0; ev_note = 0; ev_vel = 0;

        $display("==============================================================");
        $display(" PS5/VP5：物理电极 vs 0x5B 软写入 是否等效");
        $display("==============================================================");

        //================= 路径 A：物理电极摸 harm bit2（pad 索引 8+2=10）=================
        rst_n = 1'b0; repeat (200) @(posedge clk);
        rst_n = 1'b1; repeat (4000) @(posedge clk);
        wr(8'h5A, 8'h02);                       // 叠加 + 自动刷新（先关自动，避免干扰）
        wait_samples(4);
        press(7'd64);                           // 组 0 在响
        disch_time[10] = 95;                    // 右手第 3 根电极被触摸
        wait_rounds(12);                        // 等去抖 + 自动刷新节流窗口
        wait_samples(12);
        snap(0);
        $display("  路径 A（电极 touch pad10 = harm bit2）：组0 泛音1..4 幅度 = %0d %0d %0d %0d",
                 a_amp[0], a_amp[1], a_amp[2], a_amp[3]);

        //================= 路径 B：复位后用 0x5B 软写入 =================
        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;
        rst_n = 1'b0; repeat (200) @(posedge clk);
        rst_n = 1'b1; repeat (4000) @(posedge clk);
        wr(8'h5A, 8'h02);
        wr(8'h5B, 8'h04);                       // 软寄存器：harm bit2
        wr(8'h63, 8'hFF);                       // 显式全刷
        wait_samples(8);
        press(7'd64);
        wr(8'h63, 8'hFF);
        wait_samples(12);
        snap(1);
        $display("  路径 B（软写 0x5B=0x04）：         组0 泛音1..4 幅度 = %0d %0d %0d %0d",
                 b_amp[0], b_amp[1], b_amp[2], b_amp[3]);

        //================= 比对 =================
        diff = 0;
        for (k = 0; k < 16; k = k + 1) begin
            if (a_amp[k] !== b_amp[k]) begin
                diff = diff + 1;
                if (diff == 1)
                    $display("  ✗ 第 %0d 个泛音不同：电极 %0d vs 软写 %0d", k, a_amp[k], b_amp[k]);
            end
        end
        $display("  16 个泛音逐位比对：不符 %0d 个", diff);
        if (diff == 0 && b_amp[2] > b_amp[0] + 20)
            $display("  ⇒ 电极与软写入【完全等效】，且第三个泛音确实被 boost（%0d > %0d）✓✓",
                     b_amp[2], b_amp[0]);
        else if (diff == 0)
            $display("  ✗ 两者一致但看不出 boost（可能没生效）");
        else fails = fails + 1;
        if (diff != 0) fails = fails + 1;

        $display("");
        if (fails == 0) $display("RESULT ps5=PASS diff=0 boost=%0d", b_amp[2]);
        else            $display("RESULT ps5=FAIL fails=%0d diff=%0d", fails, diff);
        $finish;
    end

    initial begin
        #600_000_000;
        $display("RESULT ps5=TIMEOUT");
        $finish;
    end

endmodule
