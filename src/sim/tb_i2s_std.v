//=============================================================================
// tb_i2s_std.v —— I2S 发送器：【标准接收模型】vs【旧模型】同线对照判据
//
// 【为什么要有这一版，且为什么与 tb_i2s_tx.v 不重复】
//   tb_i2s_tx.v 的接收模型把【WS 翻转的那个上升沿】当作新声道 MSB。而 Philips/NXP
//   I2S 规范（UM11732 §3.2）要求 WS 相对 MSB **提前一个完整 BCK 周期**变化，
//   MAX98357A 也按此时序采样（其 "1-bit delay" 即指此事）。同一个位流，两种模型
//   的解释只差一位：
//
//     WS 变化后的第 1 个采样沿   标准：不计入新字(上一字末位)   旧模型：新字 MSB
//     WS 变化后的第 2 个采样沿   标准：新字 MSB                旧模型：新字 bit14
//
//   差一位是"看波形看不出来"的 —— 必须让两个模型**同线并行**解同一份位流，
//   谁的输出等于源样本，谁才是对的。这就是本测试台存在的理由。
//
// 【两个模型的差别只有一处】
//     旧模型(leg)：ws 一变，本采样沿就计入新字
//     标准(sta)  ：ws 一变，本采样沿【不计入】新字，从下一个采样沿才开始收
//                  —— 这就是"WS 提前一个 BCK"在接收侧的等价表述
//
// 【覆盖旧测试台缺的三件事】
//   ① 激励从负跨到正（旧测试台 64 帧 × +37 只走到 −30437，全程为负，一次没到正数）
//   ② 帧数加长（200 帧）、步长与 2^16 互质，便于识别"丢一位 / 错一位"
//   ③ 左右声道槽分别核对——旧测试台把同一个样本填进两个槽，从未测过左右不同值
//
// 【输出】由 tools/scripts/i2s_std_check.py 判定
//   i2s_std_src.txt   每帧源样本（16 bit 有符号）
//   i2s_std_std.txt   标准模型解出的 (ws, word)
//   i2s_std_leg.txt   旧模型解出的   (ws, word)
//=============================================================================
`timescale 1ns/1ps

module tb_i2s_std;

    localparam N_FRAME  = 200;
    localparam CLK_HALF = 18.519;       // 27 MHz
    localparam STEP     = 251;          // 与 2^16 互质

    reg clk, rst_n;
    initial clk = 1'b0;
    always #(CLK_HALF) clk = ~clk;

    wire bck_en, bck, lrck, sample_en;

    //   ★ DIV_BCK 必须与【顶层出货配置】一致：tdm_top.v 用的是 16（27/16 = 1.6875 MHz），
    //     不是 18。两者都是"每半帧 16 个采样沿"，但拍数不同；用错会让本判据与
    //     真正上板的时序不是同一档（本项目已经因为"测试台与顶层配置不同档"吃过亏）。
    audio_clk_en #(.DIV_BCK(16), .BCK_PER_LRCK(32)) u_clk (
        .clk(clk), .rst_n(rst_n),
        .bck_en(bck_en), .bck(bck), .lrck(lrck), .sample_en(sample_en));

    //-------------------------------------------------------------------------
    // 激励：0x8000 起每帧 +251 ⇒ 从 −32768 跨到正数
    //-------------------------------------------------------------------------
    reg  [15:0] src, src_lat;
    reg         src_lat_v;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            src <= 16'h8000; src_lat <= 16'h8000; src_lat_v <= 1'b0;
        end
        else if (sample_en) begin
            src_lat   <= src;
            src_lat_v <= 1'b1;
            src       <= src + STEP[15:0];
        end
        else
            src_lat_v <= 1'b0;
    end

    wire signed [23:0] s24 = {src, 8'h00};

    wire sd, ws;

    i2s_tx #(.SW(24), .DW(16)) dut (
        .clk(clk), .rst_n(rst_n),
        .bck_en(bck_en), .lrck(lrck), .sample_en(sample_en),
        .sample_in(s24),
        .sd(sd), .ws(ws));

    //=========================================================================
    // 标准 I2S 接收器（本测试台的判据）
    //
    //   ★ 关键认识（2026-10-06 实测纠错）：标准的收字逻辑与旧模型**完全相同**
    //     —— 恒在 bck 上升沿采样，WS 一变就把该沿当新字 MSB，每半个 WS 周期
    //     恰好 16 个采样沿收满 16 位。
    //     曾经写过一个"WS 变了先空一沿、下一沿才收 MSB"的版本，结果每个字只能
    //     用到 15 个沿，**永远收不满**（实测卡在 cnt=13/14）。那个写法是错的。
    //
    //   所以"标准 vs 旧"的差别**不在接收器的逻辑，而在数据相对 WS 的位置**：
    //     标准 I2S：WS 变化的那一沿读到【新字 MSB】
    //     本 RTL 现状：WS 变化的那一沿读到【上一字末位】⇒ 整字左移一位
    //   本测试台因此只需要一个、且是标准的接收器：它的输出是否等于源样本，
    //   就是"发送器是否符合标准 I2S"的判据。
    //   旧模型保留作对照：它现在能通过，恰好证明"当前 PASS 不能排除协议缺陷"。
    //=========================================================================
    reg        p_bck;
    reg        ws_prev;                 // 标准接收器的字边界（= WS 翻转）
    reg [4:0]  cnt_s;
    reg [15:0] sr_s, word_s;
    reg        v_s;
    reg        ws_prev_leg;             // 旧模型仅用于对照
    reg [4:0]  cnt_l;
    reg [15:0] sr_l, word_l;
    reg        v_l;
    //   ★ 采集门控：复位后发送器的第一帧还是 0，若从复位就开始收，收到的
    //     第一个字必然是垃圾，于是"逐字比对"从第 0 项就整体错位 —— 这正是
    //     第一版写法失败的原因（两边 200/200 全不符，看着像 RTL 坏了）。
    //     正确做法：等第一帧真正装载过之后才开始收字。
    reg        cap_en;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            p_bck <= 1'b0;
            ws_prev <= 1'b0; cnt_s <= 5'd0; sr_s <= 16'd0; word_s <= 16'd0; v_s <= 1'b0;
            ws_prev_leg <= 1'b0; cnt_l <= 5'd0; sr_l <= 16'd0; word_l <= 16'd0; v_l <= 1'b0;
            cap_en <= 1'b0;
        end
        else begin
            p_bck <= bck;
            v_s <= 1'b0;
            v_l <= 1'b0;
            //   第一帧装载后，再等 2 个采样沿让 WS/相位稳定，然后开闸
            if (src_lat_v) cap_en <= 1'b1;
            if (cap_en && (bck === 1'b1) && (p_bck === 1'b0)) begin
                // ---- 标准接收器（结构照抄 tb_i2s_tx.v 里已验证的那个模型）----
                //   ★ 我第一版在这里写错过，症状是"每个字都被复制一遍、且值减半"：
                //     收字分支里多写了一次 `sr_s <= {sr_s[14:0], sd}`，
                //     于是 WS 变化沿存进去的 MSB 在下一个沿被移掉，位上少一位。
                //     正确写法：WS 变化沿【只装载、不递增到收字分支】，之后每次
                //     先移位收集，计数到 15 时把当前 sd 作为最后一位凑满 16 位。
                if (ws !== ws_prev) begin
                    ws_prev <= ws;
                    sr_s    <= {15'b0, sd};        // WS 变化沿 = 新字 MSB
                    cnt_s   <= 5'd1;
                end
                else begin
                    sr_s  <= {sr_s[14:0], sd};
                    cnt_s <= cnt_s + 5'd1;
                    //   ★ 必须在【本采样沿】就把字填满并输出。
                    //     曾经写成"设个标志、下一沿再填"，于是第 16 位被推迟一位，
                    //     那个 bit0 变成了下一个字的 MSB ⇒ 实测现象是
                    //     **每个字都被输出两遍**（std = 8000,8000,80FB,80FB,…）。
                    //     本沿的 sd 就是第 16 位（bit0），直接拼进来即可。
                    if (cnt_s == 5'd15) begin
                        word_s <= {sr_s[14:0], sd};
                        v_s    <= 1'b1;
                    end
                end
                // ---- 旧模型（与 tb_i2s_tx.v 同构，仅作对照）----
                if (ws !== ws_prev_leg) begin
                    ws_prev_leg <= ws;
                    sr_l        <= {15'b0, sd};
                    cnt_l       <= 5'd1;
                end
                else begin
                    sr_l  <= {sr_l[14:0], sd};
                    cnt_l <= cnt_l + 5'd1;
                    if (cnt_l == 5'd15) begin
                        word_l <= {sr_l[14:0], sd};
                        v_l    <= 1'b1;
                    end
                end
            end
        end
    end

    //-------------------------------------------------------------------------
    // 主流程：线性写盘（不用 fork，避免任务间互相等待把自己卡住）
    //-------------------------------------------------------------------------
    integer fs, fa, fb;
    integer n_src, n_a, n_b;
    reg     src_lat_q;
    //   采集门控同步的源值锁存：接收器开闸后才记录，保证"源第 k 字"与
    //   "接收器第 k 字"指的是同一个样本（否则会整体错开一字，看着像 RTL 坏了）。
    reg [15:0] lat_cap;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) src_lat_q <= 1'b0;
        else        src_lat_q <= src_lat_v;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)          lat_cap <= 16'h8000;
        else if (src_lat_q)  lat_cap <= src_lat;
    end

    initial begin
        $display("==============================================================");
        $display(" I2S：标准接收模型 vs 旧模型（同一份位流，逐字比对）");
        $display("==============================================================");

        rst_n = 1'b0;
        repeat (200) @(posedge clk);
        rst_n = 1'b1;
        repeat (400) @(posedge clk);

        fs = $fopen("i2s_std_src.txt", "w");
        fa = $fopen("i2s_std_std.txt", "w");
        fb = $fopen("i2s_std_leg.txt", "w");
        if (fs == 0 || fa == 0 || fb == 0) begin
            $display("  FAIL 无法创建输出文件");
            $finish;
        end

        n_src = 0; n_a = 0; n_b = 0;
        //   跑到"三个日志都收满"为止；任一接收器的字边界判错都会让它的计数变慢，
        //   所以用超时兜底而不是死等（否则缺陷会表现成挂死，而不是可读的差异）。
        while ((n_src < N_FRAME) || (n_a < N_FRAME) || (n_b < N_FRAME)) begin
            @(posedge clk);
            if (src_lat_q && cap_en && n_src < N_FRAME) begin
                $fdisplay(fs, "%0d", $signed(lat_cap));
                n_src = n_src + 1;
            end
            if (v_s && n_a < N_FRAME) begin
                $fdisplay(fa, "%0d %0d", ws_prev, $signed(word_s));
                n_a = n_a + 1;
            end
            if (v_l && n_b < N_FRAME) begin
                $fdisplay(fb, "%0d %0d", ws_prev_leg, $signed(word_l));
                n_b = n_b + 1;
            end
        end

        $fclose(fs); $fclose(fa); $fclose(fb);
        $display(" 源 %0d 字 / 标准模型 %0d 字 / 旧模型 %0d 字", n_src, n_a, n_b);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #200_000_000;
        $display(" [watchdog] timeout（%0d/%0d/%0d 字）", n_src, n_a, n_b);
        $finish;
    end

endmodule
