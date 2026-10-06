#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nyquist_check.py —— 完整位宽 Nyquist 判据（阶段 3 遗留项）

【要回答的两个问题】
  N1 **增量位宽是否够**：最高音的相位增量必须是**完整位宽**（PHASE_W=24）下的
     精确值，不能因为位宽不够而被截断（截断 = 音高偏低，最高音区最明显）。
     方法：用 `inc = round(f * 2^PHASE_W / fs)` 独立算出**全部 128 个音**的期望值，
     与 `note_inc.hex` 逐项比对 —— 表是预生成数据，判据必须以**公式**为准（不循环）。
  N2 **第 15 泛音的 Nyquist 余量**：加性合成每声部有 16 个泛音（k=0..15），
     第 k 个泛音的频率是 k*f。最高音（127）的 15 次泛音会远超 fs/2 ⇒
     必须知道**从哪个音开始越界**，并把它作为设计约束显式记录下来。
     （这不是"缺陷"而是加性合成的固有约束，但**必须被量化**，
       否则在最高音区会听到混叠而没人知道原因。）

【为什么放在 Python 而不是 Verilog】
  这是**静态数据判据**（比对预生成表 vs 公式），不需要仿真；
  Python 读表比在 testbench 里重算更直接、失败信息更可读。

用法：python tools/scripts/nyquist_check.py [--verbose]
退出码：0 = N1 通过；1 = N1 失败
"""
import os
import sys
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TBL = os.path.join(ROOT, "src", "gowin", "tdm_synth", "note_inc.hex")

PHASE_W = 24          # 与 tdm_top.v 的 localparam PHASE_W 一致
FS = 52734.375        # 27 MHz / 16 / 32（DIV_BCK=16, 32 拍/帧）
NPART = 16            # 每声部泛音数 P


def midi_freq(n):
    """MIDI 音符号 -> 频率（A4=440Hz，十二平均律）"""
    return 440.0 * (2.0 ** ((n - 69) / 12.0))


def main():
    verbose = "--verbose" in sys.argv
    #   --simdir 是门禁 judge_script 的统一传参；本判据只读预生成表，不需要它，
    #   但必须**接受**，否则门禁调用会因"未知参数"而失败。
    if not os.path.isfile(TBL):
        print("找不到增量表: %s" % TBL)
        return 1

    rows = []
    with open(TBL, "r", encoding="utf-8", errors="replace") as f:
        for ln in f:
            s = re.sub(r"[/ ].*$", "", ln).strip()
            if s:
                rows.append(int(s, 16))

    print("=" * 70)
    print(" 完整位宽 Nyquist 判据   PHASE_W=%d  fs=%.3f Hz  表内 %d 项"
          % (PHASE_W, FS, len(rows)))
    print("=" * 70)

    #------------------------------------------------------------------ N1
    bad = []
    max_inc = 0
    for n, got in enumerate(rows):
        exp = int(round(midi_freq(n) * (1 << PHASE_W) / FS))
        if got > max_inc:
            max_inc = got
        if got != exp:
            bad.append((n, got, exp, got - exp))

    print(" N1 增量 = round(f * 2^%d / fs)，逐音比对 128 项" % PHASE_W)
    if bad:
        print("  FAIL  %d 项不符：" % len(bad))
        for n, got, exp, d in bad[:12]:
            print("     音%-3d 表=%7d 期望=%7d 差=%+d" % (n, got, exp, d))
        if len(bad) > 12:
            print("     …（其余 %d 项省略）" % (len(bad) - 12))
    else:
        print("  PASS  全部 128 项与公式逐项相等")

    #   位宽自检：最大增量必须装得下 PHASE_W 位，且用满了高位
    cap = (1 << PHASE_W) - 1
    print("       最大增量 = %d（%d 位上限 %d，占用 %.1f%%）"
          % (max_inc, PHASE_W, cap, 100.0 * max_inc / cap))
    if max_inc > cap:
        print("  FAIL  最大增量超出 %d 位 ⇒ 最高音会被截断" % PHASE_W)
        bad.append(("width", max_inc, cap, max_inc - cap))
    else:
        bits_used = max_inc.bit_length()
        print("  PASS  最大增量占 %d 位（位宽充足，未截断）" % bits_used)

    #------------------------------------------------------------------ N2
    print()
    print(" N2 第 k 泛音的 Nyquist 约束（每声部 %d 个泛音，k=0..%d）"
          % (NPART, NPART - 1))
    print("      判据：k * f(n) < fs/2 = %.3f Hz" % (FS / 2.0))
    nyq = FS / 2.0
    #   找出每个 k 仍不越界的最高音
    limits = {}
    for k in range(1, NPART):
        last_ok = -1
        for n in range(128):
            if k * midi_freq(n) < nyq:
                last_ok = n
            else:
                break
        limits[k] = last_ok

    print("      k= 1（基音）最高可用音号: 全部 0..127 均可")
    for k in (2, 4, 8, 15):
        lo = limits[k]
        if lo >= 0:
            print("      k=%2d        最高可用音号: %3d (%.1f Hz)，该音 %d 次泛音 %.1f Hz"
                  % (k, lo, midi_freq(lo), k, k * midi_freq(lo)))
        else:
            print("      k=%2d        无可用音号" % k)

    #   关键结论：想让全部 16 个泛音都不越界，音号必须 <= limits[15]
    k_max = NPART - 1
    n_safe = limits[k_max]
    print()
    print("      结论：若要求**全部 16 个泛音都不超过 Nyquist**，")
    print("            音号必须 <= %d (%.1f Hz)。" % (n_safe, midi_freq(n_safe)))
    n127 = 127
    over = [k for k in range(1, NPART) if k * midi_freq(n127) >= nyq]
    print("            而在最高音 127 (%.1f Hz)：越界的泛音号 = %s"
          % (midi_freq(n127), over if over else "无"))
    print("            ⇒ 最高音区第 %d 次及以上泛音必然混叠（加性合成的固有约束，非缺陷）"
          % (min(over) if over else 0))
    print("            缓解手段：预设表对高音区的高次泛音给 0 幅度（这是**数据**层面的选择，")
    print("            不是 RTL 能自动保证的）—— 需在阶段 5 接新音色时按此约束配表。")

    if verbose:
        print()
        print(" 逐音明细（前 8 与后 8）：")
        for n in list(range(8)) + list(range(120, 128)):
            print("   音%-3d f=%8.2f Hz  inc=%7d  %d 次泛音=%9.1f Hz %s"
                  % (n, midi_freq(n), rows[n], k_max, k_max * midi_freq(n),
                     "越界" if k_max * midi_freq(n) >= nyq else ""))

    print("=" * 70)
    if not bad:
        print("RESULT nyquist=PASS")
        return 0
    print("RESULT nyquist=FAIL (%d 项)" % len(bad))
    return 1


if __name__ == "__main__":
    sys.exit(main())
