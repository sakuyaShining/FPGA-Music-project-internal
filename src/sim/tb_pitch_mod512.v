//=============================================================================
// tb_pitch_mod512.v —— 512 档（出货配置）功能仿真：32 复音 + 滑音 + 颤音
//
// 【为什么必须单独做这一档】
//   前面的 tb_pitch_mod 用的是 NG=8 / 128 时隙（快，适合调轨迹），
//   而出货配置是 NSLOT=512（NG=32 组 × 16 泛音）。
//   两者差的不是"性能"，是**索引位宽**：组号 = slot[8:4]（5 位）。
//   本次修掉的一个真 bug 正出在这里 —— 组号曾被截成 4 位，
//   于是第 16~31 组的滑音初值会被写到错误的组（0~15）。
//   而综合告警发现了它、仿真没发现，因为仿真当时只有 8 个组。
//   ⇒ 所以要有这一档：让抢占指针走到 ≥16 号组，正是会出错的那一段。
//
// 【三个 DUT/三段，各测一件事】
//   A：note_map(NG=32) → tdm_engine(NSLOT=512, GLIDE_EN=1, VIB_EN=0)
//      1) E1 实证：先弹满 32 个音（MIDI 40..71，占满 32 个组）
//         → 记录 32 个"基频时隙"（slot 0,16,32,…,496）的相位增量，
//           逐个与 note_inc.hex 的期望值比对（32 路独立声部同时正确）
//         → 同时存一段音频，用于 FFT 旁证。
//      2) 滑音：再弹 17 个音（MIDI 88,87,…,72）→ 抢占指针依次推进到 0..16
//         → 第 17 个音落在【16 号组】（原为 MIDI 56）→ 滑音 56→72
//         → 记录 slot 256（基频）与 slot 271（第 16 泛音）的相位。
//   B：tdm_engine(NSLOT=512, VIB_EN=1, LFO=50 Hz)
//      → 记录 slot 0 与 slot 15 的相位，验证颤音深度/周期/比例性。
//
// 【时间基准】clk = 25 MHz（周期 40 ns），NSLOT=512 → fs = 48828.125 Hz
//   （时间基准只影响"音频听起来多快"，不影响逻辑正确性；
//     表必须用 --fs 48828.125 生成，否则测得的频率对不上期望值）
//
// 【运行目录必须有】sine256.hex / note_inc.hex / preset_part.hex / recip_inc.hex
//   $readmemh 找不到不报错，只是表全 0 —— 这个坑本项目踩过三次。
//=============================================================================

