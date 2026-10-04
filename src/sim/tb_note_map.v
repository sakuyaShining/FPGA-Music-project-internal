//=============================================================================
// tb_note_map.v —— 音符映射的端到端验证
//
// 【它验证什么】
//   音符映射这一层是不是真的把"MIDI 音符号"变成了"正确频率的声音"。
//   做法：发一串音符事件 → 引擎出声 → 对输出做 FFT → 看谱峰是否落在
//         12 平均律的期望基频上。
//
// 【为什么用 FFT 而不是逐位比对】
//   逐位比对的参照物是"全并行引擎"，而全并行引擎没有音符映射这一层 ✗
//   所以这一层的正确性判据只能是【频率对不对】——
//   这正是赛题现场验证要求的口径（"频谱可观测对应数量独立谱峰"）。
//
// 【演奏时间轴】逐个小节加入音符：C4 – E4 – G4 – D5
//
//   ★ 第四个音刻意【不用 C5】：
//     C5 = 523.26 Hz 与 C4 的二次谐波（261.63 × 2）【频率完全相同】，
//     FFT 无法区分"C5 的基频"和"C4 的二次谐波"。
//     第一版就栽在这里 —— 看起来像"第四个音在 0.15 s 就提前响了"，
//     其实是第一个音自己的谐波。
//     D5 = 587.33 Hz 不是 C4/E4/G4 的任何整数倍，可以无歧义地区分。
//     **这是测试用例的设计问题，不是合成的问题。**
//     0.05 s  C4 (MIDI 60)
//     0.25 s  E4 (MIDI 64)
//     0.45 s  G4 (MIDI 67)
//     0.65 s  C5 (MIDI 72)
//     0.85 s  全部释放
//     1.10 s  结束
//
// 【时间基准】clk = 5 MHz，NSLOT = 128  ->  fs = 39062.5 Hz
//   NG = 8 组 × P = 16 泛音 = 128 时隙
//   ★ 用 128 时隙而不是 tdm_top 的 512，是为了仿真时间可接受；
//     note_map 与 tdm_engine 都是参数化的，两者共用同一套逻辑。
//
// 运行目录需有 sine256.hex / note_inc.hex / preset_part.hex
//=============================================================================

