//=============================================================================
// tb_pitch_mod.v —— 表情调制（滑音 + 颤音）验收测试台
//
// 【两个 DUT，各测一件事】
//   A：note_map → tdm_engine（GLIDE_EN=1, VIB_EN=0）
//      测"滑音"：先占满 8 个组，再弹第 9 个音 → 抢占组 0 → 音高从
//      MIDI 60 滑到 MIDI 74。逐样本记录组 0 的 slot 0 与 slot 15 的相位。
//   B：tdm_engine 直连（GLIDE_EN=0, VIB_EN=1）
//      测"颤音"：手动装载 slot 0 与 slot 15，观察它们的相位增量
//      按 LFO（5 Hz）周期性变化。逐样本记录两个 slot 的相位。
//
// 【判据在 pitch_mod_check.py 里，本测试台只负责产生数据】
//   G1 滑音轨迹 ≡ Python 镜像（逐样本 0 差异）
//   G2 滑音全程 第 16 泛音/第 1 泛音 的频率比 = 16（±0.1%）
//   V1 颤音：频偏(cents) 的幅度 = 设定深度、周期 = 设定 LFO 周期
//   V2 颤音全程两个泛音的 cents 偏移相等（±0.1 音分）
//   C1 相位增量连续（无跳变/无咔哒）
//
// 【时间基准】clk = 5 MHz，NSLOT = 128 → fs = 39062.5 Hz
//   运行目录必须有三张表：sine256.hex / note_inc.hex / preset_part.hex
//                        / recip_inc.hex（滑音初值用）
//   $readmemh 找不到不报错，只是表全 0 —— 这个坑本项目踩过三次。
//=============================================================================

