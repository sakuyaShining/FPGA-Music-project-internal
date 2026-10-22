//=============================================================================
// tb_tdm_equiv.v —— TDM ≡ 全并行【逐样本逐位一致】黄金参考测试
//
// 【为什么这是最强的验收形式】
//   TDM 不是新算法，是【同一套数学、不同的调度】。
//   所以它有一个天然的黄金参考：已通过 10 套回归的全并行引擎。
//   两者喂完全相同的参数，输出序列必须逐样本完全相同（允许一个固定延迟）。
//
//   这条一致性一旦成立，就同时证明了：
//     · 时隙调度正确（每个时隙每周期恰好被访问一次）
//     · BSRAM 状态读写正确（相位推进、包络推进、门沿检测）
//     · 流水线对齐正确（含"相位取当期、包络取下一期"那一拍错位）
//     · 地址回绕正确（sc + LAT 的自然溢出）
//   任何一处差一拍，输出就会立刻对不上。
//
// 【比对的是什么】
//   刻意不比"混音后的输出"，而是比【求和结果本身】：
//     · 并行侧：4 个声部 voice_out 的整数和（未过 mixer）
//     · TDM 侧：sum_raw（未过饱和）
//   这样把增益与饱和排除在外，比对的是纯粹的运算结果。
//
// 【本版重写说明（2026-09-30）】
//   上一版累积了三个调试块 + fork/join 计数 bug，导致仿真在采集前就卡死，
//   而我又拿旧文件当结果分析，白走两轮弯路。本版：
//     · 没有 fork，没有无界 while（全部改成有界等待）
//     · 采集循环极简：对齐周期末 → 每 32 拍各记一次
//     · 硬超时兜底，保证一定会 $finish
//=============================================================================

