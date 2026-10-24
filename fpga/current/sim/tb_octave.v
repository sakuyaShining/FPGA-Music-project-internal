`timescale 1ns/1ps
//=============================================================================
// tb_octave —— 八度档 5 格（单电极直读）的判据
//
// 为什么必须做这一台：
//   八度档的 5 个格子每格只有【一个】电极，不走三电极重心。它读的是
//   rc_delta_store 里"第 75..79 号节点"，而节点号 = row*LANES + lane ——
//   这个编号和"lane*14+ch"的物理编号【不是一回事】（见 D-023 的对照表）。
//   写错编号的后果很隐蔽：读到的是一根音位电极，于是"按某个音会顺带换档"，
//   或者"换档条按下去没反应"，仿真单看波形根本看不出来。
//   所以本台除了查"按了有没有反应"，还查"读的到底是哪几个节点"。
//
// 判据：
//   [1] 5 格逐个按住：single_touch 恰好是对应那一位
//   [2] 5 格全按：5'b11111（各自独立，不是"取最高格"）
//   [3] 滞回：落在 off..on 之间保持原状态；低于 off 才松
//   [4] 坏节点（read_valid=0）：该格报 0，其余格不受影响
//   [5] 标定帧：全部报 0（不能让标定过程被当成"5 格全按"）
//   [6] 地址核对：一帧内被读到的节点必须恰好是 75..79 各一次
//=============================================================================
module tb_octave;

    localparam integer STRIPS      = 1;      // 音位侧只要 1 组，把帧缩到最短
    localparam integer CW          = 12;
    localparam integer NSINGLE     = 5;
    localparam [6:0]   SINGLE_BASE = 7'd75;
    localparam [13:0]  TH_ON       = 14'd60;
    localparam [13:0]  TH_OFF      = 14'd30;

    reg clk = 1'b0;
    always #5 clk = ~clk;

    reg rst_n = 1'b0;

    reg         frame_valid = 1'b0;
    wire        frame_ready;
    reg  [31:0] frame_sequence = 32'd1;
    reg         frame_calibration = 1'b0;
    wire [6:0]  read_address;
    reg  [CW-1:0] read_delta = 12'd0;
    reg         read_valid = 1'b1;
    wire        report_valid;
    reg         report_ready = 1'b0;
    wire [STRIPS-1:0] contact, invalid;
    wire [STRIPS*9-1:0] position;
    wire [STRIPS*(CW+2)-1:0] area;
    wire [NSINGLE-1:0] single_touch;
    wire [31:0] report_sequence;
    wire        report_calibration;

    function [STRIPS*21-1:0] make_map;
        input integer ignored;
        integer n;
        begin
            for (n = 0; n < STRIPS*3; n = n + 1) make_map[n*7 +: 7] = n;
        end
    endfunction

    rc_strip_positions #(
        .STRIPS(STRIPS), .CW(CW), .CONFIRM_FRAMES(1), .NODE_MAP(make_map(0)),
        .NSINGLE(NSINGLE), .SINGLE_BASE(SINGLE_BASE)
    ) dut (
        .clk(clk), .rst_n(rst_n),
        .frame_valid(frame_valid), .frame_ready(frame_ready),
        .frame_sequence(frame_sequence), .frame_calibration(frame_calibration),
        .read_address(read_address), .read_delta(read_delta), .read_valid(read_valid),
        .threshold_on(TH_ON), .threshold_off(TH_OFF),
        .report_valid(report_valid), .report_ready(report_ready),
        .contact(contact), .invalid(invalid), .position(position), .area(area),
        .single_touch(single_touch),
        .report_sequence(report_sequence), .report_calibration(report_calibration)
    );

    //-------------------------------------------------------------------------
    // 电极读回模型：按 read_address 直接查表（read_address 是寄存器输出，本拍稳定）
    //-------------------------------------------------------------------------
    reg [CW-1:0] mem [0:127];
    reg          bad [0:127];

    always @* begin
        read_delta = mem[read_address];
        read_valid = !bad[read_address];
    end

    //-------------------------------------------------------------------------
    // 地址观测：一帧内被读到的节点打点
    //-------------------------------------------------------------------------
    reg [127:0] seen;
    reg [6:0]   addr_q;
    integer     seen_cnt;

    always @(posedge clk) begin
        if (rst_n && read_address !== addr_q) begin
            addr_q <= read_address;
            if (!seen[read_address]) seen_cnt = seen_cnt + 1;
            seen[read_address] <= 1'b1;
        end
    end

    //-------------------------------------------------------------------------
    integer checks = 0;
    integer errors = 0;
    integer i;

    // 跑一帧，结束后 single_touch 就是本帧结论
    //   注意握手顺序：必须先撤 frame_valid 再给 report_ready。
    //   反过来的话，PUBLISH 收下报告的同一拍之后状态机回到 IDLE，
    //   而 frame_valid 还挂着 ⇒ 立刻又起一帧，于是每一帧都读到【上一帧】的数据，
    //   最后一帧还会卡在 PUBLISH 里等 report_ready（本台第一版就踩了这个坑）。
    task automatic do_frame(input cal);
        integer guard;
        begin
            // 所有驱动都在 negedge 改：posedge 是状态机采样的时刻，
            //   在 posedge 同一步里改值会与 always 块抢调度，仿真结果不可依赖
            //   （本台第二版就踩了这个：report_ready 只保持半拍，被当成没给）。
            @(negedge clk);
            frame_calibration = cal;
            frame_valid = 1'b1;
            report_ready = 1'b0;
            guard = 0;
            while (!report_valid && guard < 20000) begin
                @(negedge clk);
                guard = guard + 1;
            end
            if (!report_valid) begin
                $display("      [FAIL] 等不到 report_valid（卡在状态机里）");
                errors = errors + 1;
            end
            @(negedge clk);
            frame_valid  = 1'b0;      // 先撤帧，免得收下报告后又立刻起一帧
            report_ready = 1'b1;
            @(negedge clk);
            report_ready = 1'b0;
            @(negedge clk);
        end
    endtask

    task clear_mem;
        integer n;
        begin
            for (n = 0; n < 128; n = n + 1) begin
                mem[n] = 12'd0;
                bad[n] = 1'b0;
            end
        end
    endtask

    reg [4:0] want;

    task automatic cmp(input integer id);
        begin
            checks = checks + 1;
            if (single_touch !== want) begin
                $display("      [FAIL] 第 %0d 项：single_touch = %b，期望 %b",
                         id, single_touch, want);
                errors = errors + 1;
            end else
                $display("      第 %0d 项：single_touch = %b  OK", id, single_touch);
        end
    endtask

    initial begin
        $dumpfile("tb_octave.vcd");
        $dumpvars(0, tb_octave);

        seen = 128'd0; seen_cnt = 0; addr_q = 7'h7F;

        $display("");
        $display("================================================================");
        $display(" tb_octave —— 八度档 5 格单电极直读（节点 75..79）");
        $display("================================================================");

        clear_mem;
        repeat (4) @(posedge clk);
        rst_n = 1'b1;
        repeat (4) @(posedge clk);

        //---------------------------------------------------------------------
        // [1] 逐格按住
        //---------------------------------------------------------------------
        $display("");
        $display("  [1] 逐格按住");
        for (i = 0; i < NSINGLE; i = i + 1) begin
            clear_mem;
            mem[SINGLE_BASE + i] = 12'd100;
            do_frame(1'b0);
            want = (5'b00001 << i);
            checks = checks + 1;
            if (single_touch !== want) begin
                $display("      [FAIL] 只按第 %0d 格：single_touch = %b，期望 %b",
                         i, single_touch, want);
                errors = errors + 1;
            end else
                $display("      第 %0d 格（节点 %0d）：single_touch = %b  OK",
                         i, SINGLE_BASE + i, single_touch);
        end

        //---------------------------------------------------------------------
        // [2] 全按 —— 必须 5 位全亮，不能只报一格
        //---------------------------------------------------------------------
        clear_mem;
        for (i = 0; i < NSINGLE; i = i + 1) mem[SINGLE_BASE + i] = 12'd100;
        do_frame(1'b0);
        want = 5'b11111;
        cmp(2);

        //---------------------------------------------------------------------
        // [3] 滞回：100 → 40（在 off..on 之间，保持）→ 20（低于 off，松开）
        //---------------------------------------------------------------------
        for (i = 0; i < NSINGLE; i = i + 1) mem[SINGLE_BASE + i] = 12'd40;
        do_frame(1'b0);
        want = 5'b11111;
        cmp(31);

        for (i = 0; i < NSINGLE; i = i + 1) mem[SINGLE_BASE + i] = 12'd20;
        do_frame(1'b0);
        want = 5'b00000;
        cmp(32);

        //---------------------------------------------------------------------
        // [4] 坏节点：第 2 格读失败，其余格不受影响
        //---------------------------------------------------------------------
        clear_mem;
        mem[SINGLE_BASE + 1] = 12'd100;
        mem[SINGLE_BASE + 2] = 12'd100;
        bad[SINGLE_BASE + 2] = 1'b1;
        do_frame(1'b0);
        want = 5'b00010;
        cmp(4);

        //---------------------------------------------------------------------
        // [5] 标定帧：全部报 0
        //---------------------------------------------------------------------
        clear_mem;
        for (i = 0; i < NSINGLE; i = i + 1) mem[SINGLE_BASE + i] = 12'd100;
        do_frame(1'b1);
        want = 5'b00000;
        cmp(5);

        //---------------------------------------------------------------------
        // [6] 地址核对：一帧内必须恰好读到 75..79 各一次
        //     （音位侧 STRIPS=1 只读节点 0..2，与 75..79 不重叠）
        //---------------------------------------------------------------------
        clear_mem;
        seen = 128'd0; seen_cnt = 0; addr_q = 7'h7F;
        do_frame(1'b0);

        checks = checks + 1;
        if (seen_cnt != STRIPS*3 + NSINGLE) begin
            $display("      [FAIL] 一帧共读到 %0d 个不同节点，期望 %0d（%0d 音位 + %0d 八度档）",
                     seen_cnt, STRIPS*3 + NSINGLE, STRIPS*3, NSINGLE);
            errors = errors + 1;
        end else begin
            $display("      [6] 一帧共读 %0d 个节点  OK", seen_cnt);
        end
        for (i = 0; i < NSINGLE; i = i + 1) begin
            checks = checks + 1;
            if (!seen[SINGLE_BASE + i]) begin
                $display("      [FAIL] 节点 %0d 没被读过 —— 八度档地址算错了", SINGLE_BASE + i);
                errors = errors + 1;
            end
        end
        checks = checks + 1;
        if (seen[SINGLE_BASE + NSINGLE] || seen[SINGLE_BASE - 1]) begin
            $display("      [FAIL] 读到了 75..79 之外的节点（%0d 或 %0d）—— 地址越界",
                     SINGLE_BASE - 1, SINGLE_BASE + NSINGLE);
            errors = errors + 1;
        end else
            $display("      [6] 读到的节点恰好是 75..79 各一次  OK");

        $display("");
        $display("================================================================");
        if (errors == 0) $display(" PASS —— %0d 项检查全部通过", checks);
        else             $display(" FAIL —— %0d / %0d 项检查失败", errors, checks);
        $display("================================================================");
        $display("");
        $finish;
    end

    initial begin
        #(2_000_000);
        $display("[TIMEOUT] 仿真超时退出");
        $finish;
    end

endmodule
