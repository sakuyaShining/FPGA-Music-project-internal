`timescale 1ns/1ps
//=============================================================================
// tb_pad_velmap —— pad_pitch 的「通道 → 力度」映射判据（缺口 G4）
//
// 为什么必须单独做这一台：
//   64 位的 vel_bus 只装得下 16 路，而音高通道有 NPIT=25 路。
//   旧代码用 `vel_bus[{sc[3:0], 2'b00} +: 4]` 取值，sc=16..24 时 sc[3:0]=0..8，
//   于是 C5（通道 24）读到的是通道 8 的力度 —— 全琴唯一一个"力度串音"的键。
//   tb_pad_chain 抓不到：它只碰通道 1/3/6（都 < 16），别名区根本没被走过。
//
// 判据：
//   [1] 复位后无事件
//   [2] 25 个音高通道逐个：note = 48+ch，vel = vtab[ch]（逐通道唯一值）
//   [3] 25 通道同时按下：25 个 note-on 按扫描顺序 0..24，各自带对的 vel
//   [4] 别名专项：C5（24）单独按，vel 必须是 vtab[24]，且显式断言 != vtab[8]
//   [5] 通道 25..37（音域条 / 泛音键）按下不产生任何事件；harm_mask 仍直通
//
// 力度表为什么这样取：
//     0..8   → 1..9
//     16..24 → 7..15（= vtab[i] + 6，与 0..8 错开 6）
//   这样每一对别名通道 (k, 16+k) 的值都不相等 ⇒ 一旦回绕，判据必然炸。
//   若两边取同值，别名 bug 会被"碰巧相等"掩盖 —— 本项目在 tb_area 的校准帧上
//   栽过一次同类假通过。本台因此额外加 [0] 力度表自检：
//   表里出现 vtab[k] == vtab[16+k] 时测试台自己先报错，不让盲区藏进数据里。
//   （第一版取"反向 9..1"，k=4 两边都等于 5，通道 20 确实漏检了，故改为 +6 平移。）
//=============================================================================
module tb_pad_velmap;

    localparam integer NPIT = 25;
    localparam integer NCH  = 38;
    localparam integer BASE = 48;

    reg clk = 1'b0;
    always #5 clk = ~clk;              // 逻辑与时钟频率无关，100 MHz 够快

    reg rst_n = 1'b0;

    reg  [NCH-1:0]    touch = {NCH{1'b0}};
    reg  [2:0]        pos   = 3'd1;     // pos=1 ⇒ 相对档位 0 ⇒ note = BASE + ch
    wire [NPIT*4-1:0] vel_bus;
    wire              ev_on, ev_off;
    wire [6:0]        ev_note;
    wire [3:0]        ev_vel;
    wire [7:0]        harm_mask;

    //-------------------------------------------------------------------------
    // 逐通道力度表：每通道一个唯一值，且别名对两端不相等
    //-------------------------------------------------------------------------
    reg [3:0] vtab [0:NPIT-1];

    genvar gi;
    generate
        for (gi = 0; gi < NPIT; gi = gi + 1) begin: vb
            assign vel_bus[gi*4 +: 4] = vtab[gi];
        end
    endgenerate

    pad_pitch #(.NCH(NCH), .NPIT(NPIT), .BASE(BASE)) dut (
        .clk(clk), .rst_n(rst_n),
        .touch(touch), .pos(pos), .vel_bus(vel_bus),
        .ev_on(ev_on), .ev_off(ev_off),
        .ev_note(ev_note), .ev_vel(ev_vel),
        .harm_mask(harm_mask)
    );

    //-------------------------------------------------------------------------
    // 判据记账
    //-------------------------------------------------------------------------
    integer checks = 0;
    integer errors = 0;

    task fail(input [1023:0] msg);
        begin
            errors = errors + 1;
            $display("      [FAIL] %0s", msg);
        end
    endtask

    //-------------------------------------------------------------------------
    // 事件队列：posedge 采样，测试序列在 negedge 读（避开 NBA 竞争）
    //-------------------------------------------------------------------------
    integer   mon_n = 0;
    reg [6:0] q_note [0:63];
    reg [3:0] q_vel  [0:63];

    always @(posedge clk) begin
        if (ev_on && mon_n < 64) begin
            q_note[mon_n] = ev_note;
            q_vel[mon_n]  = ev_vel;
            mon_n         = mon_n + 1;
        end
    end

    // 等至少 want 个事件（带超时）
    task wait_events(input integer want, input integer maxcyc, output integer ok);
        integer t;
        begin
            ok = 0;
            for (t = 0; t < maxcyc; t = t + 1) begin
                @(negedge clk);
                if (mon_n >= want) begin ok = 1; t = maxcyc; end
            end
        end
    endtask

    integer   i, k, ch, ok, bad;
    reg [6:0] exp_note;
    reg [3:0] exp_vel;

    initial begin
        // 在 sim_work/ 下运行（tools/run_sims.py 就是这么跑的），路径不能再带 sim_work/
        $dumpfile("tb_pad_velmap.vcd");
        $dumpvars(0, tb_pad_velmap);

        // ---- 力度表 ----
        //   0..8   → 1..9
        //   16..24 → 7..15（= vtab[i] + 6）
        // 必须保证 vtab[16+k] != vtab[k] 对每个 k 都成立。第一版取"反向 9..1"时，
        // k=4 两边都等于 5，通道 20 的别名在反向验证里直接漏检 —— 反向验证本身
        // 也证明了这一点（17 处失败里独缺通道 20）。所以这里改成 +6 平移，
        // 并在下面加一道"力度表自检"，把这个盲区在测试台内部堵死。
        for (i = 0; i < NPIT; i = i + 1) vtab[i] = 4'd0;
        for (i = 0; i < 9;    i = i + 1) vtab[i]      = i + 1;
        for (i = 0; i < 9;    i = i + 1) vtab[16 + i] = vtab[i] + 6;
        vtab[9]  = 4'd10; vtab[10] = 4'd11; vtab[11] = 4'd12;
        vtab[12] = 4'd13; vtab[13] = 4'd14; vtab[14] = 4'd15; vtab[15] = 4'd0;

        $display("");
        $display("================================================================");
        $display(" tb_pad_velmap  —— pad_pitch 通道→力度映射判据（缺口 G4）");
        $display("================================================================");
        $display("  力度表 vtab[0..8]=1..9  vtab[16..24]=7..15（别名对两端必不相等）");
        $display("");

        //---------------------------------------------------------------------
        // [0] 力度表自检：9 对别名通道的值必须两两不等
        //     这一项不是测 DUT，是测【测试台自己】——
        //     表里若出现 vtab[k] == vtab[16+k]，该对通道的别名就永远测不出来。
        //---------------------------------------------------------------------
        bad = 0;
        for (i = 0; i < 9; i = i + 1) begin
            if (vtab[i] === vtab[16 + i]) begin
                $display("      [FAIL] 力度表自检：vtab[%0d] == vtab[%0d] == %0d，该对别名无法检出",
                         i, 16 + i, vtab[i]);
                bad = bad + 1;
            end
        end
        checks = checks + 1;
        if (bad != 0) errors = errors + bad;
        else $display("  [0] 力度表自检：9 对别名通道取值两两不等        OK");

        //---------------------------------------------------------------------
        // [1] 复位后无事件
        //---------------------------------------------------------------------
        rst_n = 1'b0;
        repeat (3) @(negedge clk);
        touch = {NCH{1'b0}};
        mon_n = 0;
        @(negedge clk);
        rst_n = 1'b1;
        repeat (3 * NCH) @(negedge clk);       // 跑满 3 轮扫描
        checks = checks + 1;
        if (mon_n !== 0) fail("复位后 touch 全低，不应产生任何 note-on");
        else $display("  [1] 复位后 3 轮扫描零事件                      OK");

        //---------------------------------------------------------------------
        // [2] 25 个音高通道逐个：note 与 vel 各自正确
        //---------------------------------------------------------------------
        $display("  [2] 逐通道：note=48+ch，vel=vtab[ch]");
        bad = 0;
        for (ch = 0; ch < NPIT; ch = ch + 1) begin
            // 先全松，跑两轮让 seen[ch] 回到 0
            touch = {NCH{1'b0}};
            repeat (2 * NCH + 4) @(negedge clk);
            mon_n = 0;

            touch[ch] = 1'b1;
            wait_events(1, 4 * NCH + 20, ok);

            checks = checks + 1;
            if (!ok) begin
                $display("      [FAIL] 通道 %0d 未产生 note-on", ch);
                errors = errors + 1;
                bad = bad + 1;
            end else begin
                exp_note = BASE + ch;
                exp_vel  = vtab[ch];
                checks = checks + 1;
                if (q_note[0] !== exp_note || q_vel[0] !== exp_vel) begin
                    $display("      [FAIL] 通道 %0d: 期望 note=%0d vel=%0d，实得 note=%0d vel=%0d",
                             ch, exp_note, exp_vel, q_note[0], q_vel[0]);
                    errors = errors + 1;
                    bad = bad + 1;
                end
            end
        end
        if (bad == 0) $display("      ｜0..24 全部 25 路，note 与 vel 均正确        OK");

        //---------------------------------------------------------------------
        // [3] 25 通道同时按下：25 个 note-on 按扫描顺序 0..24
        //---------------------------------------------------------------------
        rst_n = 1'b0;
        repeat (2) @(negedge clk);
        touch = {{(NCH-NPIT){1'b0}}, {NPIT{1'b1}}};   // 0..24 全按
        mon_n = 0;
        @(negedge clk);
        rst_n = 1'b1;                                 // 释放复位时 sc=0，touch 已就位
        wait_events(NPIT, 4 * NCH + 40, ok);

        checks = checks + 1;
        if (!ok || mon_n !== NPIT) begin
            $display("      [FAIL] 和弦：期望 %0d 个 note-on，实得 %0d", NPIT, mon_n);
            errors = errors + 1;
        end else begin
            $display("  [3] 和弦：25 通道同时按下 → %0d 个 note-on", mon_n);
            bad = 0;
            for (k = 0; k < NPIT; k = k + 1) begin
                exp_note = BASE + k;
                exp_vel  = vtab[k];
                checks = checks + 1;
                if (q_note[k] !== exp_note || q_vel[k] !== exp_vel) begin
                    $display("      [FAIL] 第 %0d 个事件（应为通道 %0d）: 期望 note=%0d vel=%0d，实得 note=%0d vel=%0d",
                             k, k, exp_note, exp_vel, q_note[k], q_vel[k]);
                    errors = errors + 1;
                    bad = bad + 1;
                end
            end
            if (bad == 0) $display("      25 个事件按扫描顺序 0..24，各自带对的 vel   OK");
        end

        //---------------------------------------------------------------------
        // [4] 别名专项：C5（通道 24）单独按
        //     这是 G4 的原点 —— 通道 24 的 sc[3:0] 是 8，旧代码会读到 vtab[8]=9
        //---------------------------------------------------------------------
        rst_n = 1'b0;
        repeat (2) @(negedge clk);
        touch = {NCH{1'b0}};
        mon_n = 0;
        touch[24] = 1'b1;
        @(negedge clk);
        rst_n = 1'b1;
        wait_events(1, 4 * NCH + 20, ok);

        checks = checks + 1;
        if (!ok) fail("C5（通道 24）未产生 note-on");
        else begin
            checks = checks + 1;
            if (q_vel[0] !== vtab[24]) begin
                $display("      [FAIL] C5: 期望 vel=%0d（vtab[24]），实得 %0d", vtab[24], q_vel[0]);
                errors = errors + 1;
            end
            else begin
                checks = checks + 1;
                if (q_vel[0] === vtab[8]) begin
                    $display("      [FAIL] C5 拿到了通道 8 的力度（vtab[8]=%0d）—— 别名未修（G4）", vtab[8]);
                    errors = errors + 1;
                end
                else $display("  [4] C5 单独按：vel=%0d（vtab[24]），未串到 vtab[8]=%0d   OK",
                              q_vel[0], vtab[8]);
            end
        end

        //---------------------------------------------------------------------
        // [5] 通道 25..37 不发声；harm_mask 仍直通 touch[37:30]
        //---------------------------------------------------------------------
        rst_n = 1'b0;
        repeat (2) @(negedge clk);
        touch = {NCH{1'b0}};
        for (i = NPIT; i < NCH; i = i + 1) touch[i] = 1'b1;
        mon_n = 0;
        @(negedge clk);
        rst_n = 1'b1;
        repeat (3 * NCH) @(negedge clk);

        checks = checks + 1;
        if (mon_n !== 0) begin
            $display("      [FAIL] 通道 25..37 不应产生 note 事件，实得 %0d 个", mon_n);
            errors = errors + 1;
        end
        else $display("  [5] 通道 25..37 按下：零 note 事件                 OK");

        checks = checks + 1;
        if (harm_mask !== touch[37:30]) begin
            $display("      [FAIL] harm_mask 应为 touch[37:30]=%b，实得 %b",
                     touch[37:30], harm_mask);
            errors = errors + 1;
        end
        else $display("  [5] harm_mask 直通 touch[37:30] = %b          OK", harm_mask);

        //---------------------------------------------------------------------
        $display("");
        $display("================================================================");
        if (errors == 0)
            $display(" PASS —— %0d 项检查全部通过", checks);
        else
            $display(" FAIL —— %0d / %0d 项检查失败", errors, checks);
        $display("================================================================");
        $display("");
        $finish;
    end

    // 全局超时保护
    initial begin
        #(10_000_000);
        $display("[TIMEOUT] 仿真超时退出");
        $finish;
    end

endmodule
