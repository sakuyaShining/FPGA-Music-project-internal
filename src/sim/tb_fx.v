//=============================================================================
// tb_fx.v —— 效果器（延迟 / 合唱）冲激响应验收
//
// 【为什么用冲激响应】
//   效果器的本质就是"把输入复制到某些延迟位置并按某种增益叠加"。
//   喂一个单位冲激，输出就是它的【冲激响应】—— 每个回声的位置与幅度都能
//   直接读出来，与理论值逐个比对即可。这比"听上去有混响"强得多。
//
// 【两个测试（+test=N）】
//   test=0 延迟：dly_len=2048、反馈 Q8=0x60(0.375)
//          → 期望回声在 2048 的整数倍处，幅度按 0.375^k 等比衰减
//   test=1 合唱：CHO_BASE=1024、depth=64、LFO 周期 390 样本（为仿真加速）
//          → 每隔约 100 样本发一个冲激，量"回声延迟"随 LFO 的起伏：
//            应在 1024±64 之间按三角波变化，周期与设定一致
//
// 【输出约定】dry_en=0、wet_sh=0 → 输出就等于抽头值本身，
//   所以回声幅度可以直接当整数读（不用反算增益）。
//=============================================================================

`timescale 1ns/1ps

module tb_fx;

    localparam integer PERIOD = 16;      // 每 16 拍一个样本（采样率本身不影响 IR 判据）

    reg clk = 1'b0;
    reg rst_n;
    always #5 clk = ~clk;

    reg [4:0] pc;
    wire sample_en = (pc == PERIOD - 1);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                 pc <= 5'd0;
        else if (pc == PERIOD - 1)  pc <= 5'd0;
        else                        pc <= pc + 5'd1;
    end

    //-------------------------------------------------------------------------
    // 参数
    //-------------------------------------------------------------------------
    reg [1:0]  which;
    reg        dry_en, dly_en, cho_en, rev_en;
    reg [2:0]  wet_sh;
    reg [15:0] dly_len;
    reg [7:0]  fb_q8;
    reg [15:0] cho_rate, cho_depth;
    reg [7:0]  rev_fb;
    integer    dly_period;
    reg [2:0]  rev_damp;

    reg signed [23:0] din;
    wire signed [23:0] dout;
    wire signed [15:0] tap;

    fx_delay #(.DW(16), .AW(11), .CHO_BASE(1024), .FLUSH_LEN(64)) u_fx (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .din(din),
        .dry_en(dry_en), .dly_en(dly_en), .cho_en(cho_en), .rev_en(rev_en),
        .wet_sh(wet_sh), .dly_len(dly_len), .fb_q8(fb_q8),
        .cho_rate(cho_rate), .cho_depth(cho_depth),
        .rev_fb_q8(rev_fb), .rev_damp(rev_damp),
        .dout(dout), .tap_dbg(tap)
    );

    //-------------------------------------------------------------------------
    // 记录 + 激励
    //-------------------------------------------------------------------------
    integer fout, ns, i;
    localparam integer NSAMP = 9000;
    localparam signed [23:0] IMP = 24'sd2560000;   // 内部 16 位 = 10000

    task wait_samples(input integer n);
        integer k;
        begin
            for (k = 0; k < n; k = k + 1) begin
                @(posedge clk);
                while (!sample_en) @(posedge clk);
            end
        end
    endtask

    initial begin
        if (!$value$plusargs("test=%d", which)) which = 2'd0;
        if (!$value$plusargs("dly=%d", dly_period)) dly_period = 2048;

        // 默认：只有湿声、满增益
        dry_en = 1'b0; dly_en = 1'b0; cho_en = 1'b0; rev_en = 1'b0;
        wet_sh = 3'd0; dly_len = dly_period[15:0]; fb_q8 = 8'd0;
        cho_rate = 16'd43000; cho_depth = 16'd64;
        rev_fb = 8'd192; rev_damp = 3'd3;   // 0.75 → 尾巴约 0.9 s
        din = 24'sd0;

        if (which == 2'd0) begin
            dly_en = 1'b1; fb_q8 = 8'd96;          // 0.375
        end
        else if (which == 2'd1) begin
            cho_en = 1'b1; cho_rate = 16'd43000;   // LFO 周期 = 2^24/43000 ≈ 390 样本
            cho_depth = 16'd64;
        end
        else begin
            rev_en = 1'b1;                          // 混响：单线多抽头 + 阻尼反馈
        end

        rst_n = 1'b0;
        repeat (20) @(posedge clk);
        rst_n = 1'b1;
        wait_samples(20);

        $display("==============================================================");
        $display(" 效果器冲激响应测试  test=%0d", which);
        if (which == 2'd0)
            $display("   延迟 dly_len=%0d 反馈 Q8=%0d", dly_len, fb_q8);
        else if (which == 2'd1)
            $display("   合唱 CHO_BASE=1024 depth=%0d LFO 频率字=%0d（周期≈390 样本）",
                     cho_depth, cho_rate);
        else
            $display("   混响 抽头 1487/1801/2137/2459 反馈 Q8=%0d 阻尼=%0d",
                     rev_fb, rev_damp);
        $display("==============================================================");

        fout = $fopen((which == 2'd0) ? "fx_delay.txt" :
                      ((which == 2'd1) ? "fx_chorus.txt" : "fx_reverb.txt"), "w");

        //---- 冲激：延迟测试发 1 个（1 样本宽）；
        //     合唱测试发【4 样本宽的短促发】----
        //   为什么合唱要用 4 样本宽：合唱抽头地址每样本移动约 0.3~1.3 个样本
        //     （LFO 在推它），【单样本冲激会被跳过】——第一次实测就有 4 次
        //     "找不到回声"。这不是 bug，是最近邻重采样的固有性质；
        //     把冲激加宽即可稳定测到。
        for (ns = 0; ns < NSAMP; ns = ns + 1) begin
            if (which != 2'd1) begin
                din <= (ns == 100) ? IMP : 24'sd0;   // 延迟与混响都用单位冲激
            end
            else begin
                // 每 137 个样本发一次、每次 4 个样本宽；共 12 次（≈4 个 LFO 周期）
                //   步长的两条约束：
                //     ① 不能与 LFO 周期（390）成简单整数比 → 否则采样相位混叠
                //        （用 97 时 97×4=388≈390，实测极差只有 73/128）；
                //     ② 必须【大于调制范围本身】(2×depth=128) → 否则搜索窗会
                //        先撞到上一个冲激的回声（用 37 时实测延迟出现 954 的假值）。
                din <= ((ns >= 100) && (((ns - 100) % 137) < 4) && (ns < 100 + 137 * 12)) ? IMP : 24'sd0;
            end
            @(posedge clk);
            while (!sample_en) @(posedge clk);
            $fdisplay(fout, "%0d", $signed(dout));
        end
        $fclose(fout);
        $display("  → %s", (which == 2'd0) ? "fx_delay.txt" :
                           ((which == 2'd1) ? "fx_chorus.txt" : "fx_reverb.txt"));
        $finish;
    end

    initial begin
        #5_000_000;
        $display("[TIMEOUT] test=%0d", which);
        $finish;
    end

endmodule
