`timescale 1ns/1ps
//=============================================================================
// tb_pad_chain —— 端到端：触摸行程 → 力度 → 音符事件里的 ev_vel
//
// 为什么必须做这一台：
//   pad_scan 的力度对了、pad_pitch 的取力度也对了，不代表【接起来】是对的。
//   pad_pitch 是轮流扫查的（38 通道走一圈），它扫到某通道的那一拍，
//   与"该通道刚按下"不是同一拍。中间隔了几十拍，任何一处采样时点错位
//   都会让音符带上【别的通道】的力度 —— 仿真单模块永远看不出来。
//
// 判据：
//   [1] 单音：通道 3 行程 → vel 7 ⇒ note-on 的 ev_vel == 7
//   [2] 双音同时：通道 1 轻(3) / 通道 6 重(12) ⇒ 两个 note-on 各自带对的力度
//   [3] 先按住 A 再按 B（相位不同）：A 的 ev_vel 仍是 A 自己的
//   [4] note-off 不受力度影响（仍是原来的音符号）
//=============================================================================
module tb_pad_chain;

    localparam integer NCH     = 16;
    localparam integer CW      = 12;
    localparam integer CHARGE  = 64;
    localparam integer CAL_RND = 32;
    localparam integer DEB     = 3;

    reg         clk = 1'b0;
    reg         rst_n = 1'b0;
    reg         note_busy = 1'b0;
    reg  [3:0]  vel_shift = 4'd5;
    reg  [2:0]  pos = 3'd1;              // 相对档位 0 ⇒ 音符号就是 BASE + 通道号

    wire [NCH-1:0]      pad_line;
    wire [NCH-1:0]      state;
    wire [6:0]          pd_note;
    wire                pd_on, pd_valid;
    wire [4*NCH-1:0]    vel_bus;
    // pad_scan 是 NCH=16，只能给通道 0..15；pad_pitch 的 vel_bus 是 NPIT*4=100 位。
    //   高位显式补 0（与 tdm_top_owned 一致），不靠隐式宽度扩展。
    wire [25*4-1:0]     pp_vel_bus = {{(25-NCH)*4{1'b0}}, vel_bus};
    wire [CW-1:0]       dbg_raw0, dbg_base0;
    wire [1:0]          dbg_phase;
    reg  [3:0]          dbg_sel = 4'd0;
    wire [CW-1:0]       dbg_raw_sel, dbg_base_sel;

    pad_scan #(.NCH(NCH), .CW(CW), .CHARGE(CHARGE), .CAL_RND(CAL_RND), .DEB(DEB)) u_scan (
        .clk(clk), .rst_n(rst_n),
        .pad(pad_line),
        .note_busy(note_busy),
        .oct_up(1'b0),
        .state(state),
        .ev_note(pd_note), .ev_on(pd_on), .ev_valid(pd_valid),
        .vel_shift(vel_shift),
        .vel_bus(vel_bus),
        .dbg_raw0(dbg_raw0), .dbg_base0(dbg_base0), .dbg_phase(dbg_phase),
        .dbg_sel(dbg_sel),
        .dbg_raw_sel(dbg_raw_sel), .dbg_base_sel(dbg_base_sel)
    );

    wire [7:0]  pp_harm;
    wire [6:0]  pp_note;
    wire [3:0]  pp_vel;
    wire        pp_on, pp_off;

    pad_pitch #(.NCH(38), .NPIT(25), .BASE(48)) u_pitch (
        .clk(clk), .rst_n(rst_n),
        .touch({30'b0, state[7:0]}),
        .pos(pos),
        .vel_bus(pp_vel_bus),
        .ev_on(pp_on), .ev_off(pp_off),
        .ev_note(pp_note), .ev_vel(pp_vel),
        .harm_mask(pp_harm)
    );

    //-------------------------------------------------------------------------
    // 每通道可变电容模型（同 tb_pad_velocity）
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
                    hold <= 1'b1; d <= 16'd0;
                end
                else if (pad_line[gi] === 1'b1 && dbg_phase == 2'd0) begin
                    hold <= 1'b1; d <= 16'd0;
                end
                else if (hold) begin
                    if (d >= cap[gi][15:0]) hold <= 1'b0;
                    else                    d    <= d + 1'b1;
                end
            end
            assign (pull1, pull0) pad_line[gi] = hold;
        end
    endgenerate

    always #18.5 clk = ~clk;

    integer errors = 0;
    integer checks = 0;

    //-------------------------------------------------------------------------
    // 采集 note-on 事件（记录音符 + 力度）
    //-------------------------------------------------------------------------
    reg [6:0] on_note [0:15];
    reg [3:0] on_vel  [0:15];
    integer   on_cnt = 0;
    integer   off_cnt = 0;
    reg [6:0] off_note [0:15];

    always @(posedge clk) begin
        if (rst_n && pp_on && on_cnt < 16) begin
            on_note[on_cnt] = pp_note;
            on_vel[on_cnt]  = pp_vel;
            on_cnt = on_cnt + 1;
        end
        if (rst_n && pp_off && off_cnt < 16) begin
            off_note[off_cnt] = pp_note;
            off_cnt = off_cnt + 1;
        end
    end

    task automatic read_base(input integer ch, output integer b);
        begin
            @(negedge clk); dbg_sel = ch[3:0];
            @(negedge clk); b = dbg_base_sel;
        end
    endtask

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

    // 期望音符号：BASE(48) + 通道号，pos=1 ⇒ rel = 0
    function [6:0] expect_note(input integer ch);
        begin
            expect_note = 7'd48 + ch[6:0];
        end
    endfunction

    integer bases [0:NCH-1];
    integer hi_i, base_i, k, ok, i, found;

    initial begin
        $dumpfile("tb_pad_chain.vcd");
        $dumpvars(0, tb_pad_chain);

        $display("");
        $display("================================================================");
        $display(" tb_pad_chain —— 触摸 → 力度 → 音符事件（端到端）");
        $display("================================================================");

        repeat (5) @(posedge clk);
        rst_n = 1'b1;

        // 等标定
        repeat (CAL_RND * 1200) @(posedge clk);
        for (k = 0; k < NCH; k = k + 1) read_base(k, bases[k]);
        $display("  标定完成，base[0] = %0d", bases[0]);

        //---------------------------------------------------------------------
        // [1] 单音：通道 3，行程对应 vel 7
        //---------------------------------------------------------------------
        on_cnt = 0; off_cnt = 0;
        base_i = bases[3];
        hi_i   = base_i + (base_i >> 3) + (base_i >> 5);
        cap[3] = hi_i + 7 * 32;
        wait_state(3, 1'b1, 60000, ok);
        repeat (200) @(posedge clk);      // 等 pad_pitch 扫到该通道并发事件

        checks = checks + 1;
        if (on_cnt != 1) begin
            $display("  [1] [FAIL] 期望 1 个 note-on，实得 %0d", on_cnt);
            errors = errors + 1;
        end
        else if (on_note[0] !== expect_note(3)) begin
            $display("  [1] [FAIL] 音符号 = %0d，期望 %0d", on_note[0], expect_note(3));
            errors = errors + 1;
        end
        else if (on_vel[0] !== 4'd7) begin
            $display("  [1] [FAIL] ev_vel = %0d，期望 7", on_vel[0]);
            errors = errors + 1;
        end
        else
            $display("  [1] 单音：note=%0d vel=%0d                        OK", on_note[0], on_vel[0]);

        //---------------------------------------------------------------------
        // [2] 松开 → note-off 音符号正确
        //---------------------------------------------------------------------
        cap[3] = base_i;
        wait_state(3, 1'b0, 60000, ok);
        repeat (200) @(posedge clk);

        checks = checks + 1;
        if (off_cnt != 1 || off_note[0] !== expect_note(3)) begin
            $display("  [2] [FAIL] note-off 数=%0d 音符号=%0d，期望 1 个 %0d",
                     off_cnt, off_note[0], expect_note(3));
            errors = errors + 1;
        end
        else $display("  [2] 松开：note-off 音符号 = %0d                   OK", off_note[0]);

        //---------------------------------------------------------------------
        // [3] 双音同时：通道 1 vel 3 / 通道 6 vel 12
        //     这一项是"单路力度"实现必然失败的场景
        //---------------------------------------------------------------------
        on_cnt = 0; off_cnt = 0;
        base_i = bases[1]; hi_i = base_i + (base_i >> 3) + (base_i >> 5);
        cap[1] = hi_i + 3 * 32;
        base_i = bases[6]; hi_i = base_i + (base_i >> 3) + (base_i >> 5);
        cap[6] = hi_i + 12 * 32;

        wait_state(1, 1'b1, 60000, ok);
        wait_state(6, 1'b1, 60000, ok);
        repeat (400) @(posedge clk);

        checks = checks + 1;
        if (on_cnt != 2) begin
            $display("  [3] [FAIL] 期望 2 个 note-on，实得 %0d", on_cnt);
            errors = errors + 1;
        end
        else begin
            // 不假设顺序，按音符号找
            found = 0;
            for (i = 0; i < on_cnt; i = i + 1) begin
                if (on_note[i] === expect_note(1) && on_vel[i] === 4'd3) found = found + 1;
                if (on_note[i] === expect_note(6) && on_vel[i] === 4'd12) found = found + 1;
            end
            if (found != 2) begin
                $display("  [3] [FAIL] 两个 note-on 的力度不对：");
                for (i = 0; i < on_cnt; i = i + 1)
                    $display("        note=%0d vel=%0d", on_note[i], on_vel[i]);
                errors = errors + 1;
            end
            else
                $display("  [3] 双音同时：vel 3 / 12 各自正确（逐通道隔离）  OK");
        end

        cap[1] = bases[1];
        cap[6] = bases[6];
        wait_state(1, 1'b0, 60000, ok);
        wait_state(6, 1'b0, 60000, ok);
        repeat (400) @(posedge clk);

        //---------------------------------------------------------------------
        // [4] 先按住 A（通道 0，vel 2），扫查相位稳定后再按 B（通道 7，vel 14）
        //     A 的 note-on 必须在 B 按下之前就已经发出，
        //     且 A 的力度不能被 B 覆盖
        //---------------------------------------------------------------------
        on_cnt = 0; off_cnt = 0;
        base_i = bases[0]; hi_i = base_i + (base_i >> 3) + (base_i >> 5);
        cap[0] = hi_i + 2 * 32;
        wait_state(0, 1'b1, 60000, ok);
        repeat (300) @(posedge clk);      // 让 A 的事件先发完

        base_i = bases[7]; hi_i = base_i + (base_i >> 3) + (base_i >> 5);
        cap[7] = hi_i + 14 * 32;
        wait_state(7, 1'b1, 60000, ok);
        repeat (400) @(posedge clk);

        checks = checks + 1;
        if (on_cnt != 2) begin
            $display("  [4] [FAIL] 期望 2 个 note-on，实得 %0d", on_cnt);
            errors = errors + 1;
        end
        else if (on_note[0] !== expect_note(0) || on_vel[0] !== 4'd2) begin
            $display("  [4] [FAIL] 先按下的 A：note=%0d vel=%0d，期望 %0d / 2",
                     on_note[0], on_vel[0], expect_note(0));
            errors = errors + 1;
        end
        else if (on_note[1] !== expect_note(7) || on_vel[1] !== 4'd14) begin
            $display("  [4] [FAIL] 后按下的 B：note=%0d vel=%0d，期望 %0d / 14",
                     on_note[1], on_vel[1], expect_note(7));
            errors = errors + 1;
        end
        else
            $display("  [4] 先后按下：A vel=2、B vel=14，互不串          OK");

        $display("");
        $display("================================================================");
        if (errors == 0) $display(" PASS —— %0d 项检查全部通过", checks);
        else             $display(" FAIL —— %0d / %0d 项检查失败", errors, checks);
        $display("================================================================");
        $display("");
        $finish;
    end

    initial begin
        #(400_000_000);
        $display("[TIMEOUT]");
        $finish;
    end

endmodule