`timescale 1ns/1ps

module tb_tdm_equiv;

    localparam NV      = 4;
    localparam NPART   = 8;
    localparam NSLOT   = NV * NPART;      // 32
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam ENV_W   = 16;
    localparam OUT_W   = 24;
    localparam NPER    = NSLOT;           // 每样本 32 拍
    localparam N_SAMP  = 2500;
    localparam CLK_HALF= 50;              // 周期 100 ns

    // 隔离开关：0 = 关掉包络，只比"相位→查表→乘幅度→累加"这条纯数据通路
    localparam ENV_ON  = 1'b1;
    // 活跃时隙掩码：只让被置位的时隙有幅度。
    //   把 32 个时隙压到 2 个，任何"时隙间串扰"都会变得完全可读 ——
    //   比在 32 个时隙里猜要快得多。
    localparam [NSLOT-1:0] ACTIVE = 32'hFFFFFFFF;  // 只 0、1 号（十六进制便于脚本批量改）
    // 频谱模式：1 = 每个时隙给一个互不相同的频率，便于在频谱上直接数峰。
    //   inc = 21000×(slot+1) → 频率 391 Hz × (slot+1)，即 391~12512 Hz。
    //   间隔必须远大于 FFT 分辨率（fs/N = 312500/2500 = 125 Hz），
    //     否则峰挤在一起根本数不出来 —— 第一版就是栽在这里。
    localparam SPECTRUM = 1'b0;
    function [PHASE_W-1:0] inc_of; input integer sl;
        begin
            if (SPECTRUM) inc_of = 24'd80000 * (sl + 1);
            else          inc_of = base_of(sl / NPART) * ((sl % NPART) + 1);
        end
    endfunction

    // 0 号时隙幅度 200、1 号幅度 100（两者不同，便于分辨谁串到了谁身上）
    function [AMP_W-1:0] act_amp; input integer s;
        begin
            if (ACTIVE[s]) act_amp = (s == 0) ? 8'd200 : 8'd100;
            else           act_amp = 8'd0;
        end
    endfunction

    reg clk, rst_n;
    reg t_clr, t_pclr;
    reg t_load_en;
    reg [4:0] t_load_slot;
    reg [PHASE_W-1:0] t_load_inc;
    // 每时隙包络参数 {s_lvl[15:0], d_m[1:0], d_k[4:0]}
    //   默认值必须与 tdm_engine 的端口默认一致，回归才成立
    reg [22:0]        t_load_epar;
    reg [AMP_W-1:0]   t_load_amp;
    reg t_load_gate;

    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 共用 sample_en：每 NPER 拍一次，两侧严格同源
    //-------------------------------------------------------------------------
    reg [7:0] pc;
    wire sample_en = (pc == 8'd0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)       pc <= 8'd0;
        // t_pclr 期间【不能】按住 pc：pclr_hold 靠 sample_en 释放，
        //   按住 pc 就没有 sample_en，冻结永远解除不了
        //   （实测症状：全程输出卡死，不符 2449/2461）。
        //   冻结本身是幂等的，不需要靠"停表"来保证时长。
        else              pc <= (pc == NPER-1) ? 8'd0 : pc + 8'd1;
    end

    //-------------------------------------------------------------------------
    // 共用参数：4 声部 × 8 泛音
    //   fs = 1/(32 × 100ns) = 312500 Hz，inc = round(f × 2^24 / 312500)
    //-------------------------------------------------------------------------
    localparam [PHASE_W-1:0] B0 = 24'd11811;   // 220.00 Hz
    localparam [PHASE_W-1:0] B1 = 24'd14881;   // 277.18 Hz
    localparam [PHASE_W-1:0] B2 = 24'd17698;   // 329.63 Hz
    localparam [PHASE_W-1:0] B3 = 24'd23622;   // 440.00 Hz

    function [PHASE_W-1:0] base_of; input integer v;
        begin
            case (v)
                0: base_of = B0;
                1: base_of = B1;
                2: base_of = B2;
                default: base_of = B3;
            endcase
        end
    endfunction

    function [AMP_W-1:0] amp_of; input integer k;
        begin
            case (k)
                0: amp_of = 8'd200;  1: amp_of = 8'd120;
                2: amp_of = 8'd80;   3: amp_of = 8'd60;
                4: amp_of = 8'd45;   5: amp_of = 8'd36;
                6: amp_of = 8'd30;   default: amp_of = 8'd26;
            endcase
        end
    endfunction

    wire [NV*NPART*PHASE_W-1:0] inc_all;
    wire [NV*NPART*AMP_W-1:0]   amp_all;

    genvar gv, gp;
    generate
        for (gv = 0; gv < NV; gv = gv + 1) begin : G_V
            for (gp = 0; gp < NPART; gp = gp + 1) begin : G_P
                assign inc_all[(gv*NPART+gp)*PHASE_W +: PHASE_W] = inc_of(gv*NPART+gp);
                assign amp_all[(gv*NPART+gp)*AMP_W +: AMP_W] = act_amp(gv*NPART+gp);
            end
        end
    endgenerate

    localparam [ENV_W-1:0] A_INC  = 16'd117;
    localparam [ENV_W-1:0] D_INC  = 16'd1;
    localparam [ENV_W-1:0] S_LVL  = 16'd22938;
    localparam [ENV_W-1:0] R_INC  = 16'd1;
    localparam [ENV_W-1:0] CUTOFF = 16'd100;

    //-------------------------------------------------------------------------
    // 每时隙包络参数（构造泛音结构）—— 测试图案
    //   EPAR_MODE = 0 : 全部默认值 {s_lvl=22938, d_m=3, d_k=12}
    //                   → 与全并行完全等价，【回归用】必须逐位一致
    //   EPAR_MODE = 1 : 泛音号每 +1，d_k 减 1 → 衰减时间常数【减半】
    //                   基频 τ≈2^14/3≈5461 拍，最高泛音 τ≈2^7/3≈43 拍
    //                   这就是"钟/马林巴"的频谱演化：高次泛音先死
    //-------------------------------------------------------------------------
    localparam EPAR_MODE = 1'b0;
    localparam [15:0] EPAR_SLVL_DEF = 16'd22938;

    function [22:0] t_epar_of;
        input integer sl;
        reg [4:0] dk;
        begin
            if (EPAR_MODE) begin
                // 用位选 + 显式 5 位中间量：直接写 (5'd14 - sl%8) 在拼接里
                // 会因 sl%8 是 32 位整数而"宽度不确定"，iverilog 直接报错。
                dk = 5'd14 - {2'b00, sl[2:0]};
                // 衰减终点也逐泛音：s_lvl 每高一个泛音减半
                //   → 高次泛音不是"衰减到某个电平停住"，而是【衰减到接近静音】
                //   这才是钟/马林巴的机理：撞击瞬间频谱很宽，随后高次泛音逐层消失
                t_epar_of = {(EPAR_SLVL_DEF >> {12'b0, sl[2:0]}), 2'd3, dk};
            end
            else
                t_epar_of = {EPAR_SLVL_DEF, 2'd3, 5'd12};
        end
    endfunction

    //-------------------------------------------------------------------------
    // 周期计数与并行侧激励寄存器（2026-10-01）
    //
    //   旧版激励不对称：并行引擎的 inc/amp/gate 是【组合连线、上电即有效】，
    //   TDM 的参数却要经 load 口装载（落在第 3~4 个样本周期）——两边连
    //   "音符从哪一拍开始"都对不上，起音段逐位比对从根上不成立。
    //
    //   新语义：两边都是【显式音符事件，样本边界生效】——
    //     · TDM：period 0 内一次性装载 inc/amp/epar/gate=1
    //              （引擎内部样本边界对齐，全部时隙在 period 1 统一生效）
    //     · 并行 ：stim_inc 在 period==0 的 sample_en 边沿置起（period 1 起有效）
    //              stim_gate 在 period==1 的边沿置起（period 2 起有效）
    //              → 门沿相对相位推进的间隔与 TDM 严格一致（各差 1 个周期）
    //-------------------------------------------------------------------------
    reg [15:0] period;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)         period <= 16'd0;
        else if (sample_en) period <= period + 16'd1;
    end

    localparam integer STIM_INC_AT  = 0;   // period==X 的 sample_en 边沿置起
    localparam integer STIM_GATE_AT = 1;

    reg stim_inc, stim_gate;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stim_inc  <= 1'b0;
            stim_gate <= 1'b0;
        end
        else if (sample_en) begin
            if (period == STIM_INC_AT)  stim_inc  <= 1'b1;
            if (period == STIM_GATE_AT) stim_gate <= 1'b1;
        end
    end

    wire [NV*NPART*PHASE_W-1:0] par_inc = stim_inc ? inc_all : {(NV*NPART*PHASE_W){1'b0}};
    wire [NV*NPART*AMP_W-1:0]   par_amp = stim_inc ? amp_all : {(NV*NPART*AMP_W){1'b0}};

    //-------------------------------------------------------------------------
    // 并行引擎（黄金参考）
    //-------------------------------------------------------------------------
    wire signed [OUT_W-1:0] par_sample;
    wire [NV*OUT_W-1:0]     par_voice;

    synth_top #(
        .NV(NV), .NPART(NPART), .PHASE_W(PHASE_W),
        .AMP_W(AMP_W), .ENV_W(ENV_W), .OUT_W(OUT_W)
    ) u_par (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .inc_all(par_inc), .amp_all(par_amp),
        .gate({NV{stim_gate}}),
        .env_en(ENV_ON),
        .a_inc(A_INC), .d_inc(D_INC), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(S_LVL), .r_inc(R_INC), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(CUTOFF), .exp_mode(1'b1),
        .mix_gain_up(3'd0), .mix_shift(2'd0),
        .sample_out(par_sample), .voice_out(par_voice)
    );

    wire signed [OUT_W+3:0] par_sum =
        $signed(par_voice[0*OUT_W +: OUT_W]) +
        $signed(par_voice[1*OUT_W +: OUT_W]) +
        $signed(par_voice[2*OUT_W +: OUT_W]) +
        $signed(par_voice[3*OUT_W +: OUT_W]);

    //-------------------------------------------------------------------------
    // TDM 引擎（被测对象）
    //-------------------------------------------------------------------------
    wire signed [OUT_W-1:0] tdm_sample;
    wire [31:0]             tdm_sum;
    wire [4:0]              tdm_slot;

    tdm_engine #(
        .NSLOT(NSLOT), .PHASE_W(PHASE_W), .AMP_W(AMP_W),
        .ENV_W(ENV_W), .OUT_W(OUT_W), .GAIN_UP(0), .SHIFT(0)
    ) u_tdm (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en), .gate_in(1'b1),
        .clr(t_clr), .pclr(t_pclr),
        .load_en(t_load_en), .load_slot(t_load_slot),
        .load_inc(t_load_inc), .load_amp(t_load_amp), .load_gate(t_load_gate),
        .load_epar(t_load_epar),
        .load_gq(18'sd0),                 // 表情调制关闭（本测试只验数据通路）
        .pmod_cfg(58'd0),                 // ★ 58'd0 = 两开关全关 → poff ≡ 0
        .env_en(ENV_ON),
        .a_inc(A_INC), .d_inc(D_INC), .d_m(2'd3), .d_k(5'd12),
        .s_lvl(S_LVL), .r_inc(R_INC), .r_m(2'd3), .r_k(5'd13),
        .env_cutoff(CUTOFF), .exp_mode(1'b1),
        .sample_out(tdm_sample), .sum_raw(tdm_sum), .slot_dbg(tdm_slot)
    );

    //-------------------------------------------------------------------------
    integer fpar, ftdm, fdbg;
    integer i, s, k;

    // 硬超时兜底：仿真必须有确定的终止条件
    initial begin
        #50_000_000;
        $display("[TIMEOUT] 到达仿真时间上限，强制结束");
        $finish;
    end

    // 有界等待：最多等 maxc 拍，返回是否等到
    task wait_pc; input [7:0] v; input integer maxc; integer c; integer ok;
        begin
            ok = 0;
            for (c = 0; c < maxc; c = c + 1) begin
                @(posedge clk);
                if (pc === v) begin ok = 1; c = maxc; end
            end
            if (!ok) $display("[WARN] 等待 pc==%0d 超时", v);
        end
    endtask

    // 必须按 TDM 自己的时隙计数器对齐，不能按 pc！
    //   clr / pclr 期间 pc 被按住、而 sc 仍在走 → 两者会失步。
    //   按 pc 对齐就会采到 TDM 周期里的任意位置（部分和），
    //   表现为"输出缓慢单调爬升"的假象 —— 这个坑让我误判过一轮。
    task wait_slot; input [4:0] v; input integer maxc; integer c; integer ok;
        begin
            ok = 0;
            for (c = 0; c < maxc; c = c + 1) begin
                @(posedge clk);
                if (tdm_slot === v) begin ok = 1; c = maxc; end
            end
            if (!ok) $display("[WARN] 等待 slot==%0d 超时", v);
        end
    endtask

    initial begin
        rst_n = 1'b0;
        t_clr = 1'b0; t_pclr = 1'b0;
        // t_clr/t_pclr 不使用（引擎里已无这两条通路）
        // boost_en 已于 2026-10-01 从引擎删除：它要补的"4 周期滞后"
        //   真身是【累加窗口跨两代状态】，现已修复。此处不再有 t_boost。
        t_load_en = 1'b0; t_load_slot = 5'd0;
        t_load_inc = 24'd0; t_load_amp = 8'd0; t_load_gate = 1'b1;
        t_load_epar = {16'd22938, 2'd3, 5'd12};   // = EPAR_DEF（默认，回归用）

        repeat (8) @(posedge clk);
        rst_n = 1'b1;

        $display("==============================================");
        $display(" TDM = 全并行  逐位一致 黄金参考测试");
        $display(" NSLOT=%0d  fs=%0d Hz  ENV_ON=%b", NSLOT, 312500, ENV_ON);
        $display(" 音符事件：period 0 装载（样本边界对齐）");
        $display("==============================================");

        //---------------------------------------------------------------------
        // 1) 等到 period 0 的 sc==0，把 32 个时隙的
        //    inc / amp / epar / gate=1 一次装载完毕（恰好占满一个样本周期）。
        //    引擎内部做样本边界对齐：全部时隙在 period 1 统一生效。
        //    上电寂静（门初值 0）—— 起音只来自这次装载的 0→1 门沿。
        //---------------------------------------------------------------------
        wait_slot(0, NSLOT * 2);
        for (s = 0; s < NSLOT; s = s + 1) begin
            @(negedge clk);
            t_load_en   = 1'b1;
            t_load_slot = s[4:0];
            t_load_inc  = inc_of(s);
            t_load_amp  = act_amp(s);
            t_load_gate = 1'b1;
            t_load_epar = t_epar_of(s);
        end
        @(negedge clk);
        t_load_en = 1'b0;

        t_pclr  = 1'b0;   // pclr 预置分支已删除（第二十三轮结论：自伤）

        //---------------------------------------------------------------------
        // 2) 采集：从 period 1（音符生效的第一个周期）起，每一拍都记下来
        //    （带时隙号），由 Python 挑出 slot==NSLOT-1 的行并做延迟搜索。
        //    起音段不再跳过 —— 它正是本次修复的验收对象。
        //---------------------------------------------------------------------
        fpar = $fopen("par_sum.txt", "w");
        ftdm = $fopen("tdm_sum.txt", "w");
        if (fpar == 0 || ftdm == 0) begin
            $display("[ERROR] 打不开输出文件");
            $finish;
        end

        for (k = 0; k < N_SAMP * NPER; k = k + 1) begin
            @(posedge clk); #1;
            $fdisplay(ftdm, "%0d %0d %0d %0d",
                      tdm_slot, $signed(tdm_sum),
                      u_tdm.env_mem[0],
                      u_par.G_VOICE[0].u_voice.env_lvl_q[0]);
            if (sample_en) $fdisplay(fpar, "%0d", par_sum);
        end

        $fclose(fpar);
        $fclose(ftdm);
        $display(" 两侧各采 %0d 个样本 -> par_sum.txt / tdm_sum.txt", N_SAMP);

        //---------------------------------------------------------------------
        // 5) 内部诊断：再抓一个周期的逐拍明细（供人工核对算术）
        //---------------------------------------------------------------------
        fdbg = $fopen("tdm_dbg.txt", "w");
        for (i = 0; i < NPER + 6; i = i + 1) begin
            @(posedge clk); #1;
            $fdisplay(fdbg, "sc=%0d slot=%0d ph1=%0d inc1=%0d env1=%0d envn=%0d amp1=%0d ampe=%0d sin=%0d prod=%0d accn=%0d",
                u_tdm.sc, u_tdm.slot_addr, u_tdm.ph1, u_tdm.inc1,
                u_tdm.env1, u_tdm.env_n, u_tdm.amp1, u_tdm.amp_eff,
                u_tdm.sin3, u_tdm.prod4, u_tdm.acc_next);
        end
        $fclose(fdbg);
        $display(" 逐拍明细 -> tdm_dbg.txt");
        $display("==============================================");
        $finish;
    end

endmodule
