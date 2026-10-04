# -*- coding: utf-8 -*-
"""
pitch_mod512_check.py —— 512 档（出货配置）功能仿真判据

对应测试台：src/sim/tb_pitch_mod512.v（NG=32 / PART=16 / NSLOT=512）

【判据】
   E1a 32 复音：32 个组的基频时隙相位增量【逐个等于】note_inc.hex 的期望值
   E1b FFT 旁证：音频里能检出高音区 16 个基频
                （低音区相邻音间隔 4.9 Hz < FFT 分辨率 11.9 Hz，本来就数不清）
   G1  滑音（16 号组，MIDI 56→72）轨迹 ≡ Python 镜像（逐样本）
   G2  滑音全程 slot271/slot256 的频率比 = 16（±0.1%）
   V1  颤音深度 = 设定值、周期 = 1/50 s
   V2  两个泛音的 cents 偏移相等（±0.1 音分）

★ 这一档专门覆盖"组号位宽"（第 16~31 组）——
  组号曾被截成 4 位，滑音初值会写到错误的组（0~15），
  而这正是只有 8 个组的测试台发现不了的区间。

用法：
  python tools/scripts/pitch_mod512_check.py --simdir sim_build/pitchmod512 --fs 48828.125
"""
import argparse
import math
import os
import sys


def load_hex(path):
    vals = []
    with open(path) as f:
        for line in f:
            for w in line.split():
                vals.append(int(w, 16))
    return vals


def load_col(path):
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
        print("   （%s：跳过 %d 行非数值，多为上电 x）" % (os.path.basename(path), skipped))
    return vals


def load_matrix(path):
    return [[int(x) for x in l.split()] for l in open(path) if l.strip()]


def dinc(ph):
    return [(ph[i + 1] - ph[i]) % (1 << 24) for i in range(len(ph) - 1)]


def cents(f, f0):
    return 1200.0 * math.log2(f / f0)


