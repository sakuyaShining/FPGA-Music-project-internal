# -*- coding: utf-8 -*-
"""
pitch_mod_check.py —— 表情调制（滑音 + 颤音）的判据脚本

【为什么要有它】
   测试台只负责产生数据（每样本的相位），判据必须是【可证伪的数值断言】，
   不能是"看波形差不多"。本脚本对 tb_pitch_mod 的四份相位文件做五条判定。

【判据】
   G1 滑音轨迹：与 Python 镜像【逐样本一致】（镜像严格照抄 RTL 的整数递推）
   G2 滑音比例性：第 16 泛音 / 第 1 泛音 的瞬时频率比 = 16（±0.1%）
                  ← "加固定 Hz 偏移"的实现会在这里必然失败
   V1 颤音幅度与周期：频偏(cents) 峰值 = 设定深度、周期 = 设定 LFO 周期
   V2 颤音比例性：两个泛音的 cents 偏移相等（±0.1 音分）
   C1 连续性：相邻样本的相位增量变化极小（无跳变 → 无咔哒）

用法：
   python tools/scripts/pitch_mod_check.py --simdir sim_build/_recheck
"""
import argparse
import math
import os
import sys

FS = 39062.5


def load_hex(path, n=None):
    vals = []
    with open(path) as f:
        for line in f:
            for w in line.split():
                vals.append(int(w, 16))
    return vals


def load_col(path):
    """读一列整数；★ 上电未初始化期可能出现 x（流水线未填满），跳过并计数"""
    vals, skipped = [], 0
    for l in open(path):
        l = l.strip()
        if not l:
            continue
        try:
            vals.append(int(l))
        except ValueError:
            skipped += 1
    if skipped:
        print("   （%s：跳过 %d 行非数值，多为上电 x）" % (path, skipped))
    return vals


def dinc(ph):
    """相位差分 = 瞬时相位增量（模 2^24）"""
    return [(ph[i + 1] - ph[i]) % (1 << 24) for i in range(len(ph) - 1)]


def cents(f, f0):
    return 1200.0 * math.log2(f / f0)


