`timescale 1ns/1ps
//=============================================================================
// tb_vel_shape —— 力度→音色 这条链路是否真的"有作用"
//
// 背景：2026-10-23 查出一个致命 bug —— reg_bank 里 0x6E（VEL_SENS）没有初值，
//       复位后是 0，而 vscale 的四段映射把 0 解释成"关闭"，
//       于是 vel_shape 输出恒等于输入，力度对音色【完全无影响】。
//
// 本台分两段：
//   A. reg_bank 复位默认值（0x6E=0x80 / 0x6F=0x05 / 0x5C=0x70）
//   B. vel_shape 在 vscale = 0 / 256 / 511 三种设置下的行为差异
//      —— 证明"改成 0x80 之后，力度真的开始影响音色了"
//=============================================================================
module tb_vel_shape;

    //=========================================================================
    // A. reg_bank 复位默认值
    //=========================================================================
    reg         clk = 1'b0;
    reg         rst_n = 1'b0;
    reg         wr_en = 1'b0;
    reg  [7:0]  wr_addr = 8'd0;
    reg  [7:0]  wr_data = 8'd0;
    reg         rd_en = 1'b0;
    reg  [7:0]  rd_addr = 8'd0;
    wire [7:0]  rd_data;
    wire [2047:0] regs_flat;

    //-------------------------------------------------------------------------
    // 两个模块都要例化 —— 这是本测试台最重要的修正
    //
    // 2026-10-23 发现：产品顶层 tdm_top_owned.v:388 例化的是
    // **reg_bank_compact**，不是 reg_bank。而本测试台原来只测 reg_bank，
    // 于是"0x6E 默认 0x80"这条判据在仿真里绿、在板上却是 0x00 ——
    // 因为改的是没被例化的那个模块。
    //
    // 现在：
    //   u_reg  = reg_bank_compact，产品真正在用的（主被测对象）
    //   u_ref  = reg_bank，参考模型（只用来交叉校验默认值是否一致）
    //
    // LIVE 必须与 tdm_top_owned.v 的 REG_LIVE_MASK 逐位一致；
    // tools/check_live_mask.py 会机械核对这一点，防止漂移。
    //-------------------------------------------------------------------------
    localparam [127:0] LIVE = 128'h000bf801fc1f03ff00ff000000000001;

    wire [1023:0] flat_live;
    wire [7:0]    rd_ref;
    reg_bank_compact #(.FLAT_MASK(LIVE)) u_reg (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_data(rd_data),
        .regs_flat(flat_live)
    );

    reg_bank #(.AW(8), .DW(8), .NW(256)) u_ref (
        .clk(clk), .rst_n(rst_n),
        .wr_en(wr_en), .wr_addr(wr_addr), .wr_data(wr_data),
        .rd_en(rd_en), .rd_addr(rd_addr), .rd_data(rd_ref),
        .regs_flat(regs_flat)
    );

    always #18.5 clk = ~clk;

    integer errors = 0;
    integer checks = 0;

    task automatic rd_reg(input [7:0] a, output [7:0] d);
        begin
            @(negedge clk); rd_en = 1'b1; rd_addr = a;
            @(negedge clk); d = rd_data; rd_en = 1'b0;
        end
    endtask

    task automatic wr_reg(input [7:0] a, input [7:0] d);
        begin
            @(negedge clk); wr_en = 1'b1; wr_addr = a; wr_data = d;
            @(negedge clk); wr_en = 1'b0;
        end
    endtask

    // 读"逻辑侧"的值（regs_flat）—— 与回读是两条不同的路
    function [7:0] live_byte(input [7:0] a);
        live_byte = flat_live[a*8 +: 8];
    endfunction

    function [7:0] ref_byte(input [7:0] a);
        ref_byte = regs_flat[a*8 +: 8];
    endfunction

    //=========================================================================
    // B. vel_shape
    //=========================================================================
    reg  [3:0]  vs_vel;
    reg  [3:0]  vs_part;
    reg  [7:0]  vs_base;
    reg  signed [9:0] vs_bias = 10'sd0;
    reg  [7:0]  vs_gain = 8'd0;
    reg  [8:0]  vs_vscale;
    reg  [1:0]  vs_slot = 2'd0;      // 四槽分层 刀1：本 tb 默认只用槽 0；
                                     //   E 组判据会扫 0..3 验证"表 4 份相同时等价"
    wire [7:0]  vs_amp;

    vel_shape u_vs (
        .vel(vs_vel), .slot(vs_slot), .part(vs_part), .base(vs_base),
        .tilt_bias(vs_bias), .tilt_gain(vs_gain),
        .vscale(vs_vscale), .amp(vs_amp)
    );

    integer v, p, nz, nz0, nz15, diff_cnt, ident_cnt;
    reg [7:0] amp_256 [0:15][0:15];
    reg [7:0] amp_0   [0:15][0:15];
    reg [7:0] amp_511 [0:15][0:15];
    reg [7:0] amp_s   [0:15][0:15];
    reg [7:0] d_5c, d_6e, d_6f;
    integer s, slot_diff, slot_checks;

    initial begin
        $dumpfile("tb_vel_shape.vcd");
        $dumpvars(0, tb_vel_shape);

        $display("");
        $display("================================================================");
        $display(" tb_vel_shape —— 0x6E 初值 + 力度对音色的实际影响");
        $display("================================================================");

        //---------------------------------------------------------------------
        $display("");
        $display(" A. 上电默认值（主被测：reg_bank_compact = 产品真正用的）");
        //---------------------------------------------------------------------
        repeat (3) @(posedge clk);
        rst_n = 1'b1;
        repeat (3) @(posedge clk);

        rd_reg(8'h5C, d_5c);
        rd_reg(8'h6E, d_6e);
        rd_reg(8'h6F, d_6f);

        checks = checks + 1;
        if (d_6e !== 8'h80) begin
            $display("   [FAIL] 0x6E 复位值 = 0x%02X，期望 0x80（力度灵敏度中点）", d_6e);
            errors = errors + 1;
        end
        else $display("   A1 0x6E VEL_SENS 复位 = 0x%02X（vscale 256，一等一）   OK", d_6e);

        checks = checks + 1;
        if (d_6f !== 8'h05) begin
            $display("   [FAIL] 0x6F 复位值 = 0x%02X，期望 0x05（每档 32 拍）", d_6f);
            errors = errors + 1;
        end
        else $display("   A2 0x6F VEL_SHIFT 复位 = 0x%02X（每档 32 拍）          OK", d_6f);

        checks = checks + 1;
        if (d_5c !== 8'h70) begin
            $display("   [FAIL] 0x5C 复位值 = 0x%02X，期望 0x70（tilt 恒等）", d_5c);
            errors = errors + 1;
        end
        else $display("   A3 0x5C TILT 复位 = 0x%02X（逐位恒等，未被改动）        OK", d_5c);

        // [A4] 两个模块的默认值必须一致 —— 防止"改了一个忘了另一个"
        checks = checks + 1;
        if (ref_byte(8'h6E) !== live_byte(8'h6E) ||
            ref_byte(8'h6F) !== live_byte(8'h6F) ||
            ref_byte(8'h5C) !== live_byte(8'h5C)) begin
            $display("   [FAIL] A4 reg_bank 与 reg_bank_compact 的默认值不一致：");
            $display("          0x6E ref=0x%02X live=0x%02X", ref_byte(8'h6E), live_byte(8'h6E));
            $display("          0x6F ref=0x%02X live=0x%02X", ref_byte(8'h6F), live_byte(8'h6F));
            $display("          0x5C ref=0x%02X live=0x%02X", ref_byte(8'h5C), live_byte(8'h5C));
            errors = errors + 1;
        end
        else $display("   A4 reg_bank 与 reg_bank_compact 默认值一致                 OK");

        // [A5] 逻辑侧可达性：写 0x6F 后 regs_flat 必须跟着变
        //      这条就是 2026-10-23 板上踩到的 DEAD READ 的仿真判据：
        //      0x6F 曾经不在 FLAT_MASK 里，回读 0x05 全绿，但 r_vel_shift 恒 0。
        wr_reg(8'h6F, 8'h07);
        checks = checks + 1;
        if (live_byte(8'h6F) !== 8'h07) begin
            $display("   [FAIL] A5 写 0x6F=0x07 后逻辑侧 = 0x%02X ⇒ 该地址不在 FLAT_MASK 里（DEAD READ）",
                     live_byte(8'h6F));
            errors = errors + 1;
        end
        else $display("   A5 写 0x6F=0x07，逻辑侧跟着变（不在 DEAD READ）           OK");
        wr_reg(8'h6F, 8'h05);   // 还原

        // [A6] 同上，0x6E
        wr_reg(8'h6E, 8'hC8);
        checks = checks + 1;
        if (live_byte(8'h6E) !== 8'hC8) begin
            $display("   [FAIL] A6 写 0x6E=0xC8 后逻辑侧 = 0x%02X（DEAD READ）", live_byte(8'h6E));
            errors = errors + 1;
        end
        else $display("   A6 写 0x6E=0xC8，逻辑侧跟着变                           OK");
        wr_reg(8'h6E, 8'h80);   // 还原

        // [A7] 反向确认：未选中字节即使写了，逻辑侧也必须恒为 0
        //      这条把"两套存储"的陷阱固化成文档 —— 不是 bug，是设计约定。
        wr_reg(8'h55, 8'hA5);
        checks = checks + 1;
        if (live_byte(8'h55) !== 8'h00) begin
            $display("   [FAIL] A7 未选中字节 0x55 的逻辑侧应为 0，实得 0x%02X", live_byte(8'h55));
            errors = errors + 1;
        end
        else $display("   A7 未选中字节 0x55 写入后逻辑侧仍为 0（设计约定）         OK");

        //---------------------------------------------------------------------
        $display("");
        $display(" B. vel_shape 行为（base=200，16 力度 × 16 泛音）");
        //---------------------------------------------------------------------
        vs_base = 8'd200;
        vs_slot = 2'd0;   // B 组一律以 slot0（钢琴/旧表）为基准，E 组拿它当"改造前"

        for (v = 0; v < 16; v = v + 1) begin
            for (p = 0; p < 16; p = p + 1) begin
                vs_vel = v[3:0]; vs_part = p[3:0];
                vs_vscale = 9'd256; #1; amp_256[v][p] = vs_amp;
                vs_vscale = 9'd0;   #1; amp_0[v][p]   = vs_amp;
                vs_vscale = 9'd511; #1; amp_511[v][p] = vs_amp;
            end
        end

        // [B1] vscale=256 ⇒ 与"只用表"一致：vel=15 那一行应接近 base（表 15 行基音=256）
        checks = checks + 1;
        if (amp_256[15][0] !== 8'd200) begin
            $display("   [FAIL] vscale=256 vel=15 part=0 amp=%0d，期望 200（基音恒等）", amp_256[15][0]);
            errors = errors + 1;
        end
        else $display("   B1 vscale=256：基音 amp == base（恒等）              OK");

        // [B2] vscale=0 ⇒ 完全恒等（这就是修复前的状态）
        ident_cnt = 0;
        for (v = 0; v < 16; v = v + 1)
            for (p = 0; p < 16; p = p + 1)
                if (amp_0[v][p] === 8'd200) ident_cnt = ident_cnt + 1;
        checks = checks + 1;
        if (ident_cnt !== 256) begin
            $display("   [FAIL] vscale=0 时只有 %0d/256 项恒等，应全部恒等", ident_cnt);
            errors = errors + 1;
        end
        else $display("   B2 vscale=0：256 项全部 == base（= 修复前的死状态）  OK");

        // [B3] vscale=256 ⇒ 表真的在起作用（存在与 base 不同的项）
        diff_cnt = 0;
        for (v = 0; v < 16; v = v + 1)
            for (p = 0; p < 16; p = p + 1)
                if (amp_256[v][p] !== 8'd200) diff_cnt = diff_cnt + 1;
        checks = checks + 1;
        if (diff_cnt < 100) begin
            $display("   [FAIL] vscale=256 只有 %0d 项偏离 base，力度几乎不起作用", diff_cnt);
            errors = errors + 1;
        end
        else
            $display("   B3 vscale=256：%0d/256 项偏离 base ⇒ 力度影响音色    OK", diff_cnt);

        // [B4] 有效泛音数随力度增加（钢琴特征之一）
        nz0 = 0; nz15 = 0;
        for (p = 0; p < 16; p = p + 1) begin
            if (amp_256[0][p]  != 8'd0) nz0  = nz0  + 1;
            if (amp_256[15][p] != 8'd0) nz15 = nz15 + 1;
        end
        checks = checks + 1;
        if (nz15 <= nz0) begin
            $display("   [FAIL] vel15 有效泛音 %0d 不多于 vel0 的 %0d", nz15, nz0);
            errors = errors + 1;
        end
        else
            $display("   B4 有效泛音：vel0 = %0d 条，vel15 = %0d 条（越多越亮）  OK", nz0, nz15);

        // [B5] 基音任何力度都不置零
        checks = checks + 1;
        nz = 0;
        for (v = 0; v < 16; v = v + 1) if (amp_256[v][0] != 8'd0) nz = nz + 1;
        if (nz !== 16) begin
            $display("   [FAIL] 基音只有 %0d/16 档非零，应恒非零", nz);
            errors = errors + 1;
        end
        else $display("   B5 基音 16 档全部非零（不会按轻就消失）            OK");

        // [B6] 亮度随力度单调上升（频谱重心）
        //   注意：这里不能拿"总能量"当判据 —— vscale 不是音量旋钮。
        //   表的语义是"力度越大，有效泛音越多"，所以 vscale=0（恒等）反而是
        //   16 条泛音全在、总能量最高；打开力度功能后弱奏会变暗、总能量下降。
        //   真正该单调的是【频谱重心】，也就是"听起来多亮"。
        checks = checks + 1;
        begin : cent
            integer ii, jj, wsum, psum;
            real c0, c4, c8, c12, c15;
            wsum = 0; psum = 0; c0 = 0; c4 = 0; c8 = 0; c12 = 0; c15 = 0;
            for (jj = 0; jj < 16; jj = jj + 1) begin
                wsum = wsum + amp_256[0][jj];  psum = psum + jj * amp_256[0][jj];
            end
            if (wsum != 0) c0 = psum * 1.0 / wsum;
            wsum = 0; psum = 0;
            for (jj = 0; jj < 16; jj = jj + 1) begin
                wsum = wsum + amp_256[4][jj];  psum = psum + jj * amp_256[4][jj];
            end
            if (wsum != 0) c4 = psum * 1.0 / wsum;
            wsum = 0; psum = 0;
            for (jj = 0; jj < 16; jj = jj + 1) begin
                wsum = wsum + amp_256[8][jj];  psum = psum + jj * amp_256[8][jj];
            end
            if (wsum != 0) c8 = psum * 1.0 / wsum;
            wsum = 0; psum = 0;
            for (jj = 0; jj < 16; jj = jj + 1) begin
                wsum = wsum + amp_256[12][jj]; psum = psum + jj * amp_256[12][jj];
            end
            if (wsum != 0) c12 = psum * 1.0 / wsum;
            wsum = 0; psum = 0;
            for (jj = 0; jj < 16; jj = jj + 1) begin
                wsum = wsum + amp_256[15][jj]; psum = psum + jj * amp_256[15][jj];
            end
            if (wsum != 0) c15 = psum * 1.0 / wsum;

            if (!(c15 > c12 && c12 > c8 && c8 > c4 && c4 > c0)) begin
                $display("   [FAIL] 频谱重心未随力度单调：vel0=%.2f vel4=%.2f vel8=%.2f vel12=%.2f vel15=%.2f",
                         c0, c4, c8, c12, c15);
                errors = errors + 1;
            end
            else
                $display("   B6 频谱重心随力度单调：vel0=%.2f < vel4=%.2f < vel8=%.2f < vel12=%.2f < vel15=%.2f  OK",
                         c0, c4, c8, c12, c15);
        end

        // [B7] 逐项打印 vel=0 / vel=8 / vel=15 三行，给人看谱形
        $display("");
        $display("   B7 谱形（amp，base=200；. = 0）");
        $display("      vel  k0   k1   k2   k3   k4   k5   k6   k7   k8   k9  k10  k11  k12  k13  k14  k15");
        for (v = 0; v < 16; v = v + 1) begin
            if (v == 0 || v == 4 || v == 8 || v == 12 || v == 15) begin
                $write("      %2d ", v);
                for (p = 0; p < 16; p = p + 1) begin
                    if (amp_256[v][p] == 8'd0) $write("   .");
                    else                       $write("%4d", amp_256[v][p]);
                end
                $write("\n");
            end
        end
        $display("");

        //---------------------------------------------------------------------
        $display("");
        $display(" E. 四槽分层 刀1 第二步：slot0 保留旧表，slot1-3 必须分化");
        $display("    slot0 钢琴(旧表原样) / slot1 弦乐 / slot2 钟铃 / slot3 贝斯");
        $display("    ★ 第一步（扩地址）的判据是'四槽必须相同'，已在表分化时按计划");
        $display("      改成'槽0 等于旧表 + 槽1-3 必须不同'。两条都必须保留：");
        $display("      前者守钢琴音色，后者守'分化真的发生了'。");
        //---------------------------------------------------------------------
        vs_base   = 8'd200;
        vs_vscale = 9'd256;

        // [E1] 槽 0 必须与改造前逐位相同 —— 钢琴音色不变的守卫
        slot_diff   = 0;
        slot_checks = 0;
        for (v = 0; v < 16; v = v + 1) begin
            for (p = 0; p < 16; p = p + 1) begin
                vs_slot = 2'd0; vs_vel = v[3:0]; vs_part = p[3:0];
                #1;
                slot_checks = slot_checks + 1;
                if (vs_amp !== amp_256[v][p]) begin
                    if (slot_diff < 8)
                        $display("      [DIFF] slot0 vel=%0d part=%0d : %0d vs 旧表 %0d",
                                 v, p, vs_amp, amp_256[v][p]);
                    slot_diff = slot_diff + 1;
                end
            end
        end
        checks = checks + 1;
        if (slot_diff != 0) begin
            $display("   [FAIL] E1 slot0 有 %0d / %0d 项与改造前不同（钢琴被改了）",
                     slot_diff, slot_checks);
            errors = errors + 1;
        end
        else
            $display("   E1 slot0 全部 %0d 项与改造前逐位相同（钢琴未受影响）  OK",
                     slot_checks);

        // [E2] 槽 1-3 必须各自与槽 0 不同（表真的分化了，不是又复制了 4 份）
        slot_diff = 0;
        for (s = 1; s < 4; s = s + 1) begin
            for (v = 0; v < 16; v = v + 1) begin
                for (p = 0; p < 16; p = p + 1) begin
                    vs_slot = s[1:0]; vs_vel = v[3:0]; vs_part = p[3:0];
                    #1;
                    if (vs_amp === amp_256[v][p]) slot_diff = slot_diff + 1;
                end
            end
        end
        checks = checks + 1;
        if (slot_diff > 768 * 3 / 4) begin
            $display("   [FAIL] E2 slot1-3 有 %0d / 768 项与 slot0 相同（表几乎没分化）",
                     slot_diff);
            errors = errors + 1;
        end
        else
            $display("   E2 slot1-3 仅 %0d / 768 项与 slot0 相同（四槽已分化）  OK",
                     slot_diff);

        // [E3] 低力度下高次泛音的相对强弱必须符合各槽性格：
        //      vel=0 / part=8 时   钟 > 弦乐 > 贝斯 > 钢琴(=0)
        //      这条是"性格"判据，不是"数值"判据 —— 表可以重调，但顺序不能反。
        for (s = 0; s < 4; s = s + 1) begin
            vs_slot = s[1:0]; vs_vel = 4'd0; vs_part = 4'd8; #1;
            amp_s[s][8] = vs_amp;
        end
        checks = checks + 1;
        if (amp_s[2][8] > amp_s[1][8] && amp_s[1][8] > amp_s[3][8]
            && amp_s[3][8] > amp_s[0][8])
            $display("   E3 vel0/part8 钟%0d>弦%0d>贝%0d>钢%0d（性格顺序正确）  OK",
                     amp_s[2][8], amp_s[1][8], amp_s[3][8], amp_s[0][8]);
        else begin
            $display("   [FAIL] E3 vel0/part8 期望 钟>弦>贝>钢，实得 %0d/%0d/%0d/%0d",
                     amp_s[2][8], amp_s[1][8], amp_s[3][8], amp_s[0][8]);
            errors = errors + 1;
        end

        vs_slot = 2'd0; vs_vel = 4'd0; vs_part = 4'd0;

        $display("");
        $display("================================================================");
        if (errors == 0) $display(" PASS —— %0d 项检查全部通过", checks);
        else             $display(" FAIL —— %0d / %0d 项检查失败", errors, checks);
        $display("================================================================");
        $display("");
        $finish;
    end

endmodule
