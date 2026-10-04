//=============================================================================
// tb_perf.v —— 演奏交互层（M1/M9）验收
//
// 【判据设计（这是本测试台的全部意义）】
//   M1 原文：「≥2 个独立可控演奏维度」，判据是"现场演示可分别操控"。
//   所以核心判据必须是【交叉测试】：
//     P1 只动维度1（选音）→ 音高变，力度【必须一点不变】
//     P2 只动维度2（力度）→ 力度变，音高【必须一点不变】
//   这两条同时成立，才叫"独立可控"；只证明"两个都能变"是不够的。
//
//   P3 锁存：触发之后再动维度，正在响的音【不能变】（真实乐器的语义）
//   P4 拨弦/力度感应：挥手越快 → 力度越大（单调）
//   P5 控制侧延迟：触发脉冲 → 引擎取样生效的拍数（补 E5 里"不含控制侧"那段）
//   P6 松手收声：pads 落下 → 发出 note-off
//
// 【四种测试】
//   test=0  交叉测试 A：固定力度，扫选音维度，逐个触发
//   test=1  交叉测试 B：固定音高，扫力度维度，逐个触发
//   test=2  锁存 + 松手收声（触发后双维同时改，看已发音是否被改）
//   test=3  变化率三档（挥手快慢 → 力度单调）
//   test=4  集成：sensor_sim → perf_ctrl → tdm_top 的 ev_* → 真引擎发声 + 量延迟
//
// 【为什么要 test=4】前三项只证明"动作总线对"；只有让真引擎出声并量出延迟，
//   才能说"这套东西接上引擎能弹"，同时给 E5 补上控制侧那一段实测。
//=============================================================================

