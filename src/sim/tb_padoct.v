//=============================================================================
// tb_padoct.v —— 【快判据】pad 路径是否产生"亚八度"分量
//
// 【为什么单独做这一条（2026-10-07）】
//   深查 `tb_show +show=0` 的音频时发现：期望音高（C4/G4/C5）**确实在音频里**，
//   但全谱最强峰是 **128.75 Hz**，恰为 C4 峰（257.49 Hz）的 **1/2**（误差 0.00%）
//   ⇒ 存在一个**精确 2:1 的亚八度分量**，且它**低于整个被触发的音域**
//     （128.75 Hz ↔ MIDI 47.72，而触发范围是 MIDI 60–76）。
//
//   但 `tb_show` 单次运行需 **5590 秒（93 分钟）**，无法用来迭代排查。
//   本判据把问题**隔离到最小**：只按 **pad0 一个键**，录一段音频，供 Python 做谱分析。
//   预期运行时间：秒级（几万样本）。
//
// 【判据（在 padoct_check.py 里）】
//   O1 期望基频（pad0 → C4 = 261.63 Hz）必须存在且足够强
//   O2 若存在 ~130.75 Hz（C4/2）分量，报告其相对幅度
//      —— 幅度若与基频同量级，说明**不是旁瓣而是真实分量**
//   O3 报告全谱最强峰及其频率，便于判断"谁抢走了 argmax"
//
// 【激励】只按 pad0（电极放电时间 30 → 95，与 tb_show 同款 RC 模型）
//=============================================================================
`timescale 1ns/1ps

module tb_padoct;

    localparam integer NCH = 16;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;          // ≈27 MHz

    reg rst_n = 1'b0;
    wire [NCH-1:0] pad_bus;
    reg            uart_rx = 1'b1;
    wire           uart_tx;
    reg            ev_valid = 1'b0, ev_on = 1'b0;
    reg [6:0]      ev_note = 7'd0;
    reg [3:0]      ev_vel  = 4'd0;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    //-------------------------------------------------------------------------
    // 电极 RC 模型（与 tb_show / tb_padtop 同款）
    //   按下 ⇒ 放电时间 95 拍；松开 ⇒ 30 拍
    //-------------------------------------------------------------------------
    integer disch_time [0:NCH-1];
    integer drift = 0;
    integer i;
    integer fout, ns;

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

    //   录制 n 个样本到 out.txt（格式与 show_pads.txt 一致：序号 + 音频）
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

    initial begin
        $display("==============================================================");
        $display(" pad 路径 亚八度分量 快判据（只按 pad0）");
        $display("==============================================================");

        for (i = 0; i < NCH; i = i + 1) disch_time[i] = 30;   // 全部松开
        ns = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (5000) @(posedge clk);        // 等自举序列与 pad_scan 稳定

        fout = $fopen("padoct.txt", "w");
        if (fout == 0) begin $display("无法创建 padoct.txt"); $finish; end

        //   ---- 段1：全松开，录 4000 样本（基线）
        $display(" [1] 全松开基线：录 4000 样本");
        rec(2000);

        //   ---- 段2：只按 pad0（C4），录 20000 样本（≈0.38 s）
        $display(" [2] 只按 pad0（期望 C4=261.63 Hz）：录 20000 样本");
        disch_time[0] = 95;
        repeat (2000) @(posedge clk);        // 等 pad_scan 识别 + 事件 + 装载
        rec(20000);

        //   ---- 段3：松开 pad0
        $display(" [3] 松开 pad0");
        disch_time[0] = 30;
        repeat (4000) @(posedge clk);
        rec(4000);

        $fclose(fout);
        $display(" 已写 padoct.txt（共 %0d 样本）", ns);
        $display("==============================================================");
        $display("RESULT padoct=DONE ns=%0d", ns);
        $finish;
    end

    initial begin
        #800_000_000;
        $display("RESULT padoct=TIMEOUT ns=%0d", ns);
        $finish;
    end

endmodule

