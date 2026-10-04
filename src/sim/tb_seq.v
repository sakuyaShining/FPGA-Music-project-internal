//=============================================================================
// tb_seq.v —— 片上曲目定序器（E7）＋ LED 指引（E6 的 LED 部分）验收
//
// 【判据怎么可证伪】
//   把定序器发出的【音符事件】逐条记下来（音高 + 第几个样本 + 开/关），
//   再按曲谱与 tempo_inc 用 Python 独立算一遍时间戳，逐条比对。
//   另外逐样本记 LED：拍点应在每一拍的第 0 个样本拉高并保持约 40 ms，
//   音高编号应等于当前步的音高低 5 位。
//
//   两种节奏都测（+test=0 慢 / +test=1 快）：证明 tempo_inc 真的在控制速度，
//   而不是"时间戳恰好对上"。
//=============================================================================

`timescale 1ns/1ps

module tb_seq;

    localparam integer PERIOD = 16;      // 每 16 拍一个样本（采样率本身不影响判据）

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

    reg [2:0]  which;
    reg        enable, hold;
    reg [23:0] tempo_inc;
    reg [7:0]  vel;

    wire        ev_valid, ev_on, beat;
    wire [6:0]  ev_note, cur_note;
    wire [7:0]  ev_vel, step_dbg;

    song_seq #(.NB(7), .NSTEP(15)) u_seq (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .enable(enable), .hold(hold), .tempo_inc(tempo_inc), .vel(vel),
        // ★ 新增的曲谱下载端口必须显式固定：
        //   悬空输入在 Verilog 里是 z，`use_ram ? ... : ...` 遇到 z 会整体变 x
        //   —— 实测表现为"该档一条事件都没有"。模块加了端口，直连它的测试台
        //   必须同步补上（顶层是自动连的，所以只有模块级测试台会中这一枪）。
        .ram_we(1'b0), .ram_sel(1'b0), .ram_note(7'd0), .ram_beats(8'd0),
        .ram_idx(6'd0), .use_ram(1'b0), .ram_len(6'd0),
        .ev_valid(ev_valid), .ev_on(ev_on), .ev_note(ev_note), .ev_vel(ev_vel),
        .beat_pulse(beat), .cur_note(cur_note), .step_dbg(step_dbg)
    );

    //-------------------------------------------------------------------------
    // 记录
    //   ★ ev_valid 只持续【一个时钟】，不能只在 sample_en 那一拍去看它
    //     ——第一版就是这么写的，结果事件一条都没记到（拍点和 LED 都对，
    //     唯独事件全丢，很容易误判成"定序器不发事件"）。
    //     改成用独立 always 块【连续监视】，并用样本计数器打时间戳。
    //-------------------------------------------------------------------------
    integer fev, fled, ns;
    integer samp_cnt;
    reg     rec_on;
    localparam integer NSAMP = 60000;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                 samp_cnt <= 0;
        else if (sample_en)         samp_cnt <= samp_cnt + 1;
    end

    always @(posedge clk) begin
        if (rst_n && rec_on && ev_valid)
            $fdisplay(fev, "%0d %0d %0d %0d", samp_cnt, ev_on, ev_note, ev_vel);
    end

    initial begin
        if (!$value$plusargs("test=%d", which)) which = 3'd0;

        // 慢：一拍 ≈ 13187 样本；快：一拍 ≈ 1319 样本（相差 10 倍）
        //   判据用"同样样本数里跑了几拍"和"拍间隔"，都与 BPM 无关，
        //   只需要两档相差 10 倍即可验证 tempo_inc 真的在控制速度。
        tempo_inc = (which == 3'd1) ? 24'd12720 : 24'd1272;
        vel       = 8'd128;
        enable    = 1'b0;
        hold      = 1'b1;                // 先按住复位到第 0 步
        rec_on    = 1'b0;

        rst_n = 1'b0;
        repeat (20) @(posedge clk);
        rst_n = 1'b1;
        repeat (50) @(posedge clk);

        fev  = $fopen((which == 3'd1) ? "seq_fast.txt" : "seq_slow.txt", "w");
        fled = $fopen((which == 3'd1) ? "led_fast.txt" : "led_slow.txt", "w");

        hold   = 1'b0;
        enable = 1'b1;
        rec_on = 1'b1;
        $display("==============================================================");
        $display(" 曲目定序器测试 test=%0d  tempo_inc=%0d（%s档）",
                 which, tempo_inc, (which == 3'd1) ? "快" : "慢");
        $display("==============================================================");

        for (ns = 0; ns < NSAMP; ns = ns + 1) begin
            @(posedge clk);
            while (!sample_en) @(posedge clk);
            $fdisplay(fled, "%0d %0d %0d %0d", samp_cnt, beat, cur_note, step_dbg);
        end
        rec_on = 1'b0;
        $fclose(fev);
        $fclose(fled);
        $display("  → %s / %s", (which == 3'd1) ? "seq_fast.txt" : "seq_slow.txt",
                 (which == 3'd1) ? "led_fast.txt" : "led_slow.txt");
        $finish;
    end

    initial begin
        #20_000_000;
        $display("[TIMEOUT] test=%0d", which);
        $finish;
    end

endmodule
