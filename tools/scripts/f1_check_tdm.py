#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
f1_check_tdm.py —— F1 判据：TDM 测试模式 512 频率栅格的独立谱峰验证

判据（赛题原文："频谱可观测对应数量独立谱峰"）：
  G1  栅格覆盖：512 个期望频率逐一在 FFT 中表现为局部极大（允许 ±1 bin 对齐误差）
  G2  峰计数：检出独立峰数 ≥ 500（合并容差；理论 512）
  G3  无谱外能量：栅格 ±8Hz 之外的能量占比 < 5%（证明没有额外杂散/混叠）
  G4  峰位精度：每个检出峰与最近栅格点偏差 < 半个栅格间距（13.85 Hz）

用法：
  python tools/scripts/f1_check_tdm.py --simdir sim_build/f1
（simdir 下需有 f1_samples.txt，由 tb_tdm_f1.v 生成）
"""
import argparse
import os

import numpy as np

FS = 52734.375
F0 = 225.0
DF = 27.7          # 栅格间距（tdm_top 注释口径）
NSLOT = 512


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default="sim_build/f1")
    ap.add_argument("--nsamp", type=int, default=16384)
    args = ap.parse_args()

    path = os.path.join(args.simdir, "f1_samples.txt")
    if not os.path.isfile(path):
        print("[ERROR] 缺 f1_samples.txt（先跑 tb_tdm_f1）")
        return 1
    x = np.array([float(v) for v in open(path) if v.strip()], dtype=float)
    n = min(len(x), args.nsamp)
    x = x[:n]
    print("====== F1 判据：TDM 测试模式 512 频率栅格 ======")
    print("样本 %d，fs=%.3f Hz，FFT 分辨率 %.3f Hz" % (n, FS, FS / n))

    X = np.abs(np.fft.rfft(x * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, 1.0 / FS)
    grid = (71583.0 + 8800.0 * np.arange(NSLOT)) * FS / 2**24   # ★ 精确栅格：直接用 RTL 公式（27.7 的四舍五入会累计漂移 18Hz

    # G1：每个栅格点的最近 bin 是否为局部极大
    ok_grid = 0
    worst_dev = 0.0
    grid_hits = np.zeros(NSLOT, dtype=bool)
    for k, f in enumerate(grid):
        lo, hi = int(np.searchsorted(freqs, f - DF / 2)), int(np.searchsorted(freqs, f + DF / 2))
        if hi <= lo + 1:
            continue
        seg = X[lo:hi]
        pk = lo + int(np.argmax(seg))
        # 局部极大（在栅格半间距窗口内）
        if 0 < pk < len(X) - 1 and X[pk] >= X[pk - 1] and X[pk] >= X[pk + 1] and X[pk] > X.max() * 0.02:
            ok_grid += 1
            grid_hits[k] = True
            worst_dev = max(worst_dev, abs(freqs[pk] - f))
    print("  [G1] 栅格覆盖：512 格中 %d 个表现为独立局部极大" % ok_grid)

    # G2：经典峰检出（全谱）
    thr = X.max() * 0.02
    peaks = [i for i in range(1, len(X) - 1) if X[i] > X[i - 1] and X[i] >= X[i + 1] and X[i] > thr]
    print("  [G2] 检出独立峰：%d（理论 512，容差 ≥500）" % len(peaks))

    # G3：栅格外能量占比（栅格 ±8 Hz 之外）
    mask_on = np.zeros(len(freqs), dtype=bool)
    for f in grid:
        mask_on[(freqs > f - 8) & (freqs < f + 8)] = True
    off_ratio = float(X[~mask_on].sum() / X.sum())
    print("  [G3] 谱外能量占比：%.2f%%（< 5%% 为过）" % (off_ratio * 100))

    # G4：峰位精度
    devs = [min(abs(freqs[i] - g) for g in grid) for i in peaks]
    ok4 = all(d < DF / 2 for d in devs)
    print("  [G4] 峰位偏差：max %.2f Hz（< 半格 %.2f Hz）" % (max(devs) if devs else 0, DF / 2))

    fails = []
    if ok_grid < NSLOT:
        fails.append("G1 栅格覆盖不足")
    if len(peaks) < 500:
        fails.append("G2 峰计数不足")
    if off_ratio >= 0.05:
        fails.append("G3 谱外能量超标")
    if not ok4:
        fails.append("G4 峰位偏差超标")

    print("-" * 50)
    if not fails:
        print("  ★★★ 通过：512 个独立谱峰与栅格一一对应（G1-G4）")
        return 0
    print("  ★ 未通过：" + "；".join(fails))
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
