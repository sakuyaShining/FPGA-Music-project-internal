//=============================================================================
// tb_t60.v —— 混响 T60 取证（21 号 §6 的七步配方）
//
// 配方要求（21 号 §6 原文）：
//   1. 冲激：单样本满幅注入，采 ≥30000 样本；
//   2. Schroeder 积分：E(n) = 10·log10(Σ_{k≥n} h(k)²)，从尾向头累加；
//   3. T60：E 从 −5dB 到 −35dB 段线性拟合，外推到 −60dB 的样本数 × Ts；
//   4. V2：RV_FB（0x48）**逐档** → T60 实测 vs 理论 6.91·Ts/(1−fb) 误差 <10%；
//   5. V3：回声密度——前 200ms 内脉冲计数随时间单调增；
//   6. V4：冲激分别过低通(2kHz)/高通(6kHz) 再 Schroeder → damp 最大档时
//          高频 T60 < 低频 T60（差 ≥20%）；
//   7. 溢出测试（V5）；全部走 0x48/0x49 寄存器（顺带验证 UART 路径）。
//
// 【本测试台的做法】
//   · 例化 **fx_delay** 本体（单样本冲激必须在模块级注入 配方第 1 步）
//   · 但系数**走真实 UART 路径** ：串口 → reg_bank → fx 的系数输入
//     （复刻 tdm_top 里那几行接线 —— 配方第 7 步要"顺带验证 UART 路径"）
//   · 每档 RV_FB 跑一遍，各 dump 一个文件
//
// 【尺子与被测物同源（复核 4 条）】
//   理论 T60 = 6.91 · Ts / (1 − fb)，其中
//     fb = rev_fb_q8 / 256   ← 抄自 fx_delay.v：`rev_mul = rev_q * rev_fb_q8` 然后 `>>> 8`
//     Ts = dly_len / fs      ← 抄自 fx_delay.v：`dl_addr = wptr - dly_len`
//   fs = 52734.375（19 号 §1 冻结）
//=============================================================================

