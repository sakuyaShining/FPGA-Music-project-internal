# -*- coding: utf-8 -*-
"""从冲激响应里直接量：回声间距（= 环路周期）与相邻回声幅度比（= 环路增益）。
这是【与理论尺子无关】的经验测量 ✓ —— 用它校准 T60 的参考公式。"""
import sys
import numpy as np

FS = 52734.375


def peaks(x, thr_ratio=0.2, min_gap=5):
    a = np.abs(x)
    thr = thr_ratio * a.max()
    out = []
    i = 1
    while i < len(a) - 1:
        if a[i] > thr and a[i] >= a[i - 1] and a[i] > a[i + 1]:
            out.append((i, x[i]))
            i += min_gap
        else:
            i += 1
    return out


for fb in (0x40, 0x80, 0xC0, 0xE0):
    p = "sim_build/t60/t60_fb%02x.txt" % fb
    x = np.array([float(l) for l in open(p)])
    pk = peaks(x, 0.05)
    gaps = [pk[i + 1][0] - pk[i][0] for i in range(min(8, len(pk) - 1))]
    ratios = [abs(pk[i + 1][1]) / abs(pk[i][1]) for i in range(min(8, len(pk) - 1)) if pk[i][1]]
    sat = int((np.abs(x) >= 32767).sum())
    print("fb=0x%02X: 前 %d 个峰，间距=%s" % (fb, len(pk), gaps[:6]))
    print("          相邻幅度比=%s" % ["%.4f" % r for r in ratios[:4]])
    if gaps:
        g = int(np.median(gaps))
        print("          ⇒ 经验环路周期 = %d 样本 = %.3f ms" % (g, g / FS * 1000))
    if ratios:
        print("          ⇒ 经验环路增益 = %.4f（RTL 的 RV_FB/256 = %.4f）"
              % (float(np.median(ratios)), fb / 256.0))
    print("          饱和样本数(|x|>=32767) = %d" % sat)