`timescale 1ns/1ps

module tb_note_map;

    localparam NG      = 8;
    localparam P       = 16;
    localparam NSLOT   = NG * P;        // 128
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam ENV_W   = 16;
    localparam OUT_W   = 24;
    localparam NB      = 7;

    localparam real CLK_HALF = 100.0;   // 5 MHz -> 周期 200 ns
    localparam NSAMP   = 42968;         // 1.10 s
    localparam PRESET  = 2'd1;          // 1 = piano

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 音频时钟使能：每 NSLOT 拍一个样本
    //-------------------------------------------------------------------------
    wire sample_en;
    reg [$clog2(NSLOT)-1:0] pc;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                          pc <= 0;
        else if (pc == NSLOT - 1)            pc <= 0;
        else                                 pc <= pc + 1'b1;
    end
    assign sample_en = (pc == 0);

    //-------------------------------------------------------------------------
    // 音符映射
    //-------------------------------------------------------------------------
    reg                ev_valid;
    reg                ev_on;
    reg [NB-1:0]       ev_note;
    reg [AMP_W-1:0]    ev_vel;

    wire               load_en;
    wire [$clog2(NSLOT)-1:0] load_slot;
    wire [PHASE_W-1:0] load_inc;
    wire [AMP_W-1:0]   load_amp;
    wire               load_gate;
    wire [22:0]        load_epar;
    wire               nm_busy;
    wire [NG-1:0]      nm_active;

    note_map #(
        .NG(NG), .P(P), .PHASE_W(PHASE_W), .AMP_W(AMP_W), .NB(NB), .NPRE(4)
    ) u_nm (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(PRESET),
        // ★ 步③ 新增端口：直接例化时必须显式接上安全默认
        //   （悬空会读 z ⇒ spec_replace 变 x ⇒ 装载幅度全 x ✗）
        //   spec_replace=0（叠加）+ 谱全 0 ⇒ 与未加塑谱时逐位相同 ✓
        .spec_we(1'b0), .spec_addr(4'd0), .spec_wdata(8'd0), .spec_replace(1'b0),
        .pad_mask(16'd0), .refresh_valid(1'b0), .rf_lo(7'd0), .rf_hi(8'd0),
        .load_en(load_en), .load_slot(load_slot),
        .load_inc(load_inc), .load_amp(load_amp),
        .load_gate(load_gate), .load_epar(load_epar),
        .busy(nm_busy), .active(nm_active)
    );

    //-------------------------------------------------------------------------
    // TDM 引擎
    //-------------------------------------------------------------------------
    wire signed [OUT_W-1:0] sample;

    tdm_engine #(
        .NSLOT(NSLOT), .PHASE_W(PHASE_W), .AMP_W(AMP_W),
        .ENV_W(ENV_W), .OUT_W(OUT_W), .GAIN_UP(4), .SHIFT(0)
    ) u_tdm (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .clr(1'b0), .pclr(1'b0), .gate_in(1'b1),
        .load_en(load_en), .load_slot(load_slot),
        .load_inc(load_inc), .load_amp(load_amp), .load_gate(load_gate),
        .load_epar(load_epar),
        .load_gq(18'sd0),                 // 滑音由 tb_pitch_mod 专测
        .pmod_cfg(58'd0),                 // 调制全关
        .env_en(1'b1),
        .a_inc(16'd117), .d_inc(16'd1), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(16'd22938), .r_inc(16'd1), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(16'd100), .exp_mode(1'b1),
        .sample_out(sample), .sum_raw(), .slot_dbg()
    );

    //-------------------------------------------------------------------------
    // 演奏事件表：{样本号, 开/关, 音符号}
    //   ★ 释放事件刻意【错开一个样本】，不挤在同一拍：
    //     note_map 装载一组要 P=16 拍，同一拍连发多个事件会撞在装载期上。
    //     错开 1 个样本（25.6 µs）在音乐上完全等价。
    //-------------------------------------------------------------------------
    localparam NEV = 8;
    integer ev_at  [0:NEV-1];
    integer ev_kind[0:NEV-1];       // 1=on 0=off
    integer ev_num [0:NEV-1];

    integer i;
    initial begin
        ev_at[0] = 1953;  ev_kind[0] = 1; ev_num[0] = 60;   // 0.05 s  C4
        ev_at[1] = 9766;  ev_kind[1] = 1; ev_num[1] = 64;   // 0.25 s  E4
        ev_at[2] = 17578; ev_kind[2] = 1; ev_num[2] = 67;   // 0.45 s  G4
        ev_at[3] = 25391; ev_kind[3] = 1; ev_num[3] = 74;   // 0.65 s  D5
        ev_at[4] = 33203; ev_kind[4] = 0; ev_num[4] = 60;   // 0.85 s  释放 C4
        ev_at[5] = 33242; ev_kind[5] = 0; ev_num[5] = 64;   // +1 样本 释放 E4
        ev_at[6] = 33281; ev_kind[6] = 0; ev_num[6] = 67;   // +2 样本 释放 G4
        ev_at[7] = 33320; ev_kind[7] = 0; ev_num[7] = 74;   // +3 样本 释放 D5
    end

    //-------------------------------------------------------------------------
    // 主激励
    //-------------------------------------------------------------------------
    integer k, evi, ns, nsamp_emit;
    integer n_ev;
    integer fout;

    initial begin
        rst_n      = 1'b0;
        ev_valid   = 1'b0;
        ev_on      = 1'b0;
        ev_note    = 7'd0;
        ev_vel     = 8'd0;
        n_ev       = 0;
        nsamp_emit = 0;

        repeat (20) @(posedge clk);
        rst_n = 1'b1;
        repeat (10) @(posedge clk);

        $display("==============================================================");
        $display(" 音符映射端到端验证   NSLOT=%0d (NG=%0d x P=%0d)  fs=%0d Hz",
                 NSLOT, NG, P, 39062);
        $display(" 音色预设 = %0d    时长 %0.2f s", PRESET, NSAMP / 39062.5);
        $display("==============================================================");
        $display(" 演奏时间轴：");
        $display("   0.05s C4(60)   0.25s E4(64)   0.45s G4(67)");
        $display("   0.65s D5(74)   0.85s 起逐个释放");

        fout = $fopen("note_out.txt", "w");

        for (ns = 0; ns < NSAMP; ns = ns + 1) begin
            //---- 本样本的演奏事件（同一拍可能有多个，错开处理不会有）----
            for (evi = 0; evi < NEV; evi = evi + 1) begin
                if (ev_at[evi] == ns) begin
                    @(negedge clk);
                    ev_valid = 1'b1;
                    ev_on    = (ev_kind[evi] != 0);
                    ev_note  = ev_num[evi][NB-1:0];
                    ev_vel   = 8'd220;
                    n_ev     = n_ev + 1;
                    @(negedge clk);
                    ev_valid = 1'b0;
                end
            end

            //---- 推进一个样本周期（恰好 NSLOT 拍）----
            for (k = 0; k < NSLOT; k = k + 1) begin
                @(posedge clk);
                if (sample_en) begin
                    $fdisplay(fout, "%0d %0d", nsamp_emit, $signed(sample));
                    nsamp_emit = nsamp_emit + 1;
                end
            end
        end

        $fclose(fout);
        $display("");
        $display(" 写出 note_out.txt（%0d 个样本）", nsamp_emit);
        $display(" 发出的音符事件数 = %0d", n_ev);
        $finish;
    end

    // 硬超时：★ 必须按【仿真时间】设，不是按拍数。
    //   1.10 s 音频 = 42968 样本 × 128 拍 × 200 ns ≈ 1.1 s 仿真时间。
    //   第一版写 #20_000_000（20 ms）—— 差了 55 倍，仿真必然超时。
    initial begin
        #2_000_000_000;
        $display("[TIMEOUT]");
        $finish;
    end

endmodule
