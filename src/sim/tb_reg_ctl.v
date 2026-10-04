//=============================================================================
// tb_reg_ctl.v —— 运行时参数通道验收（拓展 E2 + E3）
//
// 【它测什么】
//   经【UART 写寄存器】改变演奏参数，再量输出是否随之改变：
//     test=0  E3 音色切换：写 PRESET → 该音各泛音幅度随预设表改变
//     test=1  E2 颤音：写 VIB_DEPTH（三档）→ 量频偏（音分）
//     test=2  E2 滑音：写 GLIDE_M_K=(m=3,k=13) → 量衰减时间常数
//     test=3  E2 滑音：写 GLIDE_M_K=(m=3,k=10) → 与 test=2 相差 8 倍
//
// 【为什么每个 test 一次冷启动（+test=N）】
//   引擎的时隙状态（BSRAM）没有复位分支 —— 这是设计的自觉选择
//   （"BSRAM 上电本来就是 0"）。在仿真中途拉复位不会让上一音消失，
//   所以"首次非零""某组装载生效"这类判据根本无法定义。
//   在 tb_latency 里已经栽过一次，这里直接按冷启动设计。
//
// 【UART 协议】115200 8N1，两字节一帧：先地址、后数据
//   位周期 = 27e6 / 115200 = 234 拍（接收器内部 DIV 也是 234）
//
// 【运行目录需要】sine256.hex / note_inc.hex / preset_part.hex / recip_inc.hex
//                且必须是 --fs 46875 生成的那份
//=============================================================================

