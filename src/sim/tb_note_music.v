//=============================================================================
// tb_note_music.v —— 音乐示范：和声进行 + 音色切换
//
// 【它产出什么】
//   一段约 15 秒的乐曲，从 RTL 仿真直接渲染成 WAV：
//     4 小节一轮 I–vi–IV–V（C–Am–F–G），共三轮
//       (本次)：钢琴   (preset 1)
//       (本次)：钟     (preset 2)   ← 同时演示"≥2 种音色自由切换"
//       (本次)：马林巴 (preset 3)
//   每小节 1.2 s，共 12 小节。
//
// 【为什么用 note_map + tdm_engine 直连，而不是 tdm_top】
//   实测仿真速度约 50500 拍/秒。tdm_top 是 576 拍/样本（27 MHz / 46875 Hz），
//   1 秒音频要 8.9 分钟；本测试台是 128 拍/样本（5 MHz / 39062.5 Hz），
//   快 4.5 倍，约 1.5 分钟/秒音频。
//   **合成逻辑与 tdm_top 完全相同**，差别只有时隙数与时钟；
//   tdm_top 的集成（含 I2S 闭环）由 tb_tdm_top 单独验证。
//
// 【时间基准】clk = 5 MHz，NSLOT = 128（NG=8 组 × P=16 泛音），fs = 39062.5 Hz
// 运行目录需有 sine256.hex / note_inc.hex / preset_part.hex
//   $readmemh 找不到文件时不报错，只是表全 0、输出静音 —— 这个坑踩过三次。
//=============================================================================

`timescale 1ns/1ps

module tb_note_music;

    localparam NG      = 8;
    localparam P       = 16;
    localparam NSLOT   = NG * P;        // 128
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam ENV_W   = 16;
    localparam OUT_W   = 24;
    localparam NB      = 7;

    localparam real CLK_HALF = 100.0;   // 5 MHz
    localparam BAR_N   = 46875;         // 每小节 1.2 s
    localparam NBAR    = 12;            // 12 小节（3 轮）
    localparam TAIL    = 24000;         // 尾音
    localparam NSAMP   = NBAR * BAR_N + TAIL;   // 586500 ≈ 15.0 s

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    wire sample_en;
    reg [$clog2(NSLOT)-1:0] pc;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)               pc <= 0;
        else if (pc == NSLOT - 1) pc <= 0;
        else                      pc <= pc + 1'b1;
    end
    assign sample_en = (pc == 0);

    reg                ev_valid;
    reg                ev_on;
    reg [NB-1:0]       ev_note;
    reg [AMP_W-1:0]    ev_vel;
    reg [1:0]          preset;          // 逐轮切换

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
        .preset(preset),
        // 步③ 新增端口的安全默认（悬空读 z ⇒ 幅度变 x）
        .spec_we(1'b0), .spec_addr(4'd0), .spec_wdata(8'd0), .spec_replace(1'b0),
        .pad_mask(16'd0), .refresh_valid(1'b0), .rf_lo(7'd0), .rf_hi(8'd0),
        .load_en(load_en), .load_slot(load_slot),
        .load_inc(load_inc), .load_amp(load_amp),
        .load_gate(load_gate), .load_epar(load_epar),
        .busy(nm_busy), .active(nm_active)
    );

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
    // 曲目表：12 小节 × 3 音 × (开+关) = 72 个事件
    //   和弦轮转：C(60,64,67)  Am(57,60,64)  F(53,57,60)  G(55,59,62)
    //-------------------------------------------------------------------------
    localparam NEV = NBAR * 6;
    integer ev_at  [0:NEV-1];
    integer ev_kind[0:NEV-1];
    integer ev_num [0:NEV-1];

    function integer chord_note;
        input integer bar;
        input integer v;
        integer ci;
        begin
            ci = bar % 4;
            if (ci == 0)      chord_note = (v == 0) ? 60 : (v == 1) ? 64 : 67;
            else if (ci == 1) chord_note = (v == 0) ? 57 : (v == 1) ? 60 : 64;
            else if (ci == 2) chord_note = (v == 0) ? 53 : (v == 1) ? 57 : 60;
            else              chord_note = (v == 0) ? 55 : (v == 1) ? 59 : 62;
        end
    endfunction

    integer b, v, e;
    initial begin
        e = 0;
        for (b = 0; b < NBAR; b = b + 1) begin
            for (v = 0; v < 3; v = v + 1) begin
                ev_at[e]   = b * BAR_N + 100 + v * 40;
                ev_kind[e] = 1;
                ev_num[e]  = chord_note(b, v);
                e = e + 1;
            end
            for (v = 0; v < 3; v = v + 1) begin
                ev_at[e]   = b * BAR_N + BAR_N - 1000 + v * 40;
                ev_kind[e] = 0;
                ev_num[e]  = chord_note(b, v);
                e = e + 1;
            end
        end
    end

    integer k, evi, ns, nsamp_emit, n_ev;
    integer bar_now;
    integer fout;

    //-------------------------------------------------------------------------
    // 音色切换：每 4 小节一轮（1=钢琴, 2=钟, 3=马林巴）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) preset <= 2'd1;
        else begin
            bar_now = nsamp_emit / BAR_N;
            if (bar_now < 4)       preset <= 2'd1;
            else if (bar_now < 8)  preset <= 2'd2;
            else                   preset <= 2'd3;
        end
    end

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
        $display(" 音乐示范  I-vi-IV-V x 3 轮（钢琴 / 钟 / 马林巴）");
        $display(" NSLOT=%0d (NG=%0d x P=%0d)  fs=%0d Hz  %.2f s",
                 NSLOT, NG, P, 39062, NSAMP / 39062.5);
        $display("==============================================================");

        fout = $fopen("music_out.txt", "w");

        for (ns = 0; ns < NSAMP; ns = ns + 1) begin
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

            for (k = 0; k < NSLOT; k = k + 1) begin
                @(posedge clk);
                if (sample_en) begin
                    $fdisplay(fout, "%0d %0d", nsamp_emit, $signed(sample));
                    nsamp_emit = nsamp_emit + 1;
                end
            end
        end

        $fclose(fout);
        $display(" 写出 music_out.txt（%0d 个样本）  事件数 %0d", nsamp_emit, n_ev);
        $finish;
    end

    // 硬超时：按【仿真时间】算，不是拍数。
    //   586500 样本 × 128 拍 × 200 ns ≈ 15.0 s 仿真时间，留一倍余量。
    //   （这个坑本会话踩过两次，两次都是把拍数当成了仿真时间。）
    initial begin
        #30_000_000_000;
        $display("[TIMEOUT]");
        $finish;
    end

endmodule
