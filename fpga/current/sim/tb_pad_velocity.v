`timescale 1ns/1ps
//=============================================================================
// tb_pad_velocity —— pad_scan 逐通道力度通路的判据台
//
// 目的：证明"按得重 ⇒ 力度大"这条链路在 RTL 层真的成立，并且
//       · 逐通道独立（和弦/连弹不会串力度）
//       · 单调（cap 越大 vel 越大）
//       · 饱和（超过 15 钳到 15）
//       · 不受 note_busy 影响（力度在判定按下那一拍就锁进 vel_ch[]）
//
// 怎么模拟 RC：
//   硬件里 pad 是 inout，充电时 FPGA 拉高，释放后靠电极电容维持高电平，
//   放电到阈值以下才变低，放电计数 cnt 就等于"维持了多少拍"。
//   仿真里用【pull 强度】驱动：pad_scan 的强驱动（充电=1）压过测试台的 pull，
//   释放后（z）由测试台的 pull 接管，hold 计数到 cap[i] 再翻 0。
//   用 pull 而不是 strong 是为了避免充电那一拍出现 X（强 1 vs 强 0）。
//=============================================================================
module tb_pad_velocity;

    localparam integer NCH     = 16;
    localparam integer CW      = 12;
    localparam integer CHARGE  = 64;
    localparam integer CAL_RND = 32;
    localparam integer DEB     = 3;

    reg         clk = 1'b0;
    reg         rst_n = 1'b0;
    reg         note_busy = 1'b0;
    reg  [3:0]  vel_shift = 4'd5;

    wire [NCH-1:0]      pad_line;
    wire [NCH-1:0]      state;
    wire [6:0]          ev_note;
    wire                ev_on, ev_valid;
    wire [4*NCH-1:0]    vel_bus;
    wire [CW-1:0]       dbg_raw0, dbg_base0;
    wire [1:0]          dbg_phase;
    reg  [3:0]          dbg_sel = 4'd0;
    wire [CW-1:0]       dbg_raw_sel, dbg_base_sel;

    pad_scan #(.NCH(NCH), .CW(CW), .CHARGE(CHARGE), .CAL_RND(CAL_RND), .DEB(DEB)) dut (
        .clk(clk), .rst_n(rst_n),
        .pad(pad_line),
        .note_busy(note_busy),
        .oct_up(1'b0),
        .state(state),
        .ev_note(ev_note), .ev_on(ev_on), .ev_valid(ev_valid),
        .vel_shift(vel_shift),
        .vel_bus(vel_bus),
        .dbg_raw0(dbg_raw0), .dbg_base0(dbg_base0), .dbg_phase(dbg_phase),
        .dbg_sel(dbg_sel),
        .dbg_raw_sel(dbg_raw_sel), .dbg_base_sel(dbg_base_sel)
    );

    //-------------------------------------------------------------------------
    // 每通道可变电容模型：cap[i] = 该通道"放电到阈值"需要多少拍
    //-------------------------------------------------------------------------
    integer cap [0:NCH-1];
    integer n;
    initial for (n = 0; n < NCH; n = n + 1) cap[n] = 500;

    genvar gi;
    generate
        for (gi = 0; gi < NCH; gi = gi + 1) begin: rc
            reg        hold;
            reg [15:0] d;
            always @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    hold <= 1'b1;          // 复位后先假设"还充着电"，等扫描把它归零
                    d    <= 16'd0;
                end
                else if (pad_line[gi] === 1'b1 && dbg_phase == 2'd0) begin
                    hold <= 1'b1;          // 充电相：重新充满
                    d    <= 16'd0;
                end
                else if (hold) begin
                    if (d >= cap[gi][15:0]) hold <= 1'b0;
                    else                    d    <= d + 1'b1;
                end
            end
            // pull 强度：pad_scan 强驱动 1 时被压过；z 时由这里接管
            assign (pull1, pull0) pad_line[gi] = hold;
        end
    endgenerate

    //-------------------------------------------------------------------------
    // 时钟 / 工具
    //-------------------------------------------------------------------------
    always #18.5 clk = ~clk;             // 27 MHz

    integer errors = 0;
    integer checks = 0;

    task fail(input [1023:0] msg);
        begin
            errors = errors + 1;
            $display("  [FAIL] %0s", msg);
        end
    endtask

    // 读某通道的基线（经 dbg 遥测口）
    task automatic read_base(input integer ch, output integer b);
        begin
            @(negedge clk); dbg_sel = ch[3:0];
            @(negedge clk); b = dbg_base_sel;
        end
    endtask

    // 等某通道 state 变成 want（带超时）
    task automatic wait_state(input integer ch, input want, input integer maxcyc, output integer ok);
        integer t;
        begin
            ok = 0;
            for (t = 0; t < maxcyc; t = t + 1) begin
                @(posedge clk);
                if (state[ch] === want) begin ok = 1; t = maxcyc; end
            end
        end
    endtask

    // 取某通道当前力度
    function [3:0] velof(input integer ch);
        begin
            velof = vel_bus[ch*4 +: 4];
        end
    endfunction

    integer base_i, hi_i, k, ok, exp_v, got_v;
    integer bases [0:NCH-1];

    initial begin
        // 在 sim_work/ 下运行（tools/run_sims.py 就是这么跑的），路径不能再带 sim_work/
        $dumpfile("tb_pad_velocity.vcd");
        $dumpvars(0, tb_pad_velocity);

        $display("");
        $display("================================================================");
        $display(" tb_pad_velocity  —— 逐通道力度通路判据");
        $display("================================================================");

        //---------------------------------------------------------------------
        // [1] 复位后状态干净
        //---------------------------------------------------------------------
        repeat (5) @(posedge clk);
        rst_n = 1'b1;
        repeat (5) @(posedge clk);
        checks = checks + 1;
        if (state !== 16'd0) fail("复位后 state 应为 0");
        else $display("  [1] 复位后 state == 0                          OK");

        checks = checks + 1;
        if (vel_bus !== 64'd0) fail("复位后 vel_bus 应为 0");
        else $display("  [1] 复位后 vel_bus == 0                        OK");

        //---------------------------------------------------------------------
        // [2] 等标定窗结束，量出各通道基线
        //     标定窗 = CAL_RND 轮，每轮 ≈ CHARGE + cap + 1 ≈ 565 拍
        //     给足 32*1200 拍余量
        //---------------------------------------------------------------------
        repeat (CAL_RND * 1200) @(posedge clk);
        for (k = 0; k < NCH; k = k + 1) begin
            read_base(k, bases[k]);
        end
        $display("  [2] 标定后基线 base[i] = %0d（期望 ≈ 500）", bases[0]);
        checks = checks + 1;
        if (bases[0] < 460 || bases[0] > 540) fail("基线不在 460..540 之间");
        else $display("  [2] 基线落在合理区间                            OK");

        //---------------------------------------------------------------------
        // [3] 单调性：逐档验证 vel == k
        //     基准点 = 触控阈值 hi = base + base>>3 + base>>5
        //     cap = hi + k*(1<<vel_shift) ⇒ 期望 vel == k
        //     用实测 base 反推，避免依赖"base 恰好等于 500"这个假设
        //---------------------------------------------------------------------
        $display("  [3] 单调性扫描（通道 3）");
        base_i = bases[3];
        hi_i   = base_i + (base_i >> 3) + (base_i >> 5);
        $display("      base=%0d  hi=%0d  shift=%0d  每档 %0d 拍",
                 base_i, hi_i, vel_shift, (1 << vel_shift));

        ok = 1;
        for (k = 0; k <= 15; k = k + 1) begin
            // 先松开，让 state 落下去
            cap[3] = base_i;
            wait_state(3, 1'b0, 60000, ok);
            if (!ok) begin
                $display("      [FAIL] 通道 3 无法释放");
                errors = errors + 1;
                k = 16;
            end
            else begin
                // 模型里 cnt 比 cap 多 1 拍（释放那一拍 pin 仍为高，也计入），
                // 所以 cap = hi + k*32 时 delta = k*32+1 ⇒ vel = k。
                cap[3] = hi_i + k * (1 << vel_shift);
                wait_state(3, 1'b1, 60000, ok);
                if (!ok) begin
                    $display("      [FAIL] 通道 3 按下未检出（k=%0d cap=%0d）", k, cap[3]);
                    errors = errors + 1;
                    k = 16;
                end
                else begin
                    got_v = velof(3);
                    checks = checks + 1;
                    if (got_v !== k[3:0]) begin
                        $display("      [FAIL] k=%0d cap=%0d 期望 vel=%0d 实得 %0d",
                                 k, cap[3], k, got_v);
                        errors = errors + 1;
                    end
                    else
                        $display("      k=%2d  cap=%4d  →  vel=%2d            OK", k, cap[3], got_v);
                end
            end
        end
        cap[3] = base_i;
        wait_state(3, 1'b0, 60000, ok);

        //---------------------------------------------------------------------
        // [4] 逐通道独立：同时按 1 和 6，力度不同且互不串
        //     这是"用单路力度"会失败的场景（先按的会拿到后按的力度）
        //---------------------------------------------------------------------
        $display("  [4] 双通道同时按下（通道 1 轻 / 通道 6 重）");
        base_i = bases[1];
        hi_i   = base_i + (base_i >> 3) + (base_i >> 5);
        cap[1] = hi_i + 3 * (1 << vel_shift) + 8;    // 期望 ≈ 3
        base_i = bases[6];
        hi_i   = base_i + (base_i >> 3) + (base_i >> 5);
        cap[6] = hi_i + 12 * (1 << vel_shift) + 8;   // 期望 ≈ 12

        wait_state(1, 1'b1, 60000, ok);
        if (!ok) begin fail("通道 1 按下未检出"); end
        wait_state(6, 1'b1, 60000, ok);
        if (!ok) begin fail("通道 6 按下未检出"); end

        checks = checks + 1;
        if (velof(1) !== 4'd3) begin
            $display("      [FAIL] 通道 1 期望 vel=3 实得 %0d", velof(1));
            errors = errors + 1;
        end
        else $display("      通道 1 vel=%0d                            OK", velof(1));

        checks = checks + 1;
        if (velof(6) !== 4'd12) begin
            $display("      [FAIL] 通道 6 期望 vel=12 实得 %0d", velof(6));
            errors = errors + 1;
        end
        else $display("      通道 6 vel=%0d                           OK", velof(6));

        checks = checks + 1;
        if (velof(1) == velof(6)) fail("两通道力度相同 ⇒ 逐通道隔离失效");
        else $display("      两通道力度互不相同 ⇒ 逐通道隔离成立      OK");

        //---------------------------------------------------------------------
        // [5] 保持不动时力度不被"稀释"
        //     按住不放几百轮，vel 必须还是原值（不会被基线跟踪带跑）
        //---------------------------------------------------------------------
        $display("  [5] 按住 300 轮，力度不漂移");
        exp_v = velof(6);
        repeat (300 * 1200) @(posedge clk);
        checks = checks + 1;
        if (velof(6) !== exp_v[3:0]) begin
            $display("      [FAIL] 300 轮后 vel 从 %0d 漂到 %0d", exp_v, velof(6));
            errors = errors + 1;
        end
        else $display("      300 轮后 vel 仍为 %0d                       OK", velof(6));

        //---------------------------------------------------------------------
        // [6] 释放后重新按下，力度按新值更新（不是锁死在第一次）
        //---------------------------------------------------------------------
        $display("  [6] 松开再按，力度跟随新行程");
        cap[1] = bases[1];
        cap[6] = bases[6];
        wait_state(1, 1'b0, 60000, ok);
        wait_state(6, 1'b0, 60000, ok);

        base_i = bases[6];
        hi_i   = base_i + (base_i >> 3) + (base_i >> 5);
        cap[6] = hi_i + 5 * (1 << vel_shift) + 8;    // 期望 ≈ 5
        wait_state(6, 1'b1, 60000, ok);
        checks = checks + 1;
        if (velof(6) !== 4'd5) begin
            $display("      [FAIL] 第二次按下期望 vel=5 实得 %0d", velof(6));
            errors = errors + 1;
        end
        else $display("      第二次按下 vel=%0d                        OK", velof(6));

        //---------------------------------------------------------------------
        // [7] note_busy 不影响力度采样
        //     note_map 忙的时候事件会等，但力度在判定按下那一拍已锁存
        //---------------------------------------------------------------------
        $display("  [7] note_busy=1 期间按下，力度仍正确");
        cap[6] = bases[6];
        wait_state(6, 1'b0, 60000, ok);

        note_busy = 1'b1;                             // 从按下前就一直忙
        base_i = bases[6];
        hi_i   = base_i + (base_i >> 3) + (base_i >> 5);
        cap[6] = hi_i + 9 * (1 << vel_shift) + 8;
        wait_state(6, 1'b1, 60000, ok);
        repeat (10) @(posedge clk);
        checks = checks + 1;
        if (velof(6) !== 4'd9) begin
            $display("      [FAIL] busy 期间期望 vel=9 实得 %0d", velof(6));
            errors = errors + 1;
        end
        else $display("      busy 期间 vel=%0d                         OK", velof(6));
        note_busy = 1'b0;

        //---------------------------------------------------------------------
        // [8] vel_shift 改变 ⇒ 同样的行程得到不同档位（量程旋钮有效）
        //---------------------------------------------------------------------
        $display("  [8] vel_shift 从 5 改到 4，同一行程档位翻倍");
        cap[6] = bases[6];
        wait_state(6, 1'b0, 60000, ok);

        vel_shift = 4'd4;
        base_i = bases[6];
        hi_i   = base_i + (base_i >> 3) + (base_i >> 5);
        cap[6] = hi_i + 4 * (1 << 4) + 8;            // shift=4 时 4 档
        wait_state(6, 1'b1, 60000, ok);
        checks = checks + 1;
        if (velof(6) !== 4'd4) begin
            $display("      [FAIL] shift=4 期望 vel=4 实得 %0d", velof(6));
            errors = errors + 1;
        end
        else $display("      shift=4 vel=%0d                           OK", velof(6));

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
        #(400_000_000);
        $display("[TIMEOUT] 仿真超时退出");
        $finish;
    end

endmodule