`timescale 1ns/1ps

module tb_reg_ctl;

    localparam real CLK_HALF = 18.5185;   // 37.037 ns -> 27 MHz
    localparam integer DIV    = 234;      // UART 位周期
    localparam integer P      = 16;

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    reg        ev_valid = 1'b0;
    reg        ev_on    = 1'b0;
    reg [6:0]  ev_note  = 7'd0;
    reg [3:0]  ev_vel   = 4'd8;           // 8 → 内部 128
    reg [1:0]  preset_pin = 2'd0;
    reg        test_mode_pin = 1'b0;
    reg        uart_line = 1'b1;          // 串口空闲为高

    wire [5:0] led;
    wire       dac_din, dac_ws, dac_bck, pa_en;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note),
        .ev_vel(ev_vel), .preset(preset_pin), .test_mode(test_mode_pin),
        .uart_rx_pin(uart_line),
        .led(led), .dac_din(dac_din), .dac_ws(dac_ws), .dac_bck(dac_bck), .pa_en(pa_en)
    );

    //-------------------------------------------------------------------------
    // UART 发送（LSB first：起始位 → 8 数据位 → 停止位）
    //-------------------------------------------------------------------------
    task send_byte(input [7:0] b);
        integer k;
        begin
            uart_line = 1'b0;                    // 起始位
            repeat (DIV) @(posedge clk);
            for (k = 0; k < 8; k = k + 1) begin
                uart_line = b[k];                // LSB first
                repeat (DIV) @(posedge clk);
            end
            uart_line = 1'b1;                    // 停止位
            repeat (DIV) @(posedge clk);
        end
    endtask

    task wr_reg(input [7:0] addr, input [7:0] data);
        begin
            send_byte(addr);
            send_byte(data);
            repeat (20) @(posedge clk);
        end
    endtask

    task note_on(input [6:0] n);
        begin
            @(posedge clk);
            ev_note  <= n;
            ev_valid <= 1'b1;
            ev_on    <= 1'b1;
            @(posedge clk);
            ev_valid <= 1'b0;
        end
    endtask

    // 等 n 个样本周期
    task wait_samples(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
            end
        end
    endtask

    //-------------------------------------------------------------------------
    // 观测：相位（算瞬时 inc）与幅度
    //-------------------------------------------------------------------------
    integer fout, ns, ci;

    reg [2:0] which;      // 0=preset 1=vib 2=glide13 3=glide10
    integer seg;

    initial begin
        if (!$value$plusargs("test=%d", which)) which = 3'd0;
    end

    //-------------------------------------------------------------------------
    // 主流程
    //-------------------------------------------------------------------------
    integer g, k2;
    integer DURS [0:2];
    integer DEPTHS [0:2];

    initial begin
        DURS[0] = 2600; DURS[1] = 2600; DURS[2] = 2600;
        DEPTHS[0] = 0;  DEPTHS[1] = 1000; DEPTHS[2] = 2000;

        rst_n = 1'b0;
        repeat (40) @(posedge clk);
        rst_n = 1'b1;

        // 等开机自举把 8 个寄存器写完
        repeat (400) @(posedge clk);

        $display("==============================================================");
        $display(" 运行时参数通道验收（test=%0d）", which);
        $display("==============================================================");
        $display("  自举后寄存器：CTRL=%02X VIB_INC=%02X%02X%02X VIB_DEPTH=%02X%02X GMK=%02X PRESET=%02X",
                 u_top.R[8'h00*8 +: 8],
                 u_top.R[8'h32*8 +: 8], u_top.R[8'h31*8 +: 8], u_top.R[8'h30*8 +: 8],
                 u_top.R[8'h34*8 +: 8], u_top.R[8'h33*8 +: 8],
                 u_top.R[8'h35*8 +: 8], u_top.R[8'h37*8 +: 8]);

        if (which == 3'd0) begin
            //---------------------------------------------------------------
            // E3：音色切换（寄存器选音色）
            //---------------------------------------------------------------
            wr_reg(8'h00, 8'h0C);       // CTRL: 滑音开 + 音色源=寄存器
            fout = $fopen("rc_preset.txt", "w");
            for (g = 0; g < 4; g = g + 1) begin
                wr_reg(8'h37, g[7:0]);  // PRESET = g
                note_on(40 + g);        // 第 g 个音落在 g 号组（顺序分配）
                // 等这个音装载生效（跨过一个样本边界即可）
                wait_samples(4);
                // 该组 16 个泛音的幅度
                for (k2 = 0; k2 < P; k2 = k2 + 1)
                    $fwrite(fout, "%0d ", u_top.u_tdm.amp_mem[g * P + k2]);
                $fwrite(fout, "\n");
                $display("    预设 %0d 已装载：组 %0d 的 16 个泛音幅度已记录", g, g);
                wait_samples(20);
            end
            $fclose(fout);
            $display("  → rc_preset.txt");
        end
        else if (which == 3'd1) begin
            //---------------------------------------------------------------
            // E2：颤音深度（运行时写三档）
            //---------------------------------------------------------------
            wr_reg(8'h00, 8'h06);       // CTRL: 滑音开 + 颤音开
            wr_reg(8'h30, 8'h1C);       // VIB_INC = 17180 = 0x431C → LE: 1C,43,00
            wr_reg(8'h31, 8'h43);
            wr_reg(8'h32, 8'h00);
            note_on(7'd69);
            wait_samples(50);
            fout = $fopen("rc_vib.txt", "w");
            for (seg = 0; seg < 3; seg = seg + 1) begin
                wr_reg(8'h33, DEPTHS[seg][7:0]);          // VIB_DEPTH 低
                wr_reg(8'h34, DEPTHS[seg][15:8]);         // VIB_DEPTH 高
                $display("    深度段 %0d：VIB_DEPTH=%0d", seg, DEPTHS[seg]);
                for (ns = 0; ns < DURS[seg]; ns = ns + 1) begin
                    @(posedge clk);
                    while (!u_top.sample_en) @(posedge clk);
                    $fdisplay(fout, "%0d", u_top.u_tdm.phase_mem[0]);
                end
            end
            $fclose(fout);
            $display("  → rc_vib.txt（三段：深度 0 / 1000 / 2000）");
        end
        else if (which == 3'd4) begin
            //---------------------------------------------------------------
            // 旁路等价性（E4）：FX 两个效果都关时，顶层音频通路必须与
            // 引擎输出【逐位相同】—— 因为顶层是零延迟组合 mux，
            // 完全绕开 fx_delay。这一条保证"加效果器"没有偷偷改变原音。
            //---------------------------------------------------------------
            wr_reg(8'h40, 8'h01);       // FX_CTRL: 仅干声、两效果关
            note_on(7'd69);
            wait_samples(30);
            fout = $fopen("rc_bypass.txt", "w");
            for (ns = 0; ns < 2000; ns = ns + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
                $fwrite(fout, "%0d %0d\n", u_top.u_tdm.sample_out, u_top.audio);
            end
            $fclose(fout);
            $display("  → rc_bypass.txt（引擎输出 vs 顶层音频）");
        end
        else if (which == 3'd5) begin
            //---------------------------------------------------------------
            // E7 集成：通过寄存器打开定序器，验证它【真的驱动了引擎】
            //   逐样本记录 (引擎在奏声部数, LED, 音频是否非零)
            //   LED 是共阳极取反的，判据里要再取反回来。
            //---------------------------------------------------------------
            wr_reg(8'h54, 8'h80);                 // SEQ_VEL = 128
            wr_reg(8'h51, 8'h70);                 // TEMPO_INC = 0x3170 = 12656
            wr_reg(8'h52, 8'h31);
            wr_reg(8'h53, 8'h00);
            wr_reg(8'h50, 8'h01);                 // SEQ_CTRL = 使能
            fout = $fopen("rc_seq.txt", "w");
            for (ns = 0; ns < 12000; ns = ns + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
                $fwrite(fout, "%0d %0d %0d\n",
                        (u_top.nm_active != 0) ? 1 : 0, led,
                        (u_top.u_tdm.sample_out != 0) ? 1 : 0);
            end
            $fclose(fout);
            $display("  → rc_seq.txt（在奏声部数 / LED / 音频非零）");
        end
        else begin
            //---------------------------------------------------------------
            // E2：滑音速率（写 GLIDE_STEP 后量时长与轨迹）
            //   要触发滑音必须【抢占】—— 先把 32 个组占满，再弹第 33 个音
            //---------------------------------------------------------------
            wr_reg(8'h00, 8'h04);       // CTRL: 滑音开、颤音关
            if (which == 3'd2) begin
                wr_reg(8'h35, 8'h14);   // GLIDE_STEP = 20（Q16/样本）
                wr_reg(8'h36, 8'h00);
                $display("    GLIDE_STEP = 20  → 32 个半音(55216) 约 2761 样本");
            end
            else begin
                wr_reg(8'h35, 8'hA0);   // GLIDE_STEP = 160（8 倍）
                wr_reg(8'h36, 8'h00);
                $display("    GLIDE_STEP = 160 → 32 个半音(55216) 约 345 样本（8 倍速）");
            end
            // 占满 32 个组（音 40..71）
            for (g = 0; g < 32; g = g + 1) begin
                note_on(40 + g);
                wait_samples(2);
            end
            wait_samples(10);
            $display("    32 个组已占满（组 0 = MIDI 40）");
            // 第 33 个音：抢占组 0 → 滑音 40 → 72
            note_on(7'd72);
            $display("    已发抢占音 MIDI 72（组 0：40 → 72）");
            if (which == 3'd2) fout = $fopen("rc_glide20.txt", "w");
            else               fout = $fopen("rc_glide160.txt", "w");
            for (ns = 0; ns < 3000; ns = ns + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
                // 组 0 的基频（slot 0）、第 16 泛音（slot 15）、以及 RTL 自己的 gq[0]
                //   把 gq 也 dump 出来：判据可以直接核"线性速率"这条递推，
                //     而不必用"表里算出来的初值"去反推（两者会因倒数表的
                //     20 位舍入差 1~2 个计数，那是精度问题不是设计问题）。
                $fwrite(fout, "%0d %0d %0d\n",
                        u_top.u_tdm.phase_mem[0], u_top.u_tdm.phase_mem[15],
                        u_top.u_tdm.u_pmod.gq[0]);
            end
            $fclose(fout);
            $display("  → rc_glide%0d.txt", (which == 3'd2) ? 20 : 160);
        end

        $display("  完成");
        $finish;
    end

    // 硬超时（最长的一段是颤音三段 ≈ 7900 样本 ≈ 168 ms 仿真时间，
    //         所以给 400 ms —— 第一版写 80 ms，实测直接超时）
    initial begin
        #400_000_000;
        $display("[TIMEOUT] test=%0d", which);
        $finish;
    end

endmodule