def glide_mirror(gq0, step, n):
    """线性速率滑音的 Python 镜像（严格照抄 pitch_mod.v）"""
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
    ap.add_argument("--simdir", default="sim_build/pitchmod512")
    ap.add_argument("--fs", type=float, default=48828.125)
    ap.add_argument("--lfo-hz", type=float, default=50.0)
    ap.add_argument("--depth", type=float, default=1000.0)
    ap.add_argument("--step", type=int, default=10,
                    help="滑音速率（Q16/样本），与测试台 pmod_cfg 里的一致")
    a = ap.parse_args()
    d = a.simdir

    NOTE_OLD, NOTE_NEW = 56, 72           # 16 号组：原 MIDI 56 → 抢占地 MIDI 72
    note_inc = load_hex(os.path.join(d, "note_inc.hex"))
    recip = load_hex(os.path.join(d, "recip_inc.hex"))
    INC_OLD, INC_NEW = note_inc[NOTE_OLD], note_inc[NOTE_NEW]

    print("=" * 68)
    print(" 512 档功能仿真判据（NG=32 / NSLOT=512 / fs=%.3f Hz）" % a.fs)
    print("=" * 68)
    fails = []

    # ======================================================================
    # E1a 32 复音
    # ======================================================================
    fund = load_matrix(os.path.join(d, "p512_fund.txt"))
    ncol = len(fund[0])
    print("\n[E1a] 32 复音：基频时隙的相位增量 vs 表期望（%d 行 × %d 列）"
          % (len(fund), ncol))
    good, bad = 0, []
    for c in range(ncol):
        col = [fund[r][c] for r in range(len(fund))]
        dg = dinc(col)
        if all(x == note_inc[40 + c] for x in dg):
            good += 1
        else:
            bad.append((c, 40 + c, note_inc[40 + c], dg[0] if dg else None))
    print("     基频完全正确的声部数 = %d / %d" % (good, ncol))
    for c, n, exp, got in bad:
        print("       ✗ 组 %2d（MIDI %d）期望 %d，实测 %s" % (c, n, exp, got))
    if good != ncol:
        fails.append("E1a: 只有 %d/%d 路声部基频正确" % (good, ncol))

    # ======================================================================
    # E1b FFT 旁证（只作旁证，不作硬判据）
    #   E1a 已经【精确】证明 32 路声部各自正确（相位增量逐个等于表值）。
    #   FFT 在这里只能当旁证：4096 点、fs=48828 Hz → 分辨率 11.9 Hz，
    #   而低音区相邻音间隔只有 4.9 Hz（MIDI 40/41），32 个音的谐波又互相重叠
    #   —— 本来就不可能把 32 个基频"数"出来。所以这里只检查
    #   "期望基频附近是不是局部极大（能量占比 > 1%）"。
    # ======================================================================
    print("\n[E1b] FFT 旁证（高音区 16 个基频；仅旁证，硬判据是 E1a）")
    try:
        import numpy as np
        y = np.array(load_col(os.path.join(d, "p512_out.txt")), dtype=float)
        n = 4096
        seg = y[len(y) // 2: len(y) // 2 + n]
        if len(seg) < n:
            seg = y[-n:]
        S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        fr = np.fft.rfftfreq(len(seg), 1.0 / a.fs)
        S[0] = 0
        res = a.fs / n
        hit, miss = 0, []
        for nn in range(56, 72):
            exp = 440.0 * 2 ** ((nn - 69) / 12.0)
            k = int(round(exp / res))
            lo, hi = max(1, k - 2), min(len(S) - 1, k + 2)
            if S[lo:hi + 1].max() > S.max() * 0.01:
                hit += 1
            else:
                miss.append((nn, exp))
        print("     FFT 分辨率 %.1f Hz；高音区 16 个基频附近有能量的 = %d / 16" % (res, hit))
        if miss:
            print("       能量偏低的：%s" % ["MIDI %d(%.1fHz)" % m for m in miss])
        if hit < 8:
            print("     ⚠ 旁证偏弱（不影响 E1a 的结论，但值得看一眼）")
    except ImportError:
        print("     （无 numpy，跳过）")

    # ======================================================================
    # G1/G2 滑音（16 号组）
    # ======================================================================
    gf = dinc(load_col(os.path.join(d, "p512_g_f.txt")))
    gp = dinc(load_col(os.path.join(d, "p512_g_p.txt")))
    print("\n[G] 滑音（16 号组 = slot 256/271，MIDI %d → %d）" % (NOTE_OLD, NOTE_NEW))

    t0 = None
    for i in range(len(gf) - 1):
        if gf[i] == INC_OLD and gf[i + 1] != INC_OLD:
            t0 = i
    if t0 is None:
        print("     ★ 找不到滑音起始点（抢占没落到 16 号组？）")
        fails.append("G: 未检出 16 号组的滑音起始")
    else:
        print("     滑音起始于第 %d 个样本（之前 inc=%d = MIDI %d）"
              % (t0, INC_OLD, NOTE_OLD))
        gq_raw = ((INC_OLD - INC_NEW) * recip[NOTE_NEW]) >> 16
        gq0 = max(-114688, min(131071, gq_raw))
        gq_seq = glide_mirror(gq0, a.step, len(gf) - t0)
        exp = [INC_NEW + ((INC_NEW * g) >> 16) for g in gq_seq]
        best = None
        for lag in range(0, 8):
            n = len(exp) - lag
            if n < 200:
                break
            diff = sum(1 for j in range(n) if gf[t0 + lag + j] != exp[j])
            if best is None or diff < best[1]:
                best = (lag, diff, n)
        print("     初值 gq0 = %d（Q2.16，≈ %+.1f 音分）" % (gq0, cents(1 + gq0 / 65536.0, 1.0)))
        print("     G1 轨迹 vs Python 镜像：滞后 %d 样本，不符 %d / %d"
              % (best[0], best[1], best[2]))
        if best[1] != 0:
            fails.append("G1: 轨迹与镜像不符 %d/%d" % (best[1], best[2]))
            shown = 0
            for j in range(best[2]):
                if gf[t0 + best[0] + j] != exp[j]:
                    print("        j=%4d 实测 %7d 镜像 %7d" % (j, gf[t0 + best[0] + j], exp[j]))
                    shown += 1
                    if shown >= 5:
                        break
        # G2 比例性
        rmin, rmax, bad_n = 9e9, 0.0, 0
        for i in range(2, len(gf)):
            if gf[i] == 0:
                continue
            r = gp[i] / float(gf[i])
            rmin, rmax = min(rmin, r), max(rmax, r)
            if abs(r - 16.0) > 0.016:
                bad_n += 1
        print("     G2 比例 d271/d256：最小 %.5f 最大 %.5f（应为 16）" % (rmin, rmax))
        if rmax > 16.016 or rmin < 15.984 or bad_n > 2:
            fails.append("G2: 比例偏离 16（越界 %d 个样本）" % bad_n)
        tail = gf[-200:]
        print("     尾部均值 %.1f（目标 %d，未收敛是正常的：τ≈58 ms，观察窗只有 123 ms）"
              % (sum(tail) / len(tail), INC_NEW))

    # ======================================================================
    # V1/V2 颤音
    # ======================================================================
    INC60 = note_inc[60]
    b0 = [x for x in dinc(load_col(os.path.join(d, "p512_b0.txt"))) if x > 0][300:]
    b15 = [x for x in dinc(load_col(os.path.join(d, "p512_b15.txt"))) if x > 0][300:]
    print("\n[B] 颤音：设定深度 %.2f 音分，LFO %.2f Hz" %
          (cents(1 + a.depth / 65536.0, 1.0), a.lfo_hz))
    if not b0:
        print("     ★ 无数据")
        fails.append("V: 无数据")
    else:
        c0 = [cents(x, INC60) for x in b0]
        c15 = [cents(x, INC60 * 16) for x in b15]
        print("     V1 slot0：频偏 %+.2f .. %+.2f 音分（峰峰 %.2f）"
              % (min(c0), max(c0), max(c0) - min(c0)))
        exp_depth = cents(1 + a.depth / 65536.0, 1.0)
        pk = (max(c0) - min(c0)) / 2.0
        if abs(pk - exp_depth) > max(1.0, exp_depth * 0.1):
            fails.append("V1a: 颤音幅度 %.2f ≠ 设定 %.2f" % (pk, exp_depth))
        mean = sum(c0) / len(c0)
        cross = [i for i in range(1, len(c0)) if c0[i - 1] < mean <= c0[i]]
        if len(cross) >= 3:
            per = (cross[-1] - cross[0]) / float(len(cross) - 1) / a.fs
            print("     V1 LFO 周期实测 = %.5f s（期望 %.5f s）" % (per, 1.0 / a.lfo_hz))
            if abs(per - 1.0 / a.lfo_hz) > 0.02 / a.lfo_hz:
                fails.append("V1b: LFO 周期 %.5f ≠ %.5f" % (per, 1.0 / a.lfo_hz))
        else:
            print("     V1 ★ 过均值点不足（%d 个），无法测周期" % len(cross))
        dv = max(abs(c15[i] - c0[i]) for i in range(min(len(c0), len(c15))))
        print("     V2 两泛音 cents 偏移最大差 = %.4f 音分" % dv)
        if dv > 0.1:
            fails.append("V2: 泛音间 cents 差 %.3f > 0.1" % dv)

    print("\n" + "=" * 68)
    if fails:
        print(" ★ 未通过：")
        for x in fails:
            print("   -", x)
        return 1
    print(" ★★★ 512 档全部通过（E1a/E1b/G1/G2/V1/V2）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