`timescale 1ns/1ps

module tb_pitch_mod512;

    // ---- 出货配置 ----
    localparam NG      = 32;
    localparam P       = 16;
    localparam NSLOT   = NG * P;          // 512
    // 周期 = 时隙数 = 512，与出货配置【完全一致】（时钟链 ÷16 × 32）
    localparam PERIOD  = NSLOT;           // 512
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam ENV_W   = 16;
    localparam OUT_W   = 24;
    localparam NB      = 7;

    localparam real CLK_HALF = 20;        // 40 ns -> 25 MHz
    localparam real FS  = 1.0e9 / (2.0 * CLK_HALF) / PERIOD;   // 48828.125 Hz

    // 音符事件间隔（样本数）：49 ≈ 1.003 ms
    localparam integer GAP = 49;
    // E1 观测窗
    localparam integer W_FUND0 = 1600, W_FUND1 = 1700;   // 32 路基频（100 样本）
    localparam integer W_AUD0  = 1600, W_AUD1  = 5700;   // 音频（4100 样本，供 FFT）
    localparam integer TAIL    = 6000;                   // 最后抢占地滑音观察窗

    // 颤音：深度 26.22 音分，LFO 50 Hz
    localparam [15:0] VIB_DEPTH   = 16'd1000;
    localparam [23:0] LFO_INC_50HZ = 24'd17180;          // 50 Hz × 2^24 / 48828.125

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 样本边界
    //-------------------------------------------------------------------------
    reg [$clog2(PERIOD)-1:0] pc;
    wire sample_en = (pc == PERIOD - 1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                 pc <= {($clog2(PERIOD)){1'b0}};
        else if (pc == PERIOD - 1)  pc <= {($clog2(PERIOD)){1'b0}};
        else                        pc <= pc + 1'b1;
    end

    // 自检：sample_en 周期必须 = NSLOT 拍
    integer clk_cnt, per_meas, n_se;
    initial begin clk_cnt = 0; per_meas = 0; n_se = 0; end
    always @(posedge clk) begin
        clk_cnt = clk_cnt + 1;
        if (sample_en) begin
            n_se = n_se + 1;
            if (per_meas == 0 && n_se == 2) per_meas = clk_cnt;
            clk_cnt = 0;
        end
    end

    //-------------------------------------------------------------------------
    // A：note_map + tdm_engine（32 复音 + 滑音）
    //-------------------------------------------------------------------------
    reg                ev_valid = 1'b0;
    reg                ev_on    = 1'b0;
    reg [NB-1:0]       ev_note  = 7'd0;
    reg [AMP_W-1:0]    ev_vel   = 8'd0;
    reg [1:0]          preset   = 2'd1;      // 1 = piano（泛音 0 的比值 = 1.000，基频精确）

    wire               a_load_en, a_load_gate;
    wire [8:0]         a_load_slot;
    wire [PHASE_W-1:0] a_load_inc;
    wire [AMP_W-1:0]   a_load_amp;
    wire [22:0]        a_load_epar;
    wire signed [17:0] a_load_gq;
    wire               a_busy;
    wire [NG-1:0]      a_active;

    note_map #(
        .NG(NG), .P(P), .PHASE_W(PHASE_W), .AMP_W(AMP_W), .NB(NB), .NPRE(4),
        .GLIDE_EN(1'b1)
    ) u_nm (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note),
        .ev_vel(ev_vel), .preset(preset),
        // Explicit identity controls: floating new inputs make amplitudes X.
        .tilt_vbias(10'sd0), .tilt_vgain(8'd0), .vel_vscale(9'd256), .tilt(8'h70),
        .spec_commit(1'b0),
        // 步③ 新增端口的安全默认（悬空读 z ⇒ 幅度变 x）
        .spec_we(1'b0), .spec_addr(4'd0), .spec_wdata(8'd0), .spec_replace(1'b0),
        .pad_mask(16'd0), .refresh_valid(1'b0), .rf_lo(7'd0), .rf_hi(8'd0),
        .load_en(a_load_en), .load_slot(a_load_slot), .load_inc(a_load_inc),
        .load_amp(a_load_amp), .load_gate(a_load_gate), .load_epar(a_load_epar),
        .load_gq(a_load_gq),
        .busy(a_busy), .active(a_active)
    );

    wire signed [OUT_W-1:0] a_sample;
    wire [31:0]             a_sum;

    tdm_engine #(
        .NSLOT(NSLOT), .PHASE_W(PHASE_W), .AMP_W(AMP_W),
        .ENV_W(ENV_W), .OUT_W(OUT_W), .GAIN_UP(0), .SHIFT(0),
        .PART(P)
    ) u_ea (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .clr(1'b0), .pclr(1'b0), .gate_in(1'b1),
        .load_en(a_load_en), .load_slot(a_load_slot), .load_inc(a_load_inc),
        .load_amp(a_load_amp), .load_gate(a_load_gate), .load_epar(a_load_epar),
        .load_gq(a_load_gq),
        // A 段：只开滑音（glide_en=1, vib_en=0）
        .pmod_cfg({24'd17180, 16'd1000, 16'd10, 1'b0, 1'b1}),
        .env_en(1'b1),
        .a_inc(16'd117), .d_inc(16'd1), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(16'd22938), .r_inc(16'd1), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(16'd100), .exp_mode(1'b1),
        .sample_out(a_sample), .sum_raw(a_sum), .slot_dbg()
    );

    //-------------------------------------------------------------------------
    // B：tdm_engine 直连（颤音）
    //-------------------------------------------------------------------------
    reg                b_load_en   = 1'b0;
    reg [8:0]          b_load_slot = 9'd0;
    reg [PHASE_W-1:0]  b_load_inc  = 24'd0;
    reg [AMP_W-1:0]    b_load_amp  = 8'd0;
    reg                b_load_gate = 1'b0;
    reg [22:0]         b_load_epar = 23'd0;

    wire signed [OUT_W-1:0] b_sample;
    wire [31:0]             b_sum;

    tdm_engine #(
        .NSLOT(NSLOT), .PHASE_W(PHASE_W), .AMP_W(AMP_W),
        .ENV_W(ENV_W), .OUT_W(OUT_W), .GAIN_UP(0), .SHIFT(0),
        .PART(P)
    ) u_eb (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .clr(1'b0), .pclr(1'b0), .gate_in(1'b1),
        .load_en(b_load_en), .load_slot(b_load_slot), .load_inc(b_load_inc),
        .load_amp(b_load_amp), .load_gate(b_load_gate), .load_epar(b_load_epar),
        .load_gq(18'sd0),
        // B 段：只开颤音（50 Hz LFO 字 = 17180、深度 1000）
        .pmod_cfg({24'd17180, 16'd1000, 16'd10, 1'b1, 1'b0}),
        .env_en(1'b1),
        .a_inc(16'd117), .d_inc(16'd1), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(16'd22938), .r_inc(16'd1), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(16'd100), .exp_mode(1'b1),
        .sample_out(b_sample), .sum_raw(b_sum), .slot_dbg()
    );

    //-------------------------------------------------------------------------
    // 记录
    //-------------------------------------------------------------------------
    integer ffund, faout, fb0, fb15, fgf, fgp, ci;
    integer ns_a, ns_b;

    initial begin
        ffund = $fopen("p512_fund.txt", "w");   // 32 路基频相位（100 个样本）
        faout = $fopen("p512_out.txt",  "w");   // A 段音频（4100 个样本）
        fb0   = $fopen("p512_b0.txt",   "w");   // B 段 slot 0 相位
        fb15  = $fopen("p512_b15.txt",  "w");   // B 段 slot 15 相位
        fgf   = $fopen("p512_g_f.txt",  "w");   // 16 号组基频（slot 256）相位
        fgp   = $fopen("p512_g_p.txt",  "w");   // 16 号组第 16 泛音（slot 271）相位
        ns_a  = 0; ns_b = 0;
    end

    always @(posedge clk) begin
        if (sample_en) begin
            if (ns_a >= W_FUND0 && ns_a < W_FUND1) begin
                for (ci = 0; ci < NG; ci = ci + 1)
                    $fwrite(ffund, "%0d ", u_ea.phase_mem[ci * P]);
                $fwrite(ffund, "\n");
            end
            if (ns_a >= W_AUD0 && ns_a < W_AUD1)
                $fdisplay(faout, "%0d", a_sample);
            // 16 号组的滑音观测（全程记录：抢占发生的样本也要看得见）
            $fdisplay(fgf, "%0d", u_ea.phase_mem[16 * P]);
            $fdisplay(fgp, "%0d", u_ea.phase_mem[16 * P + 15]);
            if (ns_b < 4000) begin
                $fdisplay(fb0,  "%0d", u_eb.phase_mem[0]);
                $fdisplay(fb15, "%0d", u_eb.phase_mem[15]);
                ns_b = ns_b + 1;
            end
            ns_a = ns_a + 1;
        end
    end

    //-------------------------------------------------------------------------
    // 激励
    //-------------------------------------------------------------------------
    task note_on(input [NB-1:0] n, input [AMP_W-1:0] v);
        begin
            @(posedge clk);
            ev_note  <= n;
            ev_vel   <= v;
            ev_on    <= 1'b1;
            ev_valid <= 1'b1;
            @(posedge clk);
            ev_valid <= 1'b0;
        end
    endtask

    task wait_samples(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) begin
                @(posedge clk);
                while (!sample_en) @(posedge clk);
            end
        end
    endtask

    task b_load(input [8:0] sl, input [PHASE_W-1:0] inc, input [AMP_W-1:0] amp);
        begin
            @(posedge clk);
            b_load_slot <= sl;
            b_load_inc  <= inc;
            b_load_amp  <= amp;
            b_load_gate <= 1'b1;
            b_load_epar <= {16'd30000, 2'd3, 5'd20};
            b_load_en   <= 1'b1;
            @(posedge clk);
            b_load_en   <= 1'b0;
        end
    endtask

    integer i;
    reg [NB-1:0] fill_note;

    initial begin
        rst_n = 1'b0;
        repeat (20) @(posedge clk);
        rst_n = 1'b1;

        $display("==============================================================");
        $display(" 512 档功能仿真：32 复音 + 滑音 + 颤音   fs=%0.3f Hz", FS);
        $display("==============================================================");

        //---- B：装载 slot 0（基频）与 slot 15（第 16 泛音）----
        //   inc 直接从 note_map 的表里取（表由 --fs 48828.125 生成）——
        //     手写常量在改时间基准时必然过期，这个坑不留第二次。
        repeat (4) @(posedge clk);
        b_load(9'd0,  u_nm.note_rom[60],        8'd100);   // MIDI 60
        b_load(9'd15, u_nm.note_rom[60] * 16,   8'd60);    // 16 × 基频

        //---- A-1：弹满 32 个音（MIDI 40..71）----
        for (i = 0; i < NG; i = i + 1) begin
            fill_note = 40 + i;
            note_on(fill_note, 8'd200);
            wait_samples(GAP);
        end
        $display("     已弹满 32 个音（MIDI 40..71），活动组 = %b", a_active);

        //---- E1 观测窗（32 路基频 + 音频）----
        wait_samples(W_AUD1 - W_FUND0);

        //---- A-2：17 次抢占（MIDI 88,87,…,72）→ (本次)落在 16 号组 ----
        for (i = 0; i < 17; i = i + 1) begin
            note_on(88 - i, 8'd200);
            wait_samples(GAP);
        end
        $display("     已发 17 次抢占，最后一次（MIDI 72）应落在 16 号组（原 MIDI 56）");

        //---- 滑音观察窗 ----
        wait_samples(TAIL);

        $display("     自检：sample_en 周期 = %0d 拍（应为 %0d），共 %0d 次",
                 per_meas, PERIOD, n_se);
        $display("     A 段样本 %0d，B 段样本 %0d", ns_a, ns_b);
        $display("     组活动位（低 8 位应全 1）= %b", a_active[7:0]);
        $display("     数据：p512_fund/out/g_f/g_p/b0/b15.txt");
        $fclose(ffund); $fclose(faout); $fclose(fb0); $fclose(fb15);
        $fclose(fgf);   $fclose(fgp);
        $finish;
    end

    // 硬超时（总时长约 0.26 s 仿真时间）
    initial begin
        #1_000_000_000;
        $display("[TIMEOUT]");
        $finish;
    end

endmodule
