//=============================================================================
// tb_strike.v —— 激发模式（strike / hybrid）的判据
//
// 这个测试台存在的理由
// --------------------
// strike 的梯度公式有【两份实现】：
//   · Python：articulation_v2.part_ms / exp_steps（上位机 GUI 拿它显示时长）
//   · Verilog：note_map_owned 的 k_curve_off/strike_d_k + osc_env 的衰减推进
// `>>4` 或"钳到 0"任一处写错，GUI 说 340 ms、板子发 1.9 ms —— 差两个数量级，
// 而两边的单元测试各自都是绿的（只跟自己比）。所以本测试台读
// `strike_cases.hex` / `strike_expect.hex`（由 tools/gen_strike_vectors.py
// 从 Python 侧算出）逐项比对。这就是规格 §6 验收第 8 条的机器化版本。
//
// 判据分组
// --------
//   A  梯度公式：160 组 (base,curve,d_m,s_lvl,k) 的 d_k / s_lvl_q15 与 Python 一致
//   B  衰减步数：把 A 得到的 epar 灌进真的 osc_env，数拍到 s_lvl 的拍数，
//                与 Python 的 exp_steps 一致（这是"两处实现"的闭环）
//   C  enable=0 等价性：epar 逐位等于 preset_part.hex 里的原值
//   D  掩码语义：mask=0x0003 只改 k=0,1；mask=0 与 enable=0 等价
//   E  自动释放：strike 音到点回收时隙（active 清零）；sustain 音不回收；
//                auto_rel=0 不回收；32 个音占满后回收完仍能再发声
//   F  env 词：strike 只把 DEC 段 shift（[14:11]）清零，ATK/REL 原样保留
//=============================================================================
`timescale 1ns/1ps

module tb_strike;

    localparam NG      = 32;
    localparam P       = 16;
    localparam NB      = 7;
    localparam PHASE_W = 24;
    localparam AMP_W   = 8;
    localparam OWNER_W = 13;

    // 仿真时钟 10 ns（逻辑判据与绝对时间无关）。
    // ★ 释放计时器用 REL_DIV_LOG2=9（不是产品的 10）：
    //   一格 = 2^(9+9) = 262144 拍。用 10 会到 524288 拍/格，跑 32 个音
    //   再等好几格就太慢。**机制完全相同，只是分频位宽不同**；
    //   产品配置（10）的时间常数在 B9 里用算术核对。
    localparam REL_LOG2 = 9;
    localparam CLK_NS   = 10;
    localparam CELL_CLK = 1 << (9 + REL_LOG2);   // 一格多少拍

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #(CLK_NS/2) clk = ~clk;

    //---- 事件口 ----
    reg         ev_valid = 1'b0;
    reg         ev_on    = 1'b0;
    reg  [NB-1:0] ev_note = 7'd0;
    reg  [AMP_W-1:0] ev_vel = 8'd200;
    reg         ev_owned = 1'b0;
    reg  [OWNER_W-1:0] ev_instance = 13'd0;

    //---- 音色/配置口 ----
    reg  [1:0]  preset = 2'd0, own_preset = 2'd0;
    reg         cfg_valid = 1'b0, cfg_commit = 1'b0;
    reg  [1:0]  cfg_slot = 2'd0;
    reg  [3:0]  cfg_part = 4'd0;
    reg  [87:0] cfg_word = 88'd0;

    //---- 其它输入（全部取"恒等/关"）----
    reg  signed [9:0] tilt_vbias = 10'sd0;
    reg  [7:0]  tilt_vgain = 8'd0;
    reg  [8:0]  vel_vscale = 9'd256;
    reg  [7:0]  tilt = 8'h70;
    reg         spec_commit = 1'b0, spec_we = 1'b0;
    reg  [3:0]  spec_addr = 4'd0;
    reg  [7:0]  spec_wdata = 8'd0;
    reg         spec_replace = 1'b0;
    reg  [15:0] pad_mask = 16'd0;
    reg         refresh_valid = 1'b0;
    reg  [NB-1:0] rf_lo = 7'd0;
    reg  [NB:0]   rf_hi = 8'd0;

    //---- 激发模式寄存器（被测）----
    reg         artic_enable = 1'b0;
    reg  [15:0] artic_mask = 16'hFFFF;
    reg  [1:0]  strike_d_m = 2'd3;
    reg  [4:0]  strike_d_k_base = 5'd14;
    reg  [3:0]  strike_d_k_curve = 4'd10;
    reg  [3:0]  strike_s_lvl = 4'd2;
    reg         strike_auto_rel = 1'b0;
    reg  [19:0] strike_hold_ticks = 20'd1024;

    //---- DUT 输出 ----
    wire        result_valid, result_owned, result_on, result_success;
    wire [OWNER_W-1:0] result_instance;
    wire [4:0]  result_group;
    wire        cfg_ready, cfg_applied, cfg_error;
    wire [3:0]  cfg_enabled_status;
    wire        load_en;
    wire [8:0]  load_slot;
    wire [PHASE_W-1:0] load_inc;
    wire [AMP_W-1:0]   load_amp;
    wire        load_gate;
    wire [7:0]  load_start_tag;
    wire [22:0] load_epar;
    wire [39:0] load_env;
    wire signed [17:0] load_gq;
    wire        busy, ev_ack;
    wire [NG-1:0] active;
    wire        voice_valid, voice_on;
    wire [4:0]  voice_group;
    wire [NB-1:0] voice_note;

    note_map_owned #(
        .SERIAL_CUSTOM_LEGACY(0), .NG(NG), .P(P), .PHASE_W(PHASE_W), .AMP_W(AMP_W),
        .NB(NB), .NPRE(4), .GLIDE_EN(1'b0), .SPEC_STAGED(0),
        .OWNED_EVENTS(1), .OWNER_W(OWNER_W), .REL_DIV_LOG2(REL_LOG2)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .ev_owned(ev_owned), .ev_instance(ev_instance),
        .result_valid(result_valid), .result_owned(result_owned), .result_on(result_on),
        .result_success(result_success), .result_instance(result_instance),
        .result_group(result_group),
        .preset(preset), .own_preset(own_preset),
        .cfg_valid(cfg_valid), .cfg_commit(cfg_commit), .cfg_slot(cfg_slot),
        .cfg_part(cfg_part), .cfg_word(cfg_word),
        .cfg_ready(cfg_ready), .cfg_applied(cfg_applied), .cfg_error(cfg_error),
        .cfg_enabled_status(cfg_enabled_status),
        .tilt_vbias(tilt_vbias), .tilt_vgain(tilt_vgain), .vel_vscale(vel_vscale),
        .tilt(tilt),
        .spec_commit(spec_commit), .spec_we(spec_we), .spec_addr(spec_addr),
        .spec_wdata(spec_wdata), .spec_replace(spec_replace),
        .pad_mask(pad_mask), .refresh_valid(refresh_valid), .rf_lo(rf_lo), .rf_hi(rf_hi),
        .artic_enable(artic_enable), .artic_mask(artic_mask),
        .strike_d_m(strike_d_m), .strike_d_k_base(strike_d_k_base),
        .strike_d_k_curve(strike_d_k_curve), .strike_s_lvl(strike_s_lvl),
        .strike_auto_rel(strike_auto_rel), .strike_hold_ticks(strike_hold_ticks),
        .load_en(load_en), .load_slot(load_slot), .load_inc(load_inc),
        .load_amp(load_amp), .load_gate(load_gate), .load_start_tag(load_start_tag),
        .load_epar(load_epar), .load_env(load_env), .load_gq(load_gq),
        .busy(busy), .ev_ack(ev_ack), .active(active),
        .voice_valid(voice_valid), .voice_on(voice_on),
        .voice_group(voice_group), .voice_note(voice_note)
    );

    //=========================================================================
    // 抓取：装载序列里每个时隙的 epar / env / gate
    //=========================================================================
    reg [22:0] cap_epar [0:P-1];
    reg [39:0] cap_env  [0:P-1];
    reg        cap_gate [0:P-1];
    integer    cap_n;
    always @(posedge clk) if (load_en) begin
        cap_epar[load_slot[3:0]] = load_epar;
        cap_env [load_slot[3:0]] = load_env;
        cap_gate[load_slot[3:0]] = load_gate;
        cap_n = cap_n + 1;
    end

    // 参考：预设表原值（C 组判据用）
    reg [47:0] part_rom [0:63];

    // 向量
    reg [127:0] vcase [0:255];
    reg [127:0] vexp  [0:255];
    integer     vn;

    //=========================================================================
    // 判据统计
    //=========================================================================
    integer n_ok = 0, n_bad = 0;
    reg [8*256-1:0] msg;   // ★ 256 字节：中文消息按 UTF-8 三字节/字算，96 字节会被截在半个字上（第一版就是这么花屏的）

    task chk;
        input        cond;
        input [8*256-1:0] text;
        begin
            if (cond) begin
                n_ok = n_ok + 1;
                $display("[OK]   %0s", text);
            end else begin
                n_bad = n_bad + 1;
                $display("[FAIL] %0s", text);
            end
        end
    endtask

    //=========================================================================
    // 发一个音符事件，等它装完 16 个时隙
    //=========================================================================
    task note_on;
        input [NB-1:0] nt;
        input          owned;
        input [OWNER_W-1:0] inst;
        begin
            cap_n = 0;
            ev_note = nt; ev_on = 1'b1; ev_owned = owned; ev_instance = inst;
            ev_valid = 1'b1;
            @(posedge clk);
            while (!ev_ack) @(posedge clk);
            ev_valid = 1'b0;
            while (busy) @(posedge clk);
            repeat (4) @(posedge clk);
        end
    endtask

    task note_off;
        input [NB-1:0] nt;
        input          owned;
        input [OWNER_W-1:0] inst;
        begin
            cap_n = 0;
            ev_note = nt; ev_on = 1'b0; ev_owned = owned; ev_instance = inst;
            ev_valid = 1'b1;
            @(posedge clk);
            while (!ev_ack) @(posedge clk);
            ev_valid = 1'b0;
            while (busy) @(posedge clk);
            repeat (4) @(posedge clk);
        end
    endtask

    //=========================================================================
    // 主流程
    //=========================================================================
    integer i, k, ci, base, curve, dm, slvl;
    reg [127:0] cw, ew;
    reg [4:0]   e_dk;
    reg [15:0]  e_q15;
    reg [15:0]  e_st0, e_sts;
    reg [22:0]  want;
    reg         ok_case;

    //---- osc_env 的独立实例（B 组：数衰减拍数）----
    reg  [15:0] oe_lvl, oe_slvl, oe_a_inc, oe_d_inc, oe_r_inc, oe_cutoff;
    reg  [2:0]  oe_stg;
    reg  [1:0]  oe_dm, oe_rm;
    reg  [4:0]  oe_dk, oe_rk;
    reg         oe_exp;
    wire [15:0] oe_lvl_o;
    wire [2:0]  oe_stg_o;

    osc_env #(.ENV_W(16), .STG_W(3)) u_oe (
        .lvl_i(oe_lvl), .stg_i(oe_stg), .trig_on(1'b0), .trig_rel(1'b0),
        .a_inc(oe_a_inc), .d_inc(oe_d_inc), .d_m(oe_dm), .d_k(oe_dk),
        .s_lvl(oe_slvl), .r_inc(oe_r_inc), .r_m(oe_rm), .r_k(oe_rk),
        // 双段衰减显式关闭。★ 不接会悬空成 z ⇒ 比较变 x ⇒ 整个包络算成 x，
        //   而 iverilog 不报错（缺端口只是警告）。这一条就是这么被抓到的：
        //   加完端口第一次跑回归，B 组全部 "steps 40000"（永远走不到 SUS）。
        .d2_lvl(16'd0), .d2_k(5'd0),
        .cutoff(oe_cutoff), .exp_mode(oe_exp),
        .lvl_o(oe_lvl_o), .stg_o(oe_stg_o)
    );

    initial begin
        $readmemh("preset_part.hex", part_rom);
        $readmemh("strike_cases.hex", vcase);
        $readmemh("strike_expect.hex", vexp);
        // 生成器把文件补零到 256 行 ⇒ 用"最后一个非零行"数有效条数
        vn = 0;
        for (i = 0; i < 256; i = i + 1)
            if (vcase[i] !== 128'h0) vn = i + 1;

        $display("== tb_strike: %0d 组向量, 释放计时格 = %0d 拍 = %0.3f ms @27MHz",
                 vn, CELL_CLK, CELL_CLK * 1000.0 / 27000.0);

        cap_n = 0;
        rst_n = 1'b0;
        repeat (8) @(posedge clk);
        rst_n = 1'b1;
        repeat (8) @(posedge clk);

        //=================================================================
        // A + B：梯度公式与衰减步数，与 Python 向量逐项比对
        //=================================================================
        $display("\n-- A/B: 梯度公式与衰减拍数（对照 tools/gen_strike_vectors.py）");
        ok_case = 1'b1;
        for (ci = 0; ci < vn / P; ci = ci + 1) begin
            cw = vcase[ci*P];
            base  = cw[127:112];
            curve = cw[111:96];
            dm    = cw[95:80];
            slvl  = cw[79:64];

            artic_enable      = 1'b1;
            artic_mask        = 16'hFFFF;
            strike_d_k_base   = base[4:0];
            strike_d_k_curve  = curve[3:0];
            strike_d_m        = dm[1:0];
            strike_s_lvl      = slvl[3:0];
            strike_auto_rel   = 1'b0;

            note_on(7'd40, 1'b0, 13'd0);

            for (k = 0; k < P; k = k + 1) begin
                ew  = vexp[ci*P + k];
                e_dk  = ew[127:112];
                e_q15 = ew[111:96];
                e_st0 = ew[95:80];
                e_sts = ew[79:64];
                want  = {e_q15, dm[1:0], e_dk};

                //--- A: epar 逐位 ---
                if (cap_epar[k] !== want) begin
                    ok_case = 1'b0;
                    $display("   [A] 差 base=%0d curve=%0d m=%0d s=%0d k=%0d: got %06x want %06x",
                             base, curve, dm, slvl, k, cap_epar[k], want);
                end

                //--- B: 用这个 epar 跑真 osc_env，数拍到 s_lvl 的拍数 ---
                oe_lvl    = 16'd32768;
                oe_stg    = 3'd2;                 // ST_DEC
                oe_slvl   = e_q15;
                oe_dm     = dm[1:0];
                oe_dk     = e_dk;
                oe_a_inc  = 16'd0;
                oe_d_inc  = 16'd0;
                oe_r_inc  = 16'd0;
                oe_rm     = 2'd0;
                oe_rk     = 5'd0;
                oe_cutoff = 16'd0;
                oe_exp    = 1'b1;
                // ★ 必须先等一拍：oe_stg_o 是组合输出，上一轮循环结束时它是
                //   ST_SUS；不等的话 while 条件读到的是【旧值】⇒ 每次都立刻退出，
                //   拍数恒为 0（第一版就是这么错的，判据全红但看起来"跑通了"）。
                #1;
                i = 0;
                while (oe_stg_o != 3'd3 && i < 40000) begin   // 跑到 ST_SUS
                    oe_lvl = oe_lvl_o;
                    oe_stg = oe_stg_o;
                    i = i + 1;
                    #1;
                end
                // ★ 再加 1：Python 的 exp_steps 把"落到 s_lvl 的那一步"也计入，
                //   而上面这个循环在"算出 SUS"的那一拍就退出了、没有计入
                //   （第一版差 1 就是这么来的）。落地时补一次。
                if (oe_stg_o == 3'd3) i = i + 1;
                if (i != e_sts) begin
                    ok_case = 1'b0;
                    $display("   [B] 差 base=%0d curve=%0d m=%0d s=%0d k=%0d: steps %0d want %0d",
                             base, curve, dm, slvl, k, i, e_sts);
                end
            end
            note_off(7'd40, 1'b0, 13'd0);
        end
        chk(ok_case, "A/B gradient + decay ticks: all vectors match the Python model");
        $display("   （共 %0d 项 d_k/s_lvl + %0d 项衰减拍数）", vn, vn);

        //=================================================================
        // B9：产品配置（REL_DIV_LOG2=10）的时间常数用算术核对
        //=================================================================
        //   一格 = 2^19 拍；hold=79102 拍 ⇒ [19:10]=77 格 ⇒ 77*1024=78848 拍
        //   78848 / 52734.375 Hz = 1.4949 s（请求 1.500 s，误差 0.34%）
        begin : b9
            localparam integer CELL10 = 1 << 19;
            localparam integer HOLD10 = 79102;
            localparam integer CELLS  = HOLD10 / 1024;
            localparam real    SECS   = CELLS * 1024.0 * 512.0 / 27000000.0;
            chk((CELL10 == 524288) && (CELLS == 77) && (SECS > 1.49) && (SECS < 1.50),
                "B9 shipping config: 524288 clk/cell, hold=79102 ticks -> 77 cells = 1.495 s");
            $display("   （2^19=%0d 拍/格，%0d 格，%0.4f s）", CELL10, CELLS, SECS);
        end

        //=================================================================
        // C：enable=0 时 epar 逐位等于预设表原值
        //=================================================================
        $display("\n-- C: enable=0 等价性（epar 必须等于 preset_part.hex 原值）");
        artic_enable = 1'b0;
        artic_mask   = 16'hFFFF;
        strike_d_k_base  = 5'd14;
        strike_d_k_curve = 4'd10;
        strike_d_m       = 2'd3;
        strike_s_lvl     = 4'd2;
        note_on(7'd52, 1'b0, 13'd0);
        ok_case = 1'b1;
        for (k = 0; k < P; k = k + 1)
            if (cap_epar[k] !== part_rom[0*P + k][22:0]) begin
                ok_case = 1'b0;
                $display("   [C] k=%0d: got %06x want %06x", k,
                         cap_epar[k], part_rom[0*P + k][22:0]);
            end
        chk(ok_case, "C1 enable=0: all 16 partial epar values are bit-identical to the preset table");
        //   ★ 这条同时证明"覆盖确实发生了"——否则 C1 也可能因为两边都是原值而假绿
        chk(cap_epar[0][22:7] == 16'd30000,
            "C2 control: preset0 fundamental s_lvl is 30000 (so C1 really compared originals)");
        note_off(7'd52, 1'b0, 13'd0);

        //=================================================================
        // D：掩码语义
        //=================================================================
        $display("\n-- D: 掩码语义");
        //  D1  enable=1 & mask=0 必须与 enable=0 完全一致
        artic_enable = 1'b1;
        artic_mask   = 16'h0000;
        note_on(7'd53, 1'b0, 13'd0);
        ok_case = 1'b1;
        for (k = 0; k < P; k = k + 1)
            if (cap_epar[k] !== part_rom[0*P + k][22:0]) ok_case = 1'b0;
        chk(ok_case, "D1 enable=1 and mask=0: bit-identical to enable=0 (the mask is the only switch)");
        note_off(7'd53, 1'b0, 13'd0);

        //  D2  mask=0x0003 ⇒ 只有 k=0,1 走 strike，k>=2 保持原值
        artic_mask = 16'h0003;
        strike_d_k_base  = 5'd14;
        strike_d_k_curve = 4'd10;
        strike_d_m       = 2'd3;
        strike_s_lvl     = 4'd2;
        note_on(7'd54, 1'b0, 13'd0);
        ok_case = 1'b1;
        for (k = 0; k < P; k = k + 1) begin
            if (k < 2) begin
                want = {16'd4096, 2'd3, 5'd14};      // 余音 + 基准 d_k
                if (cap_epar[k] !== want) begin
                    ok_case = 1'b0;
                    $display("   [D2] k=%0d 应走 strike: got %06x want %06x",
                             k, cap_epar[k], want);
                end
            end
            else if (cap_epar[k] !== part_rom[0*P + k][22:0]) begin
                ok_case = 1'b0;
                $display("   [D2] k=%0d 不该被改: got %06x want %06x",
                         k, cap_epar[k], part_rom[0*P + k][22:0]);
            end
        end
        chk(ok_case, "D2 mask=0x0003: only k=0,1 take strike, k>=2 keep the preset values");
        note_off(7'd54, 1'b0, 13'd0);

        //  D3  s_lvl=0 ⇒ 16 个泛音都不留余音（含 k<4）
        artic_mask       = 16'hFFFF;
        strike_s_lvl     = 4'd0;
        note_on(7'd55, 1'b0, 13'd0);
        ok_case = 1'b1;
        for (k = 0; k < P; k = k + 1)
            if (cap_epar[k][22:7] !== 16'd0) ok_case = 1'b0;
        chk(ok_case, "D3 s_lvl=0: all 16 partials get s_lvl=0 (pure percussive, no tail)");
        note_off(7'd55, 1'b0, 13'd0);

        //=================================================================
        // E：自动释放（回收时隙）
        //=================================================================
        $display("\n-- E: 自动释放（strike_auto_rel）");
        artic_enable     = 1'b1;
        artic_mask       = 16'hFFFF;
        strike_s_lvl     = 4'd2;
        strike_auto_rel  = 1'b1;
        strike_hold_ticks = 20'd512;           // = 1 格（512 = 2^REL_DIV_LOG2）

        //  E1 按下 32 个 strike 音（不同音高，各占一组）
        for (i = 0; i < NG; i = i + 1) note_on(7'd40 + i[6:0], 1'b0, 13'd0);
        chk(active == {NG{1'b1}}, "E1 hold 32 strike notes: all 32 groups occupied (polyphony full)");

        //  E2 不松手，等 1 格 + 余量 ⇒ active 必须自己清零
        repeat (CELL_CLK + 4096) @(posedge clk);
        chk(active == {NG{1'b0}},
            "E2 after hold expires active self-clears (slot leak fixed, no note-off needed)");

        //  E3 回收后还能再发声（这就是"第 33 个键仍能响"）
        note_on(7'd80, 1'b0, 13'd0);
        chk(active != {NG{1'b0}}, "E3 after recycling, a new note still sounds (the 33rd key is not mute)");
        note_off(7'd80, 1'b0, 13'd0);

        //  E4  auto_rel=0 ⇒ 不回收
        strike_auto_rel = 1'b0;
        for (i = 0; i < NG; i = i + 1) note_on(7'd40 + i[6:0], 1'b0, 13'd0);
        repeat (CELL_CLK + 4096) @(posedge clk);
        chk(active == {NG{1'b1}}, "E4 auto_rel=0: still not recycled after hold expires (physically honest)");
        for (i = 0; i < NG; i = i + 1) note_off(7'd40 + i[6:0], 1'b0, 13'd0);

        //  E5  sustain 音（enable=0）不挂自动释放
        strike_auto_rel = 1'b1;
        artic_enable    = 1'b0;
        for (i = 0; i < NG; i = i + 1) note_on(7'd40 + i[6:0], 1'b0, 13'd0);
        repeat (CELL_CLK + 4096) @(posedge clk);
        chk(active == {NG{1'b1}}, "E5 sustain notes (enable=0) are never auto-released (no collateral damage)");
        for (i = 0; i < NG; i = i + 1) note_off(7'd40 + i[6:0], 1'b0, 13'd0);

        //  E6  演奏者自己松手 ⇒ 立刻回收（不等 hold）
        artic_enable = 1'b1;
        strike_hold_ticks = 20'd4096;           // 8 格，远长于测试等待
        note_on(7'd60, 1'b0, 13'd0);
        note_off(7'd60, 1'b0, 13'd0);
        chk(active == {NG{1'b0}}, "E6 manual note-off recycles immediately (auto-release never delays it)");

        //=================================================================
        // F：env 词的 DEC shift 清零（runtime 音色表路径）
        //=================================================================
        $display("\n-- F: env 词（strike 只清 DEC 段 shift）");
        //  写一个 slot 0 的音色：env = 0x0981f452eb
        //    [35]    custom = 1
        //    [34:31] ATK shift = 3
        //    [30:15] a_inc = 1000        ← custom=1 时 instrument_table 要求非 0
        //    [14:11] DEC shift = 10      ← strike 要把它清零
        //    [10:7]  REL shift = 5
        //    [6:5]   r_m = 3             ← custom=1 时要求非 0
        //    [4:0]   r_k = 11
        //  epar = 0x00006E（s_lvl=0, d_m=3, d_k=14），ratio=0x0100, amp=0x80
        for (i = 0; i < P; i = i + 1) begin
            cfg_valid = 1'b1; cfg_commit = 1'b0; cfg_slot = 2'd0;
            cfg_part = i[3:0]; cfg_word = 88'h0981f452eb01008000006E;
            @(posedge clk); @(posedge clk);
        end
        cfg_commit = 1'b1;
        @(posedge clk); @(posedge clk);
        cfg_valid = 1'b0; cfg_commit = 1'b0;
        repeat (4) @(posedge clk);
        chk(cfg_error == 1'b0, "F0 instrument table write accepted (88-bit word passes validation)");
        chk(cfg_enabled_status[0] == 1'b1,
            "F0b slot0 enabled bit set after commit (else F1/F2 would be false-green)");

        //  F1  enable=0 ⇒ env 原样（DEC shift 还是 10）
        artic_enable = 1'b0;
        note_on(7'd60, 1'b1, 13'd1);
        ok_case = 1'b1;
        for (k = 0; k < P; k = k + 1)
            if (cap_env[k] !== 40'h0981f452eb) begin
                ok_case = 1'b0;
                if (k < 2) $display("   [F1] k=%0d: got %010x want 0981f452eb", k, cap_env[k]);
            end
        chk(ok_case, "F1 enable=0: env word passed through untouched (DEC shift stays 10)");
        note_off(7'd60, 1'b1, 13'd1);

        //  F2  enable=1 ⇒ 只把 [14:11] 清零，其余位不动
        artic_enable = 1'b1;
        artic_mask   = 16'hFFFF;
        note_on(7'd61, 1'b1, 13'd2);
        ok_case = 1'b1;
        for (k = 0; k < P; k = k + 1)
            if (cap_env[k] !== 40'h0981f402eb) begin
                ok_case = 1'b0;
                if (k < 2) $display("   [F2] k=%0d: got %010x want 0981f402eb", k, cap_env[k]);
            end
        chk(ok_case, "F2 enable=1: DEC shift zeroed, all other env bits untouched (only 4 bits move)");
        note_off(7'd61, 1'b1, 13'd2);

        //=================================================================
        $display("\n==================================================");
        if (n_bad == 0)
            $display(" PASS —— %0d 项检查全部通过", n_ok);
        else
            $display(" FAIL —— %0d 项失败 / %0d 项通过", n_bad, n_ok);
        $display("==================================================");
        $finish;
    end

endmodule
