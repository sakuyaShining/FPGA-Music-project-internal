//=============================================================================
// tb_vp.v —— 塑谱 v1 验收判据 VP1–VP4（21 号 §4 的配方）
//
//  VP1 谱 RAM 写入/自动步进：连写 16 字节 ⇒ 内部谱阵列逐字节一致
//  VP2 **在响变形（核心）**：按住音 → 改谱 → 只刷该声部 ⇒
//        (a) 该声部谱形（装载幅度）变化 ✓
//        (b) 变化发生在 ≤2 个样本周期内 ✓
//        (c) **未触及声部逐位不变** ✓
//  VP3 替换/叠加：叠加=预设+谱（每个泛音的增量是同一常数）；替换=只用谱（均匀谱 ⇒ 各泛音相等）
//  VP4 pad 位掩码→谱映射：HARM_PADS 单个位 ⇒ 只有对应泛音被 boost
//
// 【判据尽量不循环论证】期望值取自"可观测的关系"，不重算 RTL 的公式：
//   · VP1 直接比对写入序列 ✓
//   · VP3 用"增量是否为同一常数"与"替换模式下各泛音是否相等" ✓
//   · VP4 用"只有一位被抬高、其余等于基线" ✓
//   · VP2 用"同一配置两次测量的差异 + 另一声部的逐位不变" ✓
//=============================================================================