`timescale 1ns/1ps

module tb_pitch_mod;

    localparam NG      = 8;
    localparam P       = 16;
    localparam NSLOT   = NG * P;          // 128
    // 出货配置下【周期 = 时隙数】（见 tdm_top.v 时钟链注释）。
    //   测试台与出货配置保持一致：PERIOD == NSLOT。
    //   （曾经为了给"分时复用衰减"腾空闲窗口而做成 NSLOT+64 ——
    //    那个方案反而暴露了 sc 回卷重访的隐藏 bug，现已废弃：
    //    时钟链改成 ÷16 后周期正好 = 512，滑音也改成线性速率、不需要窗口。）
    localparam PERIOD  = NSLOT;           // 128
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam ENV_W   = 16;
    localparam OUT_W   = 24;
    localparam NB      = 7;

    localparam real CLK_HALF = 100;       // 200 ns -> 5 MHz
    localparam real FS  = 1.0e9 / (2.0 * CLK_HALF) / PERIOD;   // 39062.5 Hz

    localparam integer NS_A = 40000;      // A 段样本数（≈1.024 s）
    localparam integer NS_B = 24000;      // B 段样本数（≈0.614 s）

    // 颤音：深度 ≈26.3 音分（Q16 1000），LFO 5 Hz
    localparam [15:0] VIB_DEPTH = 16'd1000;
    localparam [23:0] LFO_INC_5HZ = 24'd2147;   // 5.0 Hz × 2^24 / 39062.5

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 样本边界：每 NSLOT 拍一次
    //   注意不能写成 "pc==0 时 sample_en=1，且 sample_en 时 pc<=0" ——
    //     那会让 pc 永远停在 0、sample_en 永远为高，引擎的 sc 每拍被清零，
    //     结果"两个引擎都不推进"。第一版就栽在这里（数据全 0）。
    //     正确写法：pc 数到 NSLOT-1 归零，sample_en = (pc == NSLOT-1)。
    //-------------------------------------------------------------------------
    reg [$clog2(PERIOD)-1:0] pc;
    //   不要再对参数做位选（NSLOT[6:0] 对 128 求值是 0，不是 127）——
    //     直接写 PERIOD-1，让比较在 32 位上下文中零扩展。
    wire sample_en = (pc == PERIOD - 1);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                             pc <= {($clog2(PERIOD)){1'b0}};
        else if (pc == PERIOD - 1)              pc <= {($clog2(PERIOD)){1'b0}};
        else                                    pc <= pc + 1'b1;
    end

    // 自检：相邻两个 sample_en 之间应恰好 128 拍（第一版自锁时这里是 1）
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
    // A 段：note_map + tdm_engine（滑音）
    //-------------------------------------------------------------------------
    reg                ev_valid = 1'b0;
    reg                ev_on    = 1'b0;
    reg [NB-1:0]       ev_note  = 7'd0;
    reg [AMP_W-1:0]    ev_vel   = 8'd0;
    reg [1:0]          preset   = 2'd1;      // 1 = piano

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
        // 运行时参数总线（58 位）：
        //   { lfo_inc[23:0], vib_depth[15:0], glide_step[15:0],
        //     vib_en, glide_en }
        //   A 段只开滑音（滑音速率 10/样本 ≈ 93 ms 走完 1400 音分）
        .pmod_cfg({24'd2147, 16'd1000, 16'd10, 1'b0, 1'b1}),
        .env_en(1'b1),
        .a_inc(16'd117), .d_inc(16'd1), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(16'd22938), .r_inc(16'd1), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(16'd100), .exp_mode(1'b1),
        .sample_out(a_sample), .sum_raw(a_sum), .slot_dbg()
    );

    //-------------------------------------------------------------------------
    // B 段：tdm_engine 直连（颤音）
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
        // B 段：只开颤音（LFO 5 Hz、深度 1000、glide_en=0）
        .pmod_cfg({24'd2147, 16'd1000, 16'd10, 1'b1, 1'b0}),
        .env_en(1'b1),
        .a_inc(16'd117), .d_inc(16'd1), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(16'd22938), .r_inc(16'd1), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(16'd100), .exp_mode(1'b1),
        .sample_out(b_sample), .sum_raw(b_sum), .slot_dbg()
    );

    //-------------------------------------------------------------------------
    // 记录：每样本取一次相位（用于算瞬时 inc）
    //-------------------------------------------------------------------------
    integer fa0, fa15, fb0, fb15, fau;
    integer ns_a, ns_b;

    initial begin
        fa0  = $fopen("pm_a_s0.txt",  "w");
        fa15 = $fopen("pm_a_s15.txt", "w");
        fau  = $fopen("pm_a_out.txt", "w");
        fb0  = $fopen("pm_b_s0.txt",  "w");
        fb15 = $fopen("pm_b_s15.txt", "w");
        ns_a = 0; ns_b = 0;
    end

    always @(posedge clk) begin
        if (sample_en) begin
            if (ns_a < NS_A) begin
                $fdisplay(fa0,  "%0d", u_ea.phase_mem[0]);
                $fdisplay(fa15, "%0d", u_ea.phase_mem[15]);
                $fdisplay(fau,  "%0d", a_sample);
                ns_a = ns_a + 1;
            end
            if (ns_b < NS_B) begin
                $fdisplay(fb0,  "%0d", u_eb.phase_mem[0]);
                $fdisplay(fb15, "%0d", u_eb.phase_mem[15]);
                ns_b = ns_b + 1;
            end
        end
    end

    //-------------------------------------------------------------------------
    // 激励
    //-------------------------------------------------------------------------
    integer i;
    reg [NB-1:0] chord [0:7];             // 8 个音，占满 8 个组

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

    task b_load(input [8:0] sl, input [PHASE_W-1:0] inc, input [AMP_W-1:0] amp);
        begin
            @(posedge clk);
            b_load_slot <= sl;
            b_load_inc  <= inc;
            b_load_amp  <= amp;
            b_load_gate <= 1'b1;
            // 保持型包络：s_lvl 满幅、几乎不衰减
            b_load_epar <= {16'd30000, 2'd3, 5'd20};
            b_load_en   <= 1'b1;
            @(posedge clk);
            b_load_en   <= 1'b0;
        end
    endtask

    initial begin
        rst_n = 1'b0;
        repeat (20) @(posedge clk);
        rst_n = 1'b1;

        chord[0] = 7'd60; chord[1] = 7'd62; chord[2] = 7'd64; chord[3] = 7'd65;
        chord[4] = 7'd67; chord[5] = 7'd69; chord[6] = 7'd71; chord[7] = 7'd72;

        $display("==============================================================");
        $display(" 表情调制验收：滑音（A）+ 颤音（B）  fs=%0.1f Hz", FS);
        $display("==============================================================");

        //---- B：装载 slot 0（基音）与 slot 15（第 16 泛音）----
        //   inc 基准 = MIDI 60 的相位增量（从 note_inc.hex 读，见 Python 校验）
        @(posedge clk);
        repeat (4) @(posedge clk);
        b_load(9'd0,  24'd112367, 8'd100);      // MIDI 60 @fs=39062.5
        b_load(9'd15, 24'd1797872, 8'd60);      // 16 × 112367 = 1797872（24 位内）

        //---- A：先用 8 个音占满 8 个组（每 10 ms 一个）----
        for (i = 0; i < 8; i = i + 1) begin
            note_on(chord[i], 8'd200);
            repeat (NSLOT * 50) @(posedge clk);   // 10 ms
        end

        //---- A：第 9 个音 → 抢占组 0（原为 MIDI 60）→ 滑音 60 → 74 ----
        note_on(7'd74, 8'd200);
        $display("     已发出第 9 个音（MIDI 74），应抢占组 0 并开始滑音");

        //---- 跑满 A/B 两段 ----
        repeat (NSLOT * NS_A + 64) @(posedge clk);

        $display("     A 段样本 %0d，B 段样本 %0d", ns_a, ns_b);
        $display("     自检：sample_en 周期 = %0d 拍（应为 %0d），共 %0d 次",
                 per_meas, PERIOD, n_se);
        $display("     组 0 活动位 = %b (bit0 应为 1)", a_active);
        $display("     数据已写出：pm_a_s0/s15/out、pm_b_s0/s15.txt");
        $fclose(fa0); $fclose(fa15); $fclose(fau);
        $fclose(fb0); $fclose(fb15);
        $finish;
    end

    // 硬超时（A 段 ≈1.03 s 仿真时间，留足余量）
    initial begin
        #3_000_000_000;
        $display("[TIMEOUT]");
        $finish;
    end

endmodule