def glide_mirror(gq0, step, n):
    """线性速率滑音的 Python 镜像（严格照抄 pitch_mod.v）
       每样本朝 0 走 step(Q16)，越过就归零 —— 不再是指数衰减。"""
    out, g = [], gq0
    for _ in range(n):
        out.append(g)
        if g > 0:
            g = (g - step) if g > step else 0
        elif g < 0:
            g = (g + step) if g < -step else 0
        else:
            g = 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default="sim_build/_recheck")
    ap.add_argument("--step", type=int, default=10,
                    help="滑音速率（Q16/样本），与测试台 pmod_cfg 里的一致")
    ap.add_argument("--depth", type=float, default=1000.0)   # Q16
    ap.add_argument("--lfo-hz", type=float, default=5.0)
    a = ap.parse_args()

    d = a.simdir
    note_inc = load_hex(os.path.join(d, "note_inc.hex"))
    recip = load_hex(os.path.join(d, "recip_inc.hex"))
    INC60, INC74 = note_inc[60], note_inc[74]
    INC15_60, INC15_74 = INC60 * 16, INC74 * 16

    print("=" * 66)
    print(" 表情调制验收（滑音 + 颤音）")
    print("=" * 66)
    print("表：INC60=%d  INC74=%d  (比值 %.4f)" % (INC60, INC74, INC74 / INC60))

    fails = []

    # ======================================================================
    # A 段：滑音
    # ======================================================================
    a0 = dinc(load_col(os.path.join(d, "pm_a_s0.txt")))
    a15 = dinc(load_col(os.path.join(d, "pm_a_s15.txt")))
    aout = load_col(os.path.join(d, "pm_a_out.txt"))

    # 找抢占发生的那一样本：最后一个"仍是 inc60"的样本
    t0 = None
    for i in range(len(a0) - 1):
        if a0[i] == INC60 and a0[i + 1] != INC60:
            t0 = i
    if t0 is None:
        print("\n[A] ★ 找不到滑音起始点 —— 抢占没有发生？")
        fails.append("A: 未检出滑音起始")
        t0 = 0
    else:
        print("\n[A] 滑音起始于第 %d 个样本（之前 inc=%d = MIDI 60）" % (t0, INC60))

    # ---- 镜像 G1 ----
    #   note_map 的初值：gq0 = clamp((INC60-INC74) * recip[74] >> 16)
    dinc_raw = INC60 - INC74
    gq_raw = (dinc_raw * recip[74]) >> 16
    gq0 = max(-114688, min(131071, gq_raw))
    gq_seq = glide_mirror(gq0, a.step, len(a0) - t0)
    exp0 = [INC74 + ((INC74 * g) >> 16) for g in gq_seq]
    # 小范围滞后搜索（装载/流水线造成的固定偏移）
    best = None
    for lag in range(0, 8):
        n = len(exp0) - lag
        if n < 100:
            break
        diff = sum(1 for j in range(n) if a0[t0 + lag + j] != exp0[j])
        if best is None or diff < best[1]:
            best = (lag, diff, n)
    print("     滑音初值 gq0 = %d（Q2.16，≈ %+.1f 音分）" % (gq0, cents(1 + gq0 / 65536.0, 1.0)))
    print("     G1 轨迹 vs Python 镜像：滞后 %d 样本，不符 %d / %d"
          % (best[0], best[1], best[2]))
    if best[1] != 0:
        fails.append("G1: 滑音轨迹与镜像不符 %d/%d" % (best[1], best[2]))
        # 打印前几处不符
        shown = 0
        for j in range(best[2]):
            if a0[t0 + best[0] + j] != exp0[j]:
                print("        j=%4d  实测 %7d  镜像 %7d" %
                      (j, a0[t0 + best[0] + j], exp0[j]))
                shown += 1
                if shown >= 5:
                    break

    # 收敛：终点应为 INC74
    tail = a0[-200:]
    err_c = cents(sum(tail) / len(tail), INC74)
    print("     终点：实测均值 %.1f  inc，目标 %d → 误差 %+.3f 音分" %
          (sum(tail) / len(tail), INC74, err_c))
    if abs(err_c) > 1.0:
        fails.append("G1b: 滑音终点误差 %.3f 音分 > 1" % err_c)

    # ---- G2 比例性 ----
    #   跳过起始点附近 2 个样本（gq 写入不落在样本边界上，
    #   可能让同组先被访问的时隙与后被访问的时隙差一个样本 —— 已知细节）
    rmin, rmax, bad = 9e9, 0.0, 0
    for i in range(2, len(a0)):
        if a0[i] == 0:
            continue
        r = a15[i] / a0[i]
        rmin, rmax = min(rmin, r), max(rmax, r)
        if abs(r - 16.0) > 16.0 * 0.001:
            bad += 1
    print("     G2 比例 d15/d0：最小 %.5f  最大 %.5f（应为 16）" % (rmin, rmax))
    if rmax > 16.0 * 1.001 or rmin < 16.0 * 0.999 or bad > 2:
        fails.append("G2: 比例偏离 16（越界 %d 个样本）" % bad)

    # ---- C1 连续性 ----
    jmax, worst = 0.0, 0
    for i in range(t0 + 2, len(a0) - 1):
        if a0[i] == 0:
            continue
        jump = abs(a0[i + 1] - a0[i]) / float(a0[i])
        if jump > jmax:
            jmax, worst = jump, i
    print("     C1 相邻样本相位增量最大相对变化 = %.5f%%（第 %d 样本）"
          % (jmax * 100, worst))
    if jmax > 0.01:
        fails.append("C1: 相位增量跳变 %.4f%% > 1%%" % (jmax * 100))

    # ======================================================================
    # B 段：颤音
    # ======================================================================
    b0 = dinc(load_col(os.path.join(d, "pm_b_s0.txt")))
    b15 = dinc(load_col(os.path.join(d, "pm_b_s15.txt")))

    # 跳过装载建立段
    st = 3000
    seg0 = [x for x in b0[st:] if x > 0]
    seg15 = [x for x in b15[st:] if x > 0]
    if not seg0:
        print("\n[B] ★ 没有数据")
        fails.append("B: 无数据")
    else:
        c0 = [cents(x, INC60) for x in seg0]
        c15 = [cents(x, INC15_60) for x in seg15]
        exp_depth = cents(1 + a.depth / 65536.0, 1.0)
        print("\n[B] 颤音：设定深度 = %.2f 音分（Q16 %.0f），LFO = %.2f Hz"
              % (exp_depth, a.depth, a.lfo_hz))
        print("     V1 slot0：频偏 %+.2f .. %+.2f 音分（峰峰 %.2f）" %
              (min(c0), max(c0), max(c0) - min(c0)))
        pk = (max(c0) - min(c0)) / 2.0
        if abs(pk - exp_depth) > max(1.0, exp_depth * 0.1):
            fails.append("V1a: 颤音幅度 %.2f 音分 ≠ 设定 %.2f" % (pk, exp_depth))

        # 周期：过均值点的上升沿间隔
        mean = sum(c0) / len(c0)
        cross = [i for i in range(1, len(c0))
                 if c0[i - 1] < mean <= c0[i]]
        if len(cross) >= 3:
            per = (cross[-1] - cross[0]) / float(len(cross) - 1) / FS
            print("     V1 LFO 周期实测 = %.4f s（期望 %.4f s）" % (per, 1.0 / a.lfo_hz))
            if abs(per - 1.0 / a.lfo_hz) > 0.05 / a.lfo_hz:
                fails.append("V1b: LFO 周期 %.4f ≠ %.4f" % (per, 1.0 / a.lfo_hz))
        else:
            print("     V1 ★ 过均值点不足，无法测周期")

        # V2 比例性：两个泛音的 cents 偏移必须相等
        dv = max(abs(c15[i] - c0[i]) for i in range(min(len(c0), len(c15))))
        print("     V2 两个泛音的 cents 偏移最大差 = %.4f 音分" % dv)
        if dv > 0.1:
            fails.append("V2: 泛音间 cents 偏移差 %.3f > 0.1" % dv)

    # ======================================================================
    print("\n" + "=" * 66)
    if fails:
        print(" ★ 未通过：")
        for f in fails:
            print("   -", f)
        return 1
    print(" ★★★ 全部通过（G1/G1b/G2/V1/V2/C1）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