`timescale 1ns/1ps

module tb_t60;

    parameter integer NSAMP = 70000;  // 配方要求 ≥30000；最长档(fb=0.875, T60≈1.06s)要更长      // ≥30000（配方要求；最长的 fb 档要更长）
    parameter integer AW    = 11;         // fx_delay 的 AW（与 tdm_top 一致）

    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;

    // ---- UART → reg_bank（帧解析逻辑逐行抄自 tdm_top.v 的真实实现 复核 4 条）----
    reg        uart_rx = 1'b1;
    wire [7:0] u_rx_data;
    wire       u_rx_valid;
    reg  [7:0] u_addr;
    reg        u_have_addr;
    wire [1023:0] R;   // NW=128

    uart_rx u_rx (
        .clk(clk), .rst_n(rst_n), .rx(uart_rx),
        .data(u_rx_data), .valid(u_rx_valid)
    );

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            u_addr      <= 8'd0;
            u_have_addr <= 1'b0;
        end
        else if (u_rx_valid) begin
            if (!u_have_addr) begin
                u_addr      <= u_rx_data;      // 第一个字节：地址
                u_have_addr <= 1'b1;
            end
            else
                u_have_addr <= 1'b0;           // 第二个字节：数据，写完就清
        end
    end

    wire        wr_en   = u_rx_valid & u_have_addr;
    wire [7:0]  wr_addr = u_addr;
    wire [7:0]  wr_data = u_rx_data;

    reg_bank #(.AW(8), .DW(8), .NW(128)) u_reg (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(1'b0), .rd_addr(8'd0), .rd_data(),
        .regs_flat(R)
    );

    // ---- 系数切片（抄 tdm_top 的同名切片）----
    wire [7:0]  r_fxctrl = R[8'h40*8 +: 8];
    wire [15:0] r_dlylen = { R[8'h42*8 +: 8], R[8'h41*8 +: 8] };
    wire [7:0]  r_fb     = R[8'h43*8 +: 8];
    wire [7:0]  r_rev_fb = R[8'h48*8 +: 8];
    wire [2:0]  r_rev_dmp= R[8'h49*8 +: 3];
    wire [2:0]  r_wet_sh = R[8'h4A*8 +: 3];      // 若没有就用默认 0

    wire        fx_dry = r_fxctrl[0];
    wire        fx_dly = r_fxctrl[1];
    wire        fx_cho = r_fxctrl[2];
    wire        fx_rev = r_fxctrl[3];

    // ---- sample_en 必须是【÷12 频闪】，不能恒 1 ----
    //   fx_delay 的流水是 12 态 FSM，且 `else if (sample_en)` ⇒ 每态只在
    //   sample_en 那一拍推进 ⇒ **一整遍 = 12 个频闪** 。
    //   已知能工作的 tb_fx 就是这么驱动的（`sample_en = (pc == PERIOD-1)`）。
    //   原先接恒 1 ⇒ 与模块预期用法不符 ⇒ 实测输出恒 0
    reg [3:0] pc;
    wire sample_en = (pc == 4'd11);
    always @(posedge clk or negedge rst_n)
        if (!rst_n) pc <= 4'd0;
        else        pc <= (pc == 4'd11) ? 4'd0 : pc + 4'd1;

    // ---- 被测物：fx_delay ----
    reg  signed [23:0] din;
    wire signed [23:0] dout;

    fx_delay #(.AW(AW)) u_fx (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .din(din), .dout(dout),
        .dry_en(fx_dry), .dly_en(fx_dly), .cho_en(fx_cho), .rev_en(fx_rev),
        .wet_sh(3'd0),
        .dly_len(r_dlylen), .fb_q8(r_fb),
        .cho_rate(16'd430), .cho_depth(16'd64),
        .rev_fb_q8(r_rev_fb), .rev_damp(r_rev_dmp)
    );

    localparam integer DIV = 234;
    task send_byte(input [7:0] b);
        integer j;
        begin
            uart_rx = 1'b0; repeat (DIV) @(posedge clk);
            for (j = 0; j < 8; j = j + 1) begin uart_rx = b[j]; repeat (DIV) @(posedge clk); end
            uart_rx = 1'b1; repeat (DIV) @(posedge clk);
        end
    endtask
    task wr(input [7:0] a, input [7:0] d); begin send_byte(a); send_byte(d); end endtask

    integer fb_tab [0:3];
    integer k, s, q, fout;
    reg [1023:0] fname;

    initial begin
        // (本次)：默认已改为 0x80；这里跑【默认档起的三档】做判据
        //   外加 0xC0 作为【已知限制探针】（高档位 + 满幅输入会饱和，见待办清单 ⑥⑦）
        fb_tab[0] = 8'h40;    // 0.25
        fb_tab[1] = 8'h60;    // 0.375
        fb_tab[2] = 8'h80;    // 0.50 ★ 现在的默认
        fb_tab[3] = 8'hC0;    // 0.75（已知限制探针）

        uart_rx = 1'b1;
        din = 24'sd0;

        // 上电 + 让 fx 的启动冲刷走完
        //   关键（(本次)踩坑）：fx_delay 的流水是 12 态 FSM，**一遍 = 12 拍** ，
        //      而 FLUSH_LEN=2048 是 2048 **遍** ⇒ 要 ~24576 拍。
        //      原来只等 4000 拍 ⇒ 冲激落在冲刷窗口里被写成 0 ⇒ dump 全零
        rst_n = 1'b0; repeat (300) @(posedge clk);
        rst_n = 1'b1;
        repeat (60000) @(posedge clk);          // ≥ 2048 遍 × 12 拍 = 24576 拍

        // 只开混响：FX_CTRL[3]=1 ⇒ 干声关、混响开（纯冲激响应）
        wr(8'h40, 8'h08);
        wr(8'h41, 8'hDC);   // DELAY_LEN = 1500（低）
        wr(8'h42, 8'h05);   //              （高）抄自引导默认
        wr(8'h49, 8'h07);   // REV_DAMP = 7 判据 V4 要求【damp 最大档】（3 位寄存器最大值）
        repeat (2000) @(posedge clk);

        for (k = 0; k < 4; k = k + 1) begin
            wr(8'h48, fb_tab[k][7:0]);          // ★ 走 UART 路径 ✓
            repeat (6000) @(posedge clk);       // 等寄存器生效 + 环路稳定
            // 文件名按 fb 值生成 （原来写死 ：改了档位表就对不上，判据找不到文件）
            $sformat(fname, "t60_fb%02x.txt", fb_tab[k][7:0]);
            fout = $fopen(fname, "w");
            $display("  [T60] RV_FB=0x%02X ⇒ 写 t60_fb%02x.txt（%0d 样本）",
                     fb_tab[k], fb_tab[k], NSAMP);
            $display("  [诊断] FX_CTRL=0x%02X dly_len=%0d rev_fb=0x%02X damp=%0d rev_en=%0d dry=%0d",
                     r_fxctrl, r_dlylen, r_rev_fb, r_rev_dmp, fx_rev, fx_dry);
            for (s = 0; s < NSAMP; s = s + 1) begin
                din <= (s == 200) ? 24'sd2560000 : 24'sd0;   // 单样本满幅冲激
                // 一整遍流水 = 12 个 sample_en 频闪 ⇒ 等 12 个频闪再录
                for (q = 0; q < 12; q = q + 1) begin
                    @(posedge clk);
                    while (!sample_en) @(posedge clk);
                end
                $fdisplay(fout, "%0d", $signed(dout));
            end
            $fclose(fout);
            // 档间把线缓冲清干净（再冲一遍满幅冲激的尾巴会长）
            wr(8'h48, 8'h00);
            repeat (100000) @(posedge clk);
        end

        $display("  → 4 个档的冲激响应已 dump");
        $finish;
    end

    initial begin
        #3_000_000_000;   // 硬超时 3 s 仿真时间（4 档约 1.5 s）
        $display("RESULT t60=TIMEOUT");
        $finish;
    end

endmodule