`timescale 1ns/1ps

module tb_perf;

    localparam integer CLK_HALF = 19;      // ≈27 MHz（与出货同量级）
    localparam integer NSLOT    = 512;     // 与出货一致

    reg clk = 1'b0;
    reg rst_n;
    always #(CLK_HALF) clk = ~clk;

    //-------------------------------------------------------------------------
    // 本地 sample_en（周期 = NSLOT，与出货一致）
    //-------------------------------------------------------------------------
    reg [9:0] pc;
    wire sample_en = (pc == NSLOT - 1);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                  pc <= 10'd0;
        else if (pc == NSLOT - 1)    pc <= 10'd0;
        else                         pc <= pc + 10'd1;
    end

    //-------------------------------------------------------------------------
    // 被测核心（模块级）
    //-------------------------------------------------------------------------
    reg  [2:0]  which;
    reg         en;
    reg  [15:0] m1_raw, m2_raw;
    reg         m1_vld, m2_vld;
    reg  [3:0]  pads;
    reg  [3:0]  m1_shift, m2_shift;
    reg  [15:0] m1_lo, rate_th;
    reg  [6:0]  note_lo;
    reg         rate_en;
    reg  [3:0]  rate_shift;
    reg  [19:0] gate_len;

    wire        act_valid, act_on;
    wire [6:0]  act_note;
    wire [3:0]  act_vel;
    wire [6:0]  dim_note;
    wire [3:0]  dim_vel;
    wire [15:0] rate_dbg;
    wire        activity;

    perf_ctrl #(.NB(7), .GATE_W(20)) u_pc (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .m1_raw(m1_raw), .m1_vld(m1_vld),
        .m2_raw(m2_raw), .m2_vld(m2_vld),
        .pads(pads),
        .en(en), .m1_shift(m1_shift), .m1_lo(m1_lo), .note_lo(note_lo),
        .m2_shift(m2_shift), .rate_en(rate_en), .rate_th(rate_th),
        .rate_shift(rate_shift), .gate_len(gate_len),
        .act_valid(act_valid), .act_on(act_on), .act_note(act_note), .act_vel(act_vel),
        .dim_note(dim_note), .dim_vel(dim_vel), .rate_dbg(rate_dbg), .activity(activity)
    );

    //-------------------------------------------------------------------------
    // 集成用：第二份核心 → 直接驱动 tdm_top 的 ev_*（不动 RTL 就能证明整链）
    //-------------------------------------------------------------------------
    reg  [15:0] i_m1, i_m2;
    reg         i_m1v, i_m2v;
    reg  [3:0]  i_pads;
    wire        i_av, i_aon;
    wire [6:0]  i_an;
    wire [3:0]  i_av_v;

    perf_ctrl #(.NB(7), .GATE_W(20)) u_pc2 (
        .clk(clk), .rst_n(rst_n), .sample_en(sample_en),
        .m1_raw(i_m1), .m1_vld(i_m1v), .m2_raw(i_m2), .m2_vld(i_m2v), .pads(i_pads),
        .en(en), .m1_shift(m1_shift), .m1_lo(m1_lo), .note_lo(note_lo),
        .m2_shift(m2_shift), .rate_en(rate_en), .rate_th(rate_th),
        .rate_shift(rate_shift), .gate_len(gate_len),
        .act_valid(i_av), .act_on(i_aon), .act_note(i_an), .act_vel(i_av_v),
        .dim_note(), .dim_vel(), .rate_dbg(), .activity()
    );

    //-------------------------------------------------------------------------
    // 传感器仿真器（集成测试用）
    //-------------------------------------------------------------------------
    reg  [2:0]  sim_mode;
    reg         sim_run;
    reg  [15:0] sim_m1s, sim_m1st, sim_m2s, sim_m2st;
    reg  [7:0]  sim_n;
    wire [15:0] sim_m1, sim_m2;
    wire        sim_m1v, sim_m2v;
    wire [3:0]  sim_pads;

    sensor_sim #(.PERIOD(3000)) u_sim (
        .clk(clk), .rst_n(rst_n), .run(sim_run),
        .mode(sim_mode), .m1_start(sim_m1s), .m1_step(sim_m1st),
        .m2_start(sim_m2s), .m2_step(sim_m2st), .n_upd(sim_n),
        .m1_raw(sim_m1), .m2_raw(sim_m2),
        .m1_vld(sim_m1v), .m2_vld(sim_m2v), .pads(sim_pads)
    );

    //-------------------------------------------------------------------------
    // 真引擎（集成测试）
    //-------------------------------------------------------------------------
    wire [5:0] led;
    tdm_top u_top (
        .clk(clk), .rst_n(rst_n),
        .ev_valid(i_av), .ev_on(i_aon), .ev_note(i_an), .ev_vel(i_av_v),
        .preset(2'd1), .test_mode(1'b0),
        .uart_rx_pin(1'b1), .uart_tx_pin(),
        .led(led), .dac_din(), .dac_ws(), .dac_bck(), .pa_en()
    );

    //-------------------------------------------------------------------------
    // 集成接线：传感器仿真器 → 集成核心（每时钟连续，不能丢窄脉冲）
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            i_m1 <= 16'd0; i_m2 <= 16'd0;
            i_m1v <= 1'b0; i_m2v <= 1'b0; i_pads <= 4'd0;
        end
        else begin
            i_m1   <= sim_m1;
            i_m2   <= sim_m2;
            i_m1v  <= sim_m1v;
            i_m2v  <= sim_m2v;
            i_pads <= sim_pads;
        end
    end

    //-------------------------------------------------------------------------
    // 记录：动作总线事件 + 每样本的维度值
    //-------------------------------------------------------------------------
    integer fev, fdim, flog;
    integer ns;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)      ns <= 0;
        else if (sample_en) ns <= ns + 1;
    end

    always @(posedge clk) begin
        if (rst_n && act_valid)
            $fdisplay(fev, "%0d %0d %0d %0d", ns, act_on, act_note, act_vel);
    end

    // 集成记录：触发时刻 + 引擎侧状态
    integer t_trig;
    reg     trig_seen;
    reg [24:0] inc_probe;
    always @(posedge clk) begin
        if (rst_n && i_av && i_aon && !trig_seen && which == 3'd4) begin
            trig_seen <= 1'b1;
            t_trig    <= ns;
        end
    end

    //-------------------------------------------------------------------------
    // 辅助任务
    //-------------------------------------------------------------------------
    task upd(input [15:0] v1, input [15:0] v2);
        begin
            @(posedge clk);
            m1_raw <= v1; m2_raw <= v2;
            m1_vld <= 1'b1; m2_vld <= 1'b1;
            @(posedge clk);
            m1_vld <= 1'b0; m2_vld <= 1'b0;
            repeat (20) @(posedge clk);
        end
    endtask

    task press(input [3:0] p, input integer dur);
        begin
            @(posedge clk);
            pads <= p;
            repeat (dur) @(posedge clk);
        end
    endtask

    task wait_samples(input integer n);
        integer q;
        begin
            for (q = 0; q < n; q = q + 1) begin
                @(posedge clk);
                while (!sample_en) @(posedge clk);
            end
        end
    endtask

    integer i;
    initial begin
        if (!$value$plusargs("test=%d", which)) which = 3'd0;

        // 缺省配置：选音 64 个原始值/半音、力度 4 个原始值/级
        en        = 1'b1;
        m1_shift  = 4'd6;      // 64/半音
        m2_shift  = 4'd2;      // 4/级
        m1_lo     = 16'd100;
        note_lo   = 7'd60;
        rate_shift= 4'd4;
        rate_th   = 16'd50;
        rate_en   = 1'b0;
        gate_len  = 20'd5000;  // 自动收声 ≈ 95 ms
        m1_raw    = 16'd100;
        m2_raw    = 16'd0;
        m1_vld    = 1'b0; m2_vld = 1'b0;
        pads      = 4'd0;
        i_m1 = 16'd100; i_m2 = 16'd0; i_m1v = 1'b0; i_m2v = 1'b0; i_pads = 4'd0;
        sim_run = 1'b0; sim_mode = 3'd1; sim_n = 8'd16;
        sim_m1s = 16'd1000; sim_m1st = 16'd64; sim_m2s = 16'd60; sim_m2st = 16'd4;
        trig_seen = 1'b0; t_trig = 0; ns = 0;

        rst_n = 1'b0;
        repeat (40) @(posedge clk);
        rst_n = 1'b1;
        repeat (100) @(posedge clk);

        case (which)
            //=================================================================
            3'd0: begin
                fev = $fopen("perf_a.txt", "w");
                $display("==============================================================");
                $display(" test=0 交叉测试 A：固定力度(60)，只扫【选音维度】并逐个触发");
                $display("==============================================================");
                m2_raw = 16'd60;                 // 力度固定 → 15 级
                for (i = 0; i < 8; i = i + 1) begin
                    upd(16'd100 + i * 16'd64, 16'd60);   // 音高 60,61,...,67
                    press(4'b0001, 40);                  // 触发
                    press(4'b0000, 40);                  // 松手
                end
                repeat (200) @(posedge clk);
                $fclose(fev);
                $display("  → perf_a.txt  （期望：音高递增 60..67，力度恒为 15）");
            end
            //=================================================================
            3'd1: begin
                fev = $fopen("perf_b.txt", "w");
                $display("==============================================================");
                $display(" test=1 交叉测试 B：固定音高，只扫【力度维度】并逐个触发");
                $display("==============================================================");
                for (i = 0; i < 16; i = i + 1) begin
                    upd(16'd100 + 16'd192, i * 16'd4);   // 音高固定 63；力度 0..15
                    press(4'b0001, 40);
                    press(4'b0000, 40);
                end
                repeat (200) @(posedge clk);
                $fclose(fev);
                $display("  → perf_b.txt  （期望：力度递增 0..15，音高恒为 63）");
            end
            //=================================================================
            3'd2: begin
                fev  = $fopen("perf_latch.txt", "w");
                fdim = $fopen("perf_latch_dim.txt", "w");
                $display("==============================================================");
                $display(" test=2 锁存：触发后同时改两个维度，已发音不许变；松手才收声");
                $display("==============================================================");
                upd(16'd100 + 16'd192, 16'd60);      // 音高 63、力度 15
                press(4'b0001, 100);                 // 按下 = 触发（锁存 63/15）
                // 按住不放，同时把两个维度都推到别处
                for (i = 0; i < 8; i = i + 1) begin
                    upd(16'd100 + 16'd640 + i * 16'd64, 16'd0);  // 音高 70..、力度 0
                    $fdisplay(fdim, "%0d %0d %0d", dim_note, dim_vel, activity);
                end
                press(4'b0000, 100);                 // 松手 = 收声
                upd(16'd100 + 16'd640, 16'd0);       // 再按一次应使用【新】维度值
                press(4'b0001, 100);
                press(4'b0000, 100);
                repeat (200) @(posedge clk);
                $fclose(fev); $fclose(fdim);
                $display("  → perf_latch.txt（期望：全程只有 63/15 的 on 与 off，最后才出现 70/0）");
            end
            //=================================================================
            3'd3: begin
                fev = $fopen("perf_rate.txt", "w");
                $display("==============================================================");
                $display(" test=3 变化率触发：三档挥速 → 力度应单调上升");
                $display("==============================================================");
                rate_th  = 16'd60;
                note_lo  = 7'd60;
                // 每次挥完要"把手移回去"重新起手，而移回去本身也是一次大挥
                //   ⇒ 复位期间必须【关掉变化率触发】，否则每次都会多出一个假触发
                //   （第一版实测 4/4/10/10/15，把单调性判据搅乱）。
                m1_raw = 16'd1000; m2_raw = 16'd0;
                upd(16'd1000, 16'd0);
                // 三档：小挥 64、中挥 160、大挥 320
                for (i = 0; i < 3; i = i + 1) begin
                    rate_en = 1'b0;                       // 起手复位：不计触发
                    m1_raw = 16'd1000; m2_raw = 16'd0;
                    upd(16'd1000, 16'd0);
                    upd(16'd1000, 16'd0);
                    rate_en = 1'b1;                       // 只对这一次挥动计数
                    if (i == 0) upd(16'd1000 - 16'd64,  16'd0);
                    if (i == 1) upd(16'd1000 - 16'd160, 16'd0);
                    if (i == 2) upd(16'd1000 - 16'd320, 16'd0);
                    rate_en = 1'b0;
                    wait_samples(60);          // 等自动收声
                end
                repeat (400) @(posedge clk);
                $fclose(fev);
                $display("  → perf_rate.txt（期望：力度 4 / 10 / 15 递增）");
            end
            //=================================================================
            default: begin
                flog = $fopen("perf_int.txt", "w");
                $display("==============================================================");
                $display(" test=4 集成：传感器仿真器 → 交互核心 → ev_* → 真引擎发声");
                $display("==============================================================");
                // 传感器慢慢靠近：每次测量 64 个原始值 = 1 个半音
                en       = 1'b1;
                // 开变化率触发（挥手=拨弦）：慢扫时每次测量都触发一个音。
                //   第一版这里写 rate_en=0，结果整个集成测试一个音都不发 ——
                //   pads 也没动，等于什么都没测到。
                rate_en    = 1'b1;
                rate_th    = 16'd60;
                rate_shift = 4'd4;
                sim_mode = 3'd1;
                sim_m1s  = 16'd1000;
                sim_m1st = 16'd64;
                sim_m2s  = 16'd60;
                sim_n    = 8'd6;
                sim_run  = 1'b1;
                // 仿真器的总线接到集成核心
                // 接线必须【每时钟连续监视】，不能放在"每样本一次"的循环里：
                //   sim_m1v/m2v 只有一个时钟宽，而样本周期 512 拍 ——
                //   在循环里看等于 1/512 的概率撞上，结果是"一个事件都没有"。
                //   这个坑 tb_seq 已经栽过一次，这里又栽了一次，故写死在注释里。
                for (i = 0; i < 20000; i = i + 1) begin
                    @(posedge clk);
                    while (!sample_en) @(posedge clk);
                    $fdisplay(flog, "%0d %0d %0d %0d %0d %0d",
                              ns, i_an, i_aon, i_av,
                              u_top.u_tdm.inc_mem[0], u_top.u_tdm.amp_mem[0]);
                end
                $fclose(flog);
                $display("  → perf_int.txt（看组 0 的 inc/amp 是否随动作变化，以及触发→生效拍数）");
            end
        endcase
        $finish;
    end

    initial begin
        #900_000_000;
        $display("[TIMEOUT] test=%0d", which);
        $finish;
    end

endmodule
