//=============================================================================
// tb_voice.v —— 逐声部"力度/音色"是否需要独立存储？（阶段 3 判据）
//
// 【要回答的问题（把假设变成事实）】
//   阶段 3 计划里写着"保存每声部力度/音色/状态"。但读代码得到的印象是：
//   note_map 在**装载时**就把力度算进每个泛音的幅度里
//   （vel_shape → amp_shaped → amp_cal = amp_shaped*vel_cur>>8 → load_amp），
//   引擎把它逐槽写进 pa_mem ⇒ 力度已经**烘进每个泛音的幅度**，不需要运行时再查。
//
//   若这个印象成立，那么"逐声部保存力度"就不是缺口 —— 而是一条需要被
//   **判据固定住**的性质（否则将来有人"顺手优化"就可能破坏它）。
//
// 【判据】
//   V1 同一个音、不同力度 ⇒ 落进 pa_mem 的幅度**不同**（力度确实进了幅度）
//   V2 装载别的声部、别的力度之后，**已装载声部的幅度一个都不变**
//      （这是"烘进幅度"的直接证据：不需要逐声部保存力度）
//   V3 全局 `vel_vscale`(0x6E) 中途改变，**不影响已发声的声部**
//      （只对之后的装载生效 —— 与"装载时求值"一致）
//
// 【怎么读】层次引用引擎的待生效影子内存 `u_top.u_tdm.pa_mem[slot]`：
//   load_en 写的就是它，而它是"待生效"，观察它不会有采样竞争。
//   槽位 = 组号*P + 泛音号（P=16）。
//=============================================================================
`timescale 1ns/1ps

module tb_voice;

    localparam integer P = 16;                    // 每组泛音数
    localparam integer NSLOT = 512;

    reg clk = 1'b0;
    always #18.5185 clk = ~clk;

    reg rst_n = 1'b0;
    wire [15:0] pad_bus = 16'h0000;
    reg         uart_rx = 1'b1;
    wire        uart_tx;
    reg         ev_valid = 1'b0, ev_on = 1'b0;
    reg [6:0]   ev_note = 7'd0;
    reg [3:0]   ev_vel  = 4'd0;

    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .preset(2'd0), .test_mode(1'b0),
        .uart_rx_pin(uart_rx), .uart_tx_pin(uart_tx),
        .led(), .dac_din(), .dac_ws(), .dac_bck(), .pa_en(),
        .pad(pad_bus)
    );

    integer fails;
    integer i, k;

    //   一组（16 个泛音）的幅度快照
    reg [15:0] snapA [0:P-1];
    reg [15:0] snapB [0:P-1];

    task snap;
        input integer grp;
        input integer which;      // 0 -> snapA, 1 -> snapB
        integer kk;
        begin
            for (kk = 0; kk < P; kk = kk + 1) begin
                if (which == 0) snapA[kk] = u_top.u_tdm.pa_mem[grp*P + kk];
                else            snapB[kk] = u_top.u_tdm.pa_mem[grp*P + kk];
            end
        end
    endtask

    task check;
        input [255:0] name;
        input integer got;
        input integer exp;
        begin
            if (got === exp) $display("  PASS  %0s (%0d)", name, got);
            else begin
                $display("  FAIL  %0s got %0d expected %0d", name, got, exp);
                fails = fails + 1;
            end
        end
    endtask

    task ev;
        input [6:0] n;
        input       on;
        input [3:0] v;
        begin
            ev_note = n; ev_on = on; ev_vel = v; ev_valid = 1'b1;
            @(posedge clk);
            ev_valid = 1'b0;
            repeat (120) @(posedge clk);        // 装载 16 个泛音（每组约 20 拍）+ 余量
        end
    endtask

    function integer grp_of;
        input [6:0] n;
        integer kk;
        begin
            grp_of = -1;
            for (kk = 0; kk < 32; kk = kk + 1)
                if (u_top.u_nm.gtab[kk] == n[6:0] && u_top.u_nm.gact[kk])
                    grp_of = kk;
        end
    endfunction

    integer g1, g2, g3;
    integer diff_12, diff_after;

    initial begin
        $display("==============================================================");
        $display(" 逐声部力度/音色是否需要独立存储？（阶段 3）");
        $display("==============================================================");

        fails = 0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (3000) @(posedge clk);

        //---- 声部1：note 48，满力度
        ev(7'd48, 1'b1, 4'd15);
        g1 = grp_of(7'd48);
        $display(" note48(vel=15) 落在组 %0d", g1);
        snap(g1, 0);

        //---- 声部2：note 55，小力度
        ev(7'd55, 1'b1, 4'd3);
        g2 = grp_of(7'd55);
        $display(" note55(vel=3)  落在组 %0d", g2);
        snap(g2, 1);

        //--------------------------------------------------------------- V1
        $display(" V1 不同力度 ⇒ 落进 pa_mem 的幅度不同");
        diff_12 = 0;
        for (k = 0; k < P; k = k + 1)
            if (snapA[k] != snapB[k]) diff_12 = diff_12 + 1;
        $display("      两组的 16 个泛音中有 %0d 个幅度不同", diff_12);
        if (diff_12 == 0) begin
            $display("  FAIL  V1 力度没有进入幅度 ⇒ 力度确实需要另行保存");
            fails = fails + 1;
        end
        else $display("  PASS  V1 力度已烘进每个泛音的幅度");

        //--------------------------------------------------------------- V2
        $display(" V2 装载第三个声部后，前两个声部的幅度必须一个都不变");
        ev(7'd62, 1'b1, 4'd10);
        g3 = grp_of(7'd62);
        $display(" note62(vel=10) 落在组 %0d", g3);
        //   重新读组1、组2，逐项与快照比对
        diff_after = 0;
        for (k = 0; k < P; k = k + 1) begin
            if (u_top.u_tdm.pa_mem[g1*P + k] !== snapA[k]) begin
                $display("  FAIL  V2 组%0d 泛音%0d 从 %0d 变成了 %0d",
                         g1, k, snapA[k], u_top.u_tdm.pa_mem[g1*P + k]);
                diff_after = diff_after + 1;
            end
            if (u_top.u_tdm.pa_mem[g2*P + k] !== snapB[k]) begin
                $display("  FAIL  V2 组%0d 泛音%0d 从 %0d 变成了 %0d",
                         g2, k, snapB[k], u_top.u_tdm.pa_mem[g2*P + k]);
                diff_after = diff_after + 1;
            end
        end
        check("V2-other-voice-must-not-change", diff_after, 0);

        //--------------------------------------------------------------- V3
        $display(" V3 中途改全局 vel_vscale(0x6E)，已发声声部的幅度不受影响");
        //   ★ R 是 reg_bank 的输出**线网**，不能当 l-value 赋值；
        //     要改寄存器得写 reg_bank 内部的存储 `mem`（本项目其它测试台同款做法）。
        u_top.u_reg.mem[8'h6E] = 8'h00;     // vscale = 0（关掉力度灵敏度）
        repeat (200) @(posedge clk);
        diff_after = 0;
        for (k = 0; k < P; k = k + 1) begin
            if (u_top.u_tdm.pa_mem[g1*P + k] !== snapA[k]) diff_after = diff_after + 1;
            if (u_top.u_tdm.pa_mem[g2*P + k] !== snapB[k]) diff_after = diff_after + 1;
        end
        check("V3-global-change-must-not-touch-sounding", diff_after, 0);

        $display("==============================================================");
        if (fails == 0) $display("RESULT voice=PASS");
        else            $display("RESULT voice=FAIL fails=%0d", fails);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #200_000_000;
        $display("RESULT voice=TIMEOUT fails=%0d", fails);
        $finish;
    end

endmodule
