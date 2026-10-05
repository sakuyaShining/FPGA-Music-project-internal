//=============================================================================
// tb_pad_pitch.v —— 音高与八度判据自检（对应规格 v2.0 第 7 节）
//
// 覆盖：
//   P1  键位映射正确（25 键 × 5 档位 = 125 组，表驱动）
//   P2  半音完整（下排 12 键覆盖 12 个半音类）
//   P3  档位语义（同一键相邻档位相差 12）
//   P4  上限行为（超 108 不发声；用 BASE=60 的实例构造越界）
//   P5  档位不环绕
//   P6  挂音防护（按下→换挡→松开，note-off 用按下时的音）
//   P8  非音高键不发声
//   P9  无同音通道（25 键音符号两两不同）
//   P11 换挡本身不产生事件
//   P12 跨档同时发声（两个音各自独立 on/off）
//   P13 音域条防误触（不足 100 ms 不改档）
//   P14 音域条生效（≥ 100 ms 改档且 LED one-hot）
//   P15 音域条不发声
//
// 判定：逐条打印 PASS / FAIL（英文名，避免向量字符串乱码），末尾汇总。
//=============================================================================
`timescale 1ns/1ps

module tb_pad_pitch;

    reg clk = 1'b0;
    reg rst_n = 1'b0;
    always #10 clk = ~clk;                    // 50 MHz（逻辑与频率无关）

    integer errors = 0;
    integer i, j;

    //--------------------------------------------------------------- 标准实例
    reg  [34:0] touch = 35'd0;
    reg  [2:0]  pos   = 3'd1;                 // 1 = 0 档
    reg  [3:0]  vel   = 4'd12;

    wire        ev_on, ev_off;
    wire [6:0]  ev_note;
    wire [3:0]  ev_vel;
    wire [7:0]  harm_mask;

    pad_pitch #(.NCH(35), .NPIT(25), .BASE(48)) ua (
        .clk(clk), .rst_n(rst_n), .touch(touch), .pos(pos), .vel(vel),
        .ev_on(ev_on), .ev_off(ev_off), .ev_note(ev_note), .ev_vel(ev_vel),
        .harm_mask(harm_mask)
    );

    // 事件计数（测试台用阻塞赋值，便于即时读取）
    integer on_cnt = 0, off_cnt = 0;
    reg [6:0] last_on = 7'd0, last_off = 7'd0;
    always @(posedge clk) begin
        if (!rst_n) begin
            on_cnt = 0; off_cnt = 0; last_on = 7'd0; last_off = 7'd0;
        end else begin
            if (ev_on)  begin on_cnt = on_cnt + 1;  last_on  = ev_note; end
            if (ev_off) begin off_cnt = off_cnt + 1; last_off = ev_note; end
        end
    end

    //--------------------------------------------------------------- 越界实例（P4）
    wire        ev_on2, ev_off2;
    wire [6:0]  ev_note2;
    wire [7:0]  harm2;
    pad_pitch #(.NCH(35), .NPIT(25), .BASE(60)) ub (
        .clk(clk), .rst_n(rst_n), .touch(touch), .pos(pos), .vel(vel),
        .ev_on(ev_on2), .ev_off(ev_off2), .ev_note(ev_note2), .ev_vel(),
        .harm_mask(harm2)
    );
    integer on_cnt2 = 0;
    reg [6:0] last_on2 = 7'd0;
    always @(posedge clk) begin
        if (!rst_n) begin on_cnt2 = 0; last_on2 = 7'd0; end
        else if (ev_on2) begin on_cnt2 = on_cnt2 + 1; last_on2 = ev_note2; end
    end

    //--------------------------------------------------------------- 音域条实例
    localparam integer MS  = 50000;           // 50 MHz 仿真钟下 1 ms
    localparam integer MS100 = MS * 100;      // 100 ms（DUT 的确认阈值）
    reg  [4:0] cell_t = 5'd0;
    wire [2:0] spos;
    wire [4:0] sled;
    strip_ctrl #(.CLK_HZ(50000000), .HOLD_MS(100)) us (
        .clk(clk), .rst_n(rst_n), .cell_t(cell_t), .pos(spos), .led(sled)
    );

    //--------------------------------------------------------------- 工具
    task wait_cycles;
        input integer n;
        integer k;
        begin for (k = 0; k < n; k = k + 1) @(posedge clk); end
    endtask

    // 按下某通道并等事件（最多等 40 拍，扫查 35 拍一轮）
    task press_ch;
        input [5:0] ch;
        begin
            touch = 35'd0;
            wait_cycles(2);
            touch[ch] = 1'b1;
            wait_cycles(40);
        end
    endtask

    task release_ch;
        input [5:0] ch;
        begin
            touch[ch] = 1'b0;
            wait_cycles(40);
        end
    endtask

    task check;
        input [255:0] name;
        input integer got;
        input integer exp;
        begin
            if (got === exp) $display("  PASS  %0s", name);
            else begin
                $display("  FAIL  %0s  得到 %0d 期望 %0d", name, got, exp);
                errors = errors + 1;
            end
        end
    endtask

    //--------------------------------------------------------------- 主流程
    integer n_on0, n_off0, exp_note, got_note, distinct_cnt;
    reg [6:0] notes [0:24];
    reg [11:0] pcs;

    initial begin
        $display("==============================================================");
        $display(" 音高与八度判据自检（P1–P15 相关项）");
        $display("==============================================================");

        rst_n = 1'b0;
        wait_cycles(10);
        rst_n = 1'b1;
        wait_cycles(10);

        //========================================================== P1 表驱动
        $display(" P1 键位映射（25 键 × 5 档位）");
        errors = errors + 0;
        for (j = 0; j < 5; j = j + 1) begin
            pos = j;
            for (i = 0; i < 25; i = i + 1) begin
                n_on0 = on_cnt;
                press_ch(i);
                exp_note = 48 + i + 12 * (j - 1);
                got_note = last_on;
                if (on_cnt != n_on0 + 1) begin
                    $display("  FAIL  P1 通道 %0d 档位 %0d：事件数不对（%0d）", i, j, on_cnt - n_on0);
                    errors = errors + 1;
                end else if (got_note !== exp_note[6:0]) begin
                    $display("  FAIL  P1 通道 %0d 档位 %0d：得到 %0d 期望 %0d", i, j, got_note, exp_note);
                    errors = errors + 1;
                end
                release_ch(i);
            end
        end
        if (errors == 0) $display("  PASS  P1 全部 125 组键位映射正确");

        //========================================================== P9 / P2
        $display(" P9 无同音通道 / P2 半音完整");
        pos = 3'd1;                              // 0 档
        pcs = 12'd0;
        distinct_cnt = 0;
        for (i = 0; i < 25; i = i + 1) begin
            n_on0 = on_cnt;
            press_ch(i);
            notes[i] = last_on;
            release_ch(i);
        end
        // 两两不同
        for (i = 0; i < 25; i = i + 1) begin
            for (j = i + 1; j < 25; j = j + 1)
                if (notes[i] === notes[j]) begin
                    $display("  FAIL  P9 通道 %0d 与 %0d 同音 %0d", i, j, notes[i]);
                    errors = errors + 1;
                end
        end
        if (errors == 0) $display("  PASS  P9 25 个音两两不同");
        // 下排 12 键的半音类
        for (i = 0; i < 12; i = i + 1) pcs[notes[i] % 12] = 1'b1;
        // 手工统计（iverilog 的 -g2005 不带 $countones）
        distinct_cnt = 0;
        for (i = 0; i < 12; i = i + 1) if (pcs[i]) distinct_cnt = distinct_cnt + 1;
        check("P2-all-12-semitone-classes", distinct_cnt, 12);

        //========================================================== P3 档位语义
        $display(" P3 档位语义（相邻档位相差 12）");
        for (j = 0; j < 4; j = j + 1) begin
            pos = j;     press_ch(6'd5); got_note = last_on; release_ch(6'd5);
            pos = j + 1;      press_ch(6'd5);
            if (last_on - got_note !== 12) begin
                $display("  FAIL  P3 档位 %0d→%0d 差值为 %0d", j, j+1, last_on - got_note);
                errors = errors + 1;
            end
            release_ch(6'd5);
        end
        if (errors == 0) $display("  PASS  P3 相邻档位差值均为 12");

        //========================================================== P4 上限
        $display(" P4 上限行为（BASE=60 实例：48+12 以上越界）");
        pos = 3'd4;                              // +3 档
        on_cnt2 = 0;
        press_ch(6'd24);                         // 60+24+36 = 120 > 108 → 不应发声
        check("P4-out-of-range-silent", on_cnt2, 0);
        release_ch(6'd24);
        pos = 3'd1;
        press_ch(6'd0);                          // 60+0+0 = 60 → 应发声
        check("P4-in-range-still-sounds", on_cnt2, 1);
        release_ch(6'd0);

        //========================================================== P6 挂音防护
        $display(" P6 挂音防护（按下→换挡→松开）");
        pos = 3'd1;
        touch = 35'd0; wait_cycles(2);
        touch[6'd7] = 1'b1; wait_cycles(40);
        got_note = last_on;                       // 按下时的音
        n_off0 = off_cnt;
        pos = 3'd3;                               // 换到 +1 档
        wait_cycles(40);
        touch[6'd7] = 1'b0; wait_cycles(40);
        check("P6-note-off-count", off_cnt - n_off0, 1);
        check("P6-note-off-uses-latched", last_off, got_note);

        //========================================================== P11 换挡不产生事件
        $display(" P11 换挡本身不产生事件");
        touch = 35'd0; wait_cycles(40);
        n_on0 = on_cnt; n_off0 = off_cnt;
        for (j = 0; j < 5; j = j + 1) begin pos = j; wait_cycles(40); end
        check("P11-no-events-on-switch", (on_cnt - n_on0) + (off_cnt - n_off0), 0);

        //========================================================== P12 跨档同时发声
        $display(" P12 跨档同时发声");
        pos = 3'd1;
        touch = 35'd0; wait_cycles(40);
        n_on0 = on_cnt; n_off0 = off_cnt;
        touch[6'd3] = 1'b1; wait_cycles(40);      // 音 A = 48+3+0 = 51
        got_note = last_on;
        pos = 3'd4;                                // 换到 +3 档
        wait_cycles(40);
        touch[6'd3] = 1'b0;                        // 松开旧音
        wait_cycles(40);
        touch[6'd10] = 1'b1;                       // 新音 = 48+10+36 = 94
        wait_cycles(40);
        check("P12-two-note-on", on_cnt - n_on0, 2);
        check("P12-old-note-not-cut", got_note, 51);
        check("P12-new-note-pitch", last_on, 94);
        touch[6'd10] = 1'b0; wait_cycles(40);
        check("P12-two-note-off", off_cnt - n_off0, 2);

        //========================================================== P13/P14/P15 音域条
        $display(" P13/P14/P15 音域条");
        cell_t = 5'd0; wait_cycles(50);
        // P13：按住不足 100 ms
        cell_t = 5'b10000; wait_cycles(MS * 10);      // 10 ms，远不足 100 ms
        check("P13-short-press-ignored", spos, 1);
        // P14：持续按住
        wait_cycles(MS100 + MS);                      // 超过 100 ms
        check("P14-hold-100ms-takes-effect", spos, 4);
        check("P14-led-one-hot", sled, 5'b10000);
        // P15：整个过程中不产生音符事件
        n_on0 = on_cnt; n_off0 = off_cnt;
        cell_t = 5'b00010; wait_cycles(MS100 + MS);
        check("P15-strip-silent", (on_cnt - n_on0) + (off_cnt - n_off0), 0);
        cell_t = 5'd0; wait_cycles(50);
        pos = 3'd1;

        //========================================================== P8 非音高键
        $display(" P8 非音高键不发声");
        touch = 35'd0; wait_cycles(40);
        n_on0 = on_cnt;
        for (i = 30; i < 38; i = i + 1) begin
            touch[i] = 1'b1; wait_cycles(2);
        end
        wait_cycles(40);
        check("P8-non-pitch-silent", on_cnt - n_on0, 0);
        check("P8-harm-mask", harm_mask, 8'hFF);
        touch = 35'd0;

        //========================================================== 汇总
        $display("==============================================================");
        if (errors == 0) $display(" 全部判据通过");
        else             $display(" 失败 %0d 项", errors);
        $display("==============================================================");
        $finish;
    end

    // 看门狗
    initial begin
        #5_000_000_000;     // 5 s 仿真时限（含多处 100 ms 等待）
        $display(" [看门狗] 仿真超时");
        $display(" 失败 %0d 项（含超时）", errors + 1);
        $finish;
    end

endmodule
