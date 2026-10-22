#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tdm_compare.py —— TDM 黄金参考比对（解析真值法）

【为什么要有"解析真值"这第三只手】
  只比"并行 vs TDM"时，两边对不上你不知道该信谁。
  本脚本用第一性原理算出每个样本应有的值：

      prod_s(n) = (table[(n × inc_s) >> 16] × (amp_s << 8)) >> 16
      sum(n)    = Σ_s prod_s(n)

  于是可以分别问："并行偏了多少？""TDM 偏了多少？"——定位范围立刻减半。
  实测：全并行引擎与解析真值完全一致（这顺带把并行引擎也独立验证了一遍）。

【用法】
  python tools/scripts/tdm_compare.py --simdir sim_build/tdm --mask 0x3
    --mask  活跃时隙掩码（十六进制）。0 号时隙幅度 200，其余 100。
"""
import argparse
import os
import sys

import numpy as np


def load_sine(path):
    tab = []
    with open(path) as f:
        for line in f:
            for w in line.split():
                v = int(w, 16)
                if v >= 32768:
                    v -= 65536
                tab.append(v)
    assert len(tab) == 256, "正弦表应为 256 项，实得 %d" % len(tab)
    return tab


BASE = [11811, 14881, 17698, 23622]      # 4 个声部的基频 inc（fs=312500）
NSLOT = 32
NPART = 8


def build_amps(mask):
    amps = [0] * NSLOT
    for s in range(NSLOT):
        if (mask >> s) & 1:
            amps[s] = 200 if s == 0 else 100
    return amps


def model(tab, amps, n):
    tot = 0
    for s in range(NSLOT):
        if amps[s] == 0:
            continue
        v, k = s // NPART, s % NPART
        addr = ((n * BASE[v] * (k + 1)) & 0xFFFFFF) >> 16
        tot += (tab[addr] * (amps[s] << 8)) >> 16
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default=r"sim_build\tdm")
    ap.add_argument("--mask", default="0x3")
    ap.add_argument("--nsamp", type=int, default=500)
    ap.add_argument("--skip", type=int, default=0,
                    help="黄金参考比对时跳过前 N 个样本。包络打开时两个引擎的"
                         "起音触发时刻差几个周期（稳态后一致），跳过起音段即可。")
    args = ap.parse_args()

    mask = int(args.mask, 16)
    tab = load_sine(os.path.join(args.simdir, "sine256.hex"))
    amps = build_amps(mask)

    # 前几拍流水线尚未建立，可能出现 X（未初始化）。
    #   直接 int() 会抛 ValueError 把比对脚本打断 —— 这里显式跳过非数值行，
    #   而不是让它崩掉（崩掉会让人误以为"设计坏了"，其实是数据里有 X）。
    def _num(s):
        try:
            return int(s)
        except ValueError:
            return None

    raw = [l.split() for l in open(os.path.join(args.simdir, "tdm_sum.txt")) if l.strip()]
    rows = []
    n_skip = 0
    for r in raw:
        a, b = _num(r[0]), _num(r[1])
        if a is None or b is None:
            n_skip += 1
            continue
        rows.append((a, b))
    if n_skip:
        print("  （跳过 %d 行含 X 的采样 —— 流水线建立前的正常现象）" % n_skip)
    slot = np.array([a for a, _ in rows])
    val = np.array([b for _, b in rows])
    tdm = val[slot == NSLOT - 1]

    par = np.array([int(x) for x in open(os.path.join(args.simdir, "par_sum.txt"))])

    N = min(len(tdm), len(par), args.nsamp)
    exp = np.array([model(tab, amps, n) for n in range(N + 40)])

    print("掩码 0x%08X   活跃时隙 %d 个   比对 %d 个样本" % (mask, bin(mask).count("1"), N))
    print("  解析真值 前 10 :", [model(tab, amps, n) for n in range(10)])
    print("  并行引擎 前 10 :", list(par[:10]))
    print("  TDM  引擎 前 10 :", list(tdm[:10]))

    ok = True
    for name, arr in (("并行", par), ("TDM ", tdm)):
        best = None
        for k in range(0, 30):
            n = N - k
            if n < 100:
                break
            d = int(np.sum(arr[k:k + n] != exp[:n]))
            if best is None or d < best[1]:
                best = (k, d, n)
        tag = "  ★★★ 与解析真值完全一致" if best[1] == 0 else ""
        if best[1] != 0:
            ok = False
        print("  %s 滞后 %2d 拍 : 不符 %4d / %-4d%s" % (name, best[0], best[1], best[2], tag))

    #-------------------------------------------------------------------------
    # 黄金参考：TDM 直接与【全并行引擎】逐位比对
    #   解析真值模型没建模包络（amp_eff 恒等于 amp<<8），
    #   所以包络打开时上面那两项必然对不上 —— 那不是错误，是模型不适用。
    #   而目标要求的验收标准本来就是"TDM ≡ 全并行"，这一项在任何配置下都成立。
    #-------------------------------------------------------------------------
    golden_ok = False
    bestg = None
    pg = par[args.skip:]
    tg = tdm[args.skip:]
    for k in range(0, 40):
        n = min(len(pg), len(tg)) - k
        if n < 200:
            break
        d = int(np.sum(pg[k:k + n] != tg[:n]))
        if bestg is None or d < bestg[1]:
            bestg = (k, d, n)
        if d == 0:
            golden_ok = True
    tag = "  ★★★ 黄金参考通过：TDM 与全并行逐位一致" if golden_ok else ""
    print("  ── 黄金参考 TDM vs 并行 (跳过前 %d 个样本) : 延迟 %d, 不符 %d / %d%s"
          % (args.skip, bestg[0], bestg[1], bestg[2], tag))

    if not golden_ok:
        ok = False

    print("  => %s" % ("★ 全部通过" if ok else "仍有差异（见上）"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
