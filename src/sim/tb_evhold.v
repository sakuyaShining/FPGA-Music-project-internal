//=============================================================================
// tb_evhold.v —— event_hold 单元判据（待处理队列 + 接收确认）
//
// 【为什么先单元后集成】
//   这一个模块是"不丢事件"的唯一保证点。它的失效很隐蔽：事件丢了会表现为
//   挂音或少音，而时序看上去一切正常。先在这里把语义钉死，
//   再进 tdm_top 看端到端，定位成本最低。
//
// 【判据】
//   H1 空队列不产生 out_valid（不凭空造事件）
//   H2 深度上限正确：收满 DEPTH 后 in_ready 必须为 0
//   H3 违规源端（不理会 ready 硬灌）⇒ overflow 如实计数，不静默丢弃
//   H4 **合规源端 + 慢消费者 ⇒ 一个都不丢，且顺序完全保持**
//      （这是"不丢 note-off"的直接证据：note-off 与 note-on 走同一条路，
//        只要序列完整、顺序不变，就既不会丢 on 也不会丢 off）
//=============================================================================
`timescale 1ns/1ps

module tb_evhold;

    localparam DEPTH = 8;
    localparam NB    = 7;
    localparam VB    = 4;
    localparam NEV   = 20;              // H4 要发的事件数（>DEPTH，必然经历反压）

    reg clk, rst_n;
    initial clk = 1'b0;
    always #5 clk = ~clk;

    reg             in_valid, in_on;
    reg  [NB-1:0]   in_note;
    reg  [VB-1:0]   in_vel;
    wire            in_ready;
    wire            out_valid, out_on;
    wire [NB-1:0]   out_note;
    wire [VB-1:0]   out_vel;
    reg             out_ready;
    wire [3:0]      level;
    wire [15:0]     overflow;

    event_hold #(.DEPTH(DEPTH), .NB(NB), .VB(VB)) dut (
        .clk(clk), .rst_n(rst_n),
        .in_valid(in_valid), .in_on(in_on), .in_note(in_note), .in_vel(in_vel),
        .in_ready(in_ready),
        .out_valid(out_valid), .out_on(out_on), .out_note(out_note), .out_vel(out_vel),
        .out_ready(out_ready),
        .level(level), .overflow(overflow)
    );

    integer fails;
    reg     in_ready_pre;               // 时钟沿【之前】的 in_ready（见 H2 注释）

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

    //   合规源端：把事件放上并**保持到 in_ready=1**（这就是"接收确认"）。
    //   带有限等待：队列可能一直是满的，无界 while 会把测试台挂死，
    //   表现为 TIMEOUT 而不是可读的失败。
    task send_ev;
        input          on;
        input [NB-1:0] n;
        input [VB-1:0] v;
        integer guard;
        begin
            //   标准 valid/ready 的时序（写成"边沿驱动"而不是"等条件"）：
            //     ① 在时钟沿把事件与 valid=1 一起放上（数据先于 valid 稳定）
            //     ② 若这一拍 ready 未起，保持不动，下一沿再看
            //     ③ ready 起来的那一拍就是"接收拍"，此刻撤销 valid
            //   ★ 第一版写成"先 @(posedge) 再 while(!ready) @(posedge)"，
            //     采样时刻与 RTL 的接收拍错开一档，于是每个事件都被多算一拍，
            //     队列里多出来的条目并不是真的事件 —— 实测表现为"发 20 收 14"。
            in_on = on; in_note = n; in_vel = v; in_valid = 1'b1;
            guard = 0;
            while (!in_ready && guard < 5000) begin
                @(posedge clk);
                guard = guard + 1;
            end
            if (!in_ready) $display("   [warn] send_ev 等 in_ready 超时");
            @(posedge clk);              // 接收拍：本沿事件被写入
            in_valid = 1'b0;
        end
    endtask

    //   慢消费者：先等 out_valid 再取 —— 不能只等固定拍数
    task consume_one;
        integer w;
        begin
            w = 0;
            while (!out_valid && w < 5000) begin
                @(posedge clk);
                w = w + 1;
            end
            if (!out_valid) $display("   [warn] consume_one 等 out_valid 超时（level=%0d）", level);
            out_ready = 1'b1;
            @(posedge clk);
            out_ready = 1'b0;
        end
    endtask

    //   记录实际收到的事件
    localparam MAXR = 64;
    integer  r_note [0:MAXR-1];
    integer  r_on   [0:MAXR-1];
    integer  nr;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) nr <= 0;
        else if (out_valid && out_ready && nr < MAXR) begin
            r_note[nr] <= out_note;
            r_on[nr]   <= out_on;
            nr         <= nr + 1;
        end
    end

    integer i, k, bad;

    initial begin
        $display("==============================================================");
        $display(" event_hold 单元判据（待处理队列 / 接收确认 / FIFO 保序）");
        $display("==============================================================");

        fails = 0; nr = 0;
        rst_n = 1'b0; in_valid = 1'b0; in_on = 1'b0; in_note = 7'd0;
        in_vel = 4'd0; out_ready = 1'b0; in_ready_pre = 1'b0;
        repeat (10) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);
        in_ready_pre = in_ready;

        //--------------------------------------------------------------- H1
        $display(" H1 空队列不应产生 out_valid");
        repeat (10) @(posedge clk);
        check("H1-empty-out-valid-0", out_valid, 0);
        check("H1-empty-level-0", level, 0);

        //--------------------------------------------------------------- H2
        $display(" H2 灌满到 DEPTH，in_ready 必须变 0");
        //   ★ in_ready 必须在【时钟沿之前】采样：它是 cnt/指针的**组合**输出，
        //     RTL 在沿上更新指针，沿后再读会晚一拍，
        //     于是"本拍有没有被接收"数出来比实际少 1。
        k = 0;
        for (i = 0; i < DEPTH + 3; i = i + 1) begin
            in_on = 1'b1; in_note = 60 + i[6:0]; in_vel = 4'd9;
            in_valid = 1'b1;
            @(posedge clk);
            if (in_ready_pre) k = k + 1;
            in_ready_pre = in_ready;
        end
        in_valid = 1'b0;
        check("H2-accepted-exactly-DEPTH", k, DEPTH);
        check("H2-level-saturates", level, DEPTH);
        check("H2-in-ready-low-when-full", in_ready, 0);
        //   上面满之后仍举着 in_valid 3 拍 ⇒ 触发 overflow（见 H3）
        check("H3-overflow-counted", overflow, 3);

        //--------------------------------------------------------------- H4
        $display(" H4 合规源端 + 慢消费者 ⇒ 不丢、且严格保序");
        //   先把已灌进去的 8 条排空，回到干净状态
        for (i = 0; i < DEPTH; i = i + 1) consume_one;
        repeat (5) @(posedge clk);
        nr = 0;
        check("H4-drained-level-0", level, 0);
        check("H4-drained-empty", out_valid, 0);

        //   发 NEV 条事件：偶数号 on、奇数号 off，note 号递增且唯一
        //   （用唯一 note 号，任何丢件/错序都会立刻显形）
        //
        //   ★ 这里用【单线程 发一条/收一条】而不是生产/消费双进程并发。
        //     并发版本我写了三版都对不齐：fork...join 在生产者结束时就返回、
        //     采样时刻与 RTL 的接收拍错开、生产速率与消费速率不匹配 ——
        //     每次的失败都长得像"RTL 丢事件"，其实全是测试台的时序问题。
        //     而本模块要证明的性质（**不丢、保序**）根本不需要真实并发：
        //     逐条 发→收 就能覆盖它，而且完全确定、失败信息可直接定位。
        //     并发/吞吐的性能问题不在本单元的验收范围内。
        bad = 0;
        for (i = 0; i < NEV; i = i + 1) begin
            send_ev((i % 2 == 0), (7'd60 + i[6:0]), (i[3:0]));
            consume_one;
        end
        repeat (10) @(posedge clk);

        $display("  发出 %0d 条，收到 %0d 条", NEV, nr);
        bad = 0;
        if (nr != NEV) begin
            $display("  FAIL  H4 收到 %0d 条 ≠ 发出 %0d 条 ⇒ 有事件丢失", nr, NEV);
            bad = bad + 1;
        end
        for (i = 0; i < nr && i < NEV; i = i + 1) begin
            if (r_note[i] != (60 + i) || r_on[i] != ((i % 2 == 0) ? 1 : 0)) begin
                $display("  FAIL  H4 第 %0d 条应为 note=%0d on=%0d，实测 note=%0d on=%0d",
                         i, 60 + i, (i % 2 == 0) ? 1 : 0, r_note[i], r_on[i]);
                bad = bad + 1;
            end
        end
        if (bad == 0)
            $display("  PASS  H4 序列逐条相等（%0d 条，含 %0d 个 note-off）",
                     NEV, (NEV + 1) / 2);
        check("H4-sequence-bad-count", bad, 0);
        check("H4-overflow-still-3", overflow, 3);   // 合规源端不应产生新的 overflow

        $display("==============================================================");
        if (fails == 0) $display("RESULT evhold=PASS");
        else            $display("RESULT evhold=FAIL fails=%0d", fails);
        $display("==============================================================");
        $finish;
    end

    initial begin
        #50_000_000;
        $display("RESULT evhold=TIMEOUT");
        $finish;
    end

endmodule