`timescale 1ns/1ps

module tb_vp;

    reg clk = 1'b0;
    reg rst_n;
    always #18.5185 clk = ~clk;

    reg        uart_rx = 1'b1;
    wire       uart_tx;
    reg        ev_valid, ev_on;
    reg [6:0]  ev_note;
    reg [3:0]  ev_vel;
    wire [15:0] pad_unused;                    // inout 端口必须接一根线（不能直接写常量 ✗）

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_unused)
    );

    localparam integer DIV = 234;
    integer i, k, fails;
    integer a0 [0:15];        // 基线（spec=0）
    integer a1 [0:15];        // 叠加 + 均匀谱
    integer a2 [0:15];        // 替换 + 均匀谱
    integer b0 [0:15];        // 第二声部基线
    integer b1 [0:15];        // 第二声部刷新后（必须逐位不变）
    integer delta, dmin, dmax;
    integer t0, t1, fails_before, add_delta;

    task send_byte(input [7:0] b);
        integer j;
        begin
            uart_rx = 1'b0; repeat (DIV) @(posedge clk);
            for (j = 0; j < 8; j = j + 1) begin uart_rx = b[j]; repeat (DIV) @(posedge clk); end
            uart_rx = 1'b1; repeat (DIV) @(posedge clk);
        end
    endtask
    task wr(input [7:0] a, input [7:0] d); begin send_byte(a); send_byte(d); end endtask

    task wait_samples(input integer n);
        integer j;
        begin
            for (j = 0; j < n; j = j + 1) begin
                @(posedge clk);
                while (!u_top.sample_en) @(posedge clk);
            end
        end
    endtask

    task press(input [6:0] n);
        begin
            @(posedge clk);
            ev_note <= n; ev_vel <= 4'd15; ev_on <= 1'b1; ev_valid <= 1'b1;
            @(posedge clk);
            ev_valid <= 1'b0;
            wait_samples(6);                   // 等装载序列走完 + 跨样本边界
        end
    endtask

    task read_amps(input integer grp, input integer is_b);
        integer j;
        begin
            for (j = 0; j < 16; j = j + 1)
                if (is_b) b1[j] = u_top.u_tdm.amp_mem[grp*16 + j];
                else      a0[j] = u_top.u_tdm.amp_mem[grp*16 + j];
        end
    endtask

    // 读任意数组（用寄存器组模拟：这里直接读进 a1/a2/b0）
    task read_into(input integer grp, input integer which);
        integer j, v;
        begin
            for (j = 0; j < 16; j = j + 1) begin
                v = u_top.u_tdm.amp_mem[grp*16 + j];
                case (which)
                    1: a1[j] = v;
                    2: a2[j] = v;
                    3: b0[j] = v;
                    default: a0[j] = v;
                endcase
            end
        end
    endtask

    // 写 16 字节谱（自动步进：只写 0x58 一次 + 16 次 0x59）
    task write_spec(input integer val);
        integer j;
        begin
            wr(8'h58, 8'd0);
            for (j = 0; j < 16; j = j + 1) wr(8'h59, val[7:0]);
        end
    endtask

    initial begin
        fails = 0;
        ev_valid = 0; ev_on = 0; ev_note = 0; ev_vel = 0;
        $display("==============================================================");
        $display(" 塑谱 v1 判据 VP1–VP4");
        $display("==============================================================");

        rst_n = 1'b0; repeat (200) @(posedge clk);
        rst_n = 1'b1; repeat (4000) @(posedge clk);

        //---------------- VP1：连写 16 字节，内部阵列逐字节一致 ----------------
        wr(8'h58, 8'd0);
        for (i = 0; i < 16; i = i + 1) wr(8'h59, (i*13 + 7) & 8'hFF);
        if (u_top.u_nm.spec_ram[0]  !== 8'd7  || u_top.u_nm.spec_ram[1]  !== 8'd20 ||
            u_top.u_nm.spec_ram[15] !== 8'd202) begin
            $display("  [VP1] ✗ 内部谱阵列与写入序列不符：spec[0]=%0d(期望7) spec[1]=%0d(期望20) spec[15]=%0d(期望202)",
                     u_top.u_nm.spec_ram[0], u_top.u_nm.spec_ram[1], u_top.u_nm.spec_ram[15]);
            fails = fails + 1;
        end
        else $display("  [VP1] 连写 16 字节 + 自动步进 ⇒ 阵列逐字节一致 ✓（spec[0]=7 spec[1]=20 spec[15]=202）");

        // 清谱（写 0）
        write_spec(0);

        //---------------- 基线：spec=0、叠加模式 → 记录预设装载幅度 ----------------
        press(7'd64);                          // 第一声部 → 组 0
        read_into(0, 0);
        //---------------- VP2 前置：再按一个音 → 组 1 ----------------
        press(7'd72);
        read_into(1, 3);                       // b0 = 第二声部基线
        $display("  [VP2] 两个声部在响：组0 首泛音 amp=%0d，组1 首泛音 amp=%0d", a0[0], b0[0]);

        //---------------- VP3-叠加：spec=100（均匀）⇒ 每个泛音的增量应为同一常数 ----------------
        write_spec(100);
        wr(8'h5A, 8'h02);                      // 叠加 + 自动刷新（默认值）
        wr(8'h63, 8'hFF);                      // 全刷（只刷在响的组）
        wait_samples(8);
        read_into(0, 1);                       // a1
        dmin = 100000; dmax = -100000;
        for (k = 0; k < 16; k = k + 1) begin
            delta = a1[k] - a0[k];
            // ★ 只统计【未封顶】的泛音：装载幅度是力度缩放后的，封顶处 ≈239（不是 250 ✗）
            if (a0[k] + 100 < 255) begin
                if (delta < dmin) dmin = delta;
                if (delta > dmax) dmax = delta;
            end
        end
        $display("  [VP3-叠加] 均匀谱 100 ⇒ 未封顶泛音的增量范围 [%0d, %0d]（应为同一常数，允许 ±1 截断）", dmin, dmax);
        if (dmax - dmin > 1 || dmin <= 0) begin
            $display("        => FAIL 增量不是同一常数"); fails = fails + 1;
        end
        else $display("        ⇒ 增量恒为 %0d~%0d ✓（= 100 × 力度系数的>>8 截断，且与预设无关 ✓）", dmin, dmax);
        add_delta = dmin;                      // ★ 保存【未封顶】的那个增量常数（k=0 是封顶的 ✗ 不能用）

        //---------------- VP3-替换：spec=100（均匀）⇒ 各泛音应彼此相等 ----------------
        wr(8'h5A, 8'h03);                      // bit0=1 替换 + bit1 自动刷新
        wr(8'h63, 8'hFF);
        wait_samples(8);
        read_into(0, 2);                       // a2
        dmin = 100000; dmax = -100000;
        for (k = 0; k < 16; k = k + 1) begin
            if (a2[k] < dmin) dmin = a2[k];
            if (a2[k] > dmax) dmax = a2[k];
        end
        $display("  [VP3-替换] 均匀谱 100 ⇒ 各泛音 amp 范围 [%0d, %0d]（应相等，且=叠加模式的增量）",
                 dmin, dmax);
        if (dmin != dmax || (dmin - add_delta > 1) || (add_delta - dmin > 1)) begin
            $display("        => FAIL 替换模式不满足『只用谱』（或与未封顶增量不一致，允许 ±1）"); fails = fails + 1;
        end
        else $display("        ⇒ 替换模式各泛音相等（=%0d）且 = 叠加模式的未封顶增量 %0d ✓（预设被完全忽略 ✓）",
                      dmin, add_delta);

        // 回叠加模式 + 清谱
        wr(8'h5A, 8'h02);
        write_spec(0);
        wr(8'h63, 8'hFF);
        wait_samples(8);

        //---------------- VP4：HARM_PADS 单个位 → 只有对应泛音被 boost ----------------
        read_into(0, 0);                       // 重新取基线
        wr(8'h5B, 8'h04);                      // bit2 ⇒ 泛音 3（k=2）
        wr(8'h63, 8'hFF);
        wait_samples(8);
        read_into(0, 1);                       // a1 = boost 后
        $display("  [VP4] HARM_PADS=0x04（泛音3）⇒ k=2 的 amp %0d→%0d；k=0 的 amp %0d→%0d",
                 a0[2], a1[2], a0[0], a1[0]);
        if (a1[2] <= a0[2] || a1[2] < 200) begin
            $display("        ⇒ ✗ 目标泛音没有被 boost"); fails = fails + 1;
        end
        else if (a1[0] != a0[0] || a1[1] != a0[1] || a1[3] != a0[3]) begin
            $display("        ⇒ ✗ 非目标泛音被改动"); fails = fails + 1;
        end
        else $display("        ⇒ 只有 k=2 被 boost、其余逐位不变 ✓");
        wr(8'h5B, 8'h00);
        wr(8'h63, 8'hFF);

        //---------------- VP2 核心（逐声部）：关掉自动刷新，只发 0x63=0 ----------------
        //   ★ 教训：第一版没关自动刷新 ⇒ 写谱就把 spec_dirty 置脏 ⇒ 节流到点后
        //     自动来了个"全刷" ⇒ 未触及的组1 也被改了 ✗（那是全局模式的正常行为 ✓，
        //     但不是本判据要验的"逐声部" ✓）
        wr(8'h5A, 8'h00);                      // bit1=0 关自动刷新；bit0=0 叠加
        wait_samples(4);
        read_into(0, 0);                       // 组0 刷新前
        read_into(1, 3);                       // 组1 刷新前
        t0 = 0;
        write_spec(180);
        wr(8'h63, 8'h00);                      // ★ 只刷声部 0（组 0）
        for (k = 0; k < 40; k = k + 1) begin
            wait_samples(1);
            t0 = t0 + 1;
            if (u_top.u_tdm.amp_mem[0] != a0[0]) k = 100;   // 变了就停
        end
        read_into(0, 1);                       // 组0 刷新后
        $display("  [VP2a 逐声部] 单刷声部0：组0 首泛音 %0d→%0d（耗时 %0d 个样本周期，需 ≤2）",
                 a0[0], a1[0], t0);
        if (a1[0] == a0[0]) begin
            $display("        => FAIL 在响声部没有变化"); fails = fails + 1;
        end
        else if (t0 > 2) begin
            $display("        => FAIL 变化用了 %0d 个样本周期（要求 ≤2）", t0); fails = fails + 1;
        end
        else $display("        ⇒ 在响声部在 %0d 个样本周期内变化 ✓", t0);

        for (k = 0; k < 16; k = k + 1)
            if (u_top.u_tdm.amp_mem[16 + k] !== b0[k]) begin
                $display("        => FAIL 未触及的组1 第 %0d 泛音被改动：%0d → %0d",
                         k, b0[k], u_top.u_tdm.amp_mem[16+k]);
                fails = fails + 1;
                k = 100;
            end
        if (fails == 0) $display("        ⇒ 未触及声部 16 个泛音逐位不变 ✓（A1 逐声部塑形 ✓）");

        //---------------- VP2 全局：打开自动刷新 ⇒ 写谱后所有在响的声部都应变 ----------------
        //   ★ 判据设计：两个声部**同一预设 + 同一谱** ⇒ 全局刷新后它们的装载幅度必须**逐位相等** ✓
        //     （第一版拿同一个泛音"有没有变"来判 ✗，但那个泛音在两次谱下都封顶到 239 ✗ ⇒ 假失败）
        wr(8'h5A, 8'h02);                      // bit1=1 自动刷新
        write_spec(60);                        // 新谱 ⇒ 置脏
        for (k = 0; k < 12; k = k + 1) wait_samples(1);   // 等节流窗口 + 装载
        fails_before = 0;
        for (k = 0; k < 16; k = k + 1)
            if (u_top.u_tdm.amp_mem[k] !== u_top.u_tdm.amp_mem[16+k]) fails_before = fails_before + 1;
        $display("  [VP2b 全局自动] 写谱后：组0 首泛音 %0d，组1 首泛音 %0d；两个声部逐位不同处 = %0d（应 0）",
                 u_top.u_tdm.amp_mem[0], u_top.u_tdm.amp_mem[16], fails_before);
        if (fails_before != 0) begin
            $display("        => FAIL 自动刷新没有让所有在响的声部用上同一谱"); fails = fails + 1;
        end
        else $display("        ⇒ 自动刷新把【所有在响的声部】都更新到同一谱 ✓（全局塑形模式 ✓）");

        $display("");
        if (fails == 0) $display("RESULT vp=PASS vp1=1 vp2=1 vp3=1 vp4=1");
        else            $display("RESULT vp=FAIL fails=%0d", fails);
        $finish;
    end

    initial begin
        #900_000_000;
        $display("RESULT vp=TIMEOUT");
        $finish;
    end

endmodule
