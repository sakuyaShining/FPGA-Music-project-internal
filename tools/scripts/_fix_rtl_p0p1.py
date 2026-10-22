# -*- coding: utf-8 -*-
"""doc22 工单：RTL 五处修复（P0-1 + P1-1/2/3/4），P1-5 经核实为误报。

每条都用**精确子串替换**，改完打印命中情况；
若某条未命中（代码已被人改过），脚本会明确报告而不是静默跳过。
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

EDITS = [
    # ---------------- P0-1：湿声发送电平符号 ----------------
    # din[23:9] 是无符号位选，负半波被整流成正数，直流灌进延迟线后被反馈环放大到削顶。
    ("src/rtl/fx_delay.v",
     "wire signed [24:0]   wr_sum = $signed({1'b0, din[23:9]}) + fb_val",
     "wire signed [24:0]   wr_sum = ($signed(din) >>> 9) + fb_val"),

    # ---------------- P1-2：湿声求和先饱和再截位 ----------------
    ("src/rtl/fx_delay.v",
     "RE:    wire signed \\[23:0\\] wet_sum = \\(dly_en \\? \\{\\{8\\{dl_tap\\[DW-1\\]\\}\\}, dl_tap\\} : 24'sd0\\)"
     "\\s*\\n\\s*\\+ \\(cho_en \\? \\{\\{8\\{ch_tap\\[DW-1\\]\\}\\}, ch_tap\\} : 24'sd0\\)"
     "\\s*\\n\\s*\\+ \\{\\{1\\{rev_wet\\[22\\]\\}\\}, rev_wet\\};",
     """    // 三路湿声各可达 +/-8388607，和可达 +/-2.5e7；若直接截成 24 位会回绕成
    // 极性相反的爆音，而后级 mix_sum 的饱和救不了"已经回绕"的值。先加宽求和再饱和。
    wire signed [25:0] wet_raw = (dly_en ? {{10{dl_tap[DW-1]}}, dl_tap} : 26'sd0)
                               + (cho_en ? {{10{ch_tap[DW-1]}}, ch_tap} : 26'sd0)
                               + {{3{rev_wet[22]}}, rev_wet};
    wire signed [23:0] wet_sum = (wet_raw >  26'sd8388607) ?  24'sd8388607 :
                                 (wet_raw < -26'sd8388608) ? -24'sd8388608 :
                                                              wet_raw[23:0];"""),

    # ---------------- P1-3：阈值比较用全宽 ----------------
    # hi/lo 是 CW+3 位（15 位），原来比较时切成 12 位：base>3543 时阈值回绕成小数，
    # 复位初值 base=4095 正好落在这个区间 ⇒ 上电幽灵触摸。
    ("src/rtl/pad_scan.v",
     "if (cnt[i] > hi[CW-1:0]) begin",
     "if (cnt[i] > hi) begin                      // 全宽比较：阈值 15 位，切 12 位会在 base>3543 时回绕"),
    ("src/rtl/pad_scan.v",
     "if (cnt[i] < lo[CW-1:0]) begin",
     "if (cnt[i] < lo) begin                      // 同上"),

    # ---------------- P1-4：写地址按 NW 取模 ----------------
    # NW=128 而接口地址 8 位：合成后 bit7 被丢弃，0x80-0xFF 别名写入 0x00-0x7F；
    # 仿真里越界写被忽略 ⇒ 板上与仿真分叉。显式按 NW 掩码，两边一致。
    ("src/rtl/reg_bank.v",
     """    always @(posedge clk) begin
        if (wr_en)
            mem[wr_addr] <= wr_data;
    end""",
     """    always @(posedge clk) begin
        if (wr_en)
            // 地址按 NW 取模（NW 为 2 的幂）。合成后高位本来会被丢弃，显式写出来
            // 是为了让仿真与板上行为一致：0x80-0xFF 别名到 0x00-0x7F，而不是被忽略。
            mem[wr_addr & (NW-1)] <= wr_data;
    end"""),

    # ---------------- P1-1：事件仲裁改用事件脉冲 ----------------
    # 原来用 seq_en 电平选通：定序器一使能就永久压住 pads 与排针事件，16 个触摸键整体变哑。
    ("src/rtl/tdm_top.v",
     """    wire        ev_valid_i = u_ev_valid ? 1'b1      :
                             seq_en      ? sq_ev_valid :
                             pd_ev_valid ? 1'b1      : ev_valid;
    wire        ev_on_i    = u_ev_valid ? u_ev_on   :
                             seq_en      ? sq_ev_on    :
                             pd_ev_valid ? pd_ev_on    : ev_on;
    wire [6:0]  ev_note_i  = u_ev_valid ? u_ev_note :
                             seq_en      ? sq_ev_note  :
                             pd_ev_valid ? pd_ev_note  : ev_note;
    wire [3:0]  ev_vel_i   = u_ev_valid ? u_ev_vel  :
                             seq_en      ? sq_ev_vel[7:4] :
                             pd_ev_valid ? 4'd12       : ev_vel;   // pad 力度 v1 固定 12/15""",
     """    // 仲裁选通：定序器只在【正在发事件的这一拍】抢占总线。
    // 原来用 seq_en（电平）选通 —— 定序器一使能就长期压住 pads 与排针事件，
    // 16 个触摸键会整体变哑，与本文件"三者互为兜底"的说明矛盾。
    wire        seq_ev_sel = seq_en & sq_ev_valid;
    wire        ev_valid_i = u_ev_valid ? 1'b1       :
                             seq_ev_sel  ? 1'b1       :
                             pd_ev_valid ? 1'b1       : ev_valid;
    wire        ev_on_i    = u_ev_valid ? u_ev_on    :
                             seq_ev_sel  ? sq_ev_on   :
                             pd_ev_valid ? pd_ev_on   : ev_on;
    wire [6:0]  ev_note_i  = u_ev_valid ? u_ev_note  :
                             seq_ev_sel  ? sq_ev_note :
                             pd_ev_valid ? pd_ev_note : ev_note;
    wire [3:0]  ev_vel_i   = u_ev_valid ? u_ev_vel   :
                             seq_ev_sel  ? sq_ev_vel[7:4] :
                             pd_ev_valid ? 4'd12      : ev_vel;   // pad 力度 v1 固定 12/15"""),

    # ---------------- P1-5：澄清（不是缺陷） ----------------
    ("src/rtl/note_map.v",
     "    wire [PHASE_W+16-1:0] inc_mul = note_rom[g_note_r] * ratio_q8;",
     "    // 位宽说明：note_rom 24 位 x ratio_q8 16 位 = 40 位，声明 [PHASE_W+16-1:0]\n"
     "    //   即 [39:0]，宽度本来就是够的（不要把它误读成 39 位而再去加宽）。\n"
     "    wire [PHASE_W+16-1:0] inc_mul = note_rom[g_note_r] * ratio_q8;"),
]


def main():
    import re
    apply = "--apply" in sys.argv
    ok = miss = 0
    for f, old, new in EDITS:
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            print("  [缺文件] %s" % f)
            miss += 1
            continue
        s = io.open(p, encoding="utf-8", errors="replace").read()
        # "RE:" 前缀 = 用正则匹配（容忍对齐空白差异），其余走精确子串
        if old.startswith("RE:"):
            pat = re.compile(old[3:])
            n = len(pat.findall(s))
            hit = lambda: pat.sub(lambda m: new, s, count=1)  # noqa: E731
        else:
            n = s.count(old)
            hit = lambda: s.replace(old, new)                  # noqa: E731
        if n == 0:
            print("  [未命中] %s  旧文「%s」" % (f, old[3:].strip().splitlines()[0][:60]))
            miss += 1
            continue
        if n > 1:
            print("  [多处命中 %d，跳过] %s" % (n, f))
            miss += 1
            continue
        ok += 1
        print("  [%s] %s" % ("已改" if apply else "将改", f))
        if apply:
            io.open(p, "w", encoding="utf-8", newline="").write(hit())
    print("-" * 70)
    print("  命中 %d 处，未命中 %d 处" % (ok, miss))
    if not apply:
        print("  （预演，未写文件；加 --apply 执行）")
    return 0 if miss == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
