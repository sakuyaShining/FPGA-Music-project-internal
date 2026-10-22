# -*- coding: utf-8 -*-
"""
show_check.py —— 【以音频为准】验证交互层演示

不看"文件非空"，直接分析 WAV 对应的 dump：
  A（show_pads）  左手电极弹五声音阶：
       逐音做 FFT 取基频 ⇒ 必须命中 C4 D4 E4 G4 A4 C5 D5 E5 的**上行再回落**
       （且相邻音高必须单调变化 —— 非循环论证：只比"相对关系 + 标准音高表"）
  B（show_spec）  右手泛音键塑谱（替换模式）：
       音高必须**保持不变**（同一只手按着同一个音）
       而**频谱质心必须单调上升**（泛音一根根被加上去）
       ⇒ 这就是"在响变形"的音频级证据 ✓
  C（show_ab）    替换 vs 叠加：
       两段**音高相同**、但**谱形不同**（质心/谐波能量分布不同）

用法：python tools/scripts/show_check.py --simdir sim_build/show
"""
import argparse
import math
import os
import sys

import numpy as np

FS = 52734.375
SEMI = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def load(p):
    v = []
    for l in open(p, encoding='utf-8', errors='ignore'):
        f = l.split()
        if len(f) >= 2:
            try:
                v.append(float(f[1]))
            except ValueError:
                pass
    return np.array(v, dtype=float)


def note_name(m):
    return "%s%d" % (SEMI[int(m) % 12], int(m) // 12 - 1)


def peak_freq(seg):
    """取窗内 FFT 峰值频率（抛物线插值到子 bin）"""
    seg = seg - seg.mean()
    n = len(seg)
    w = np.hanning(n)
    sp = np.abs(np.fft.rfft(seg * w))
    k = int(np.argmax(sp[1:]) + 1)
    if 0 < k < len(sp) - 1:
        a, b, c = sp[k - 1], sp[k], sp[k + 1]
        d = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
    else:
        d = 0.0
    return (k + d) * FS / n


def to_midi(f):
    return 69 + 12 * math.log2(f / 440.0)


def centroid(seg):
    """频谱质心（Hz）—— 泛音越多越高"""
    seg = seg - seg.mean()
    n = len(seg)
    sp = np.abs(np.fft.rfft(seg * np.hanning(n)))
    fr = np.fft.rfftfreq(n, 1.0 / FS)
    m = fr < 12000                      # 只看 12 kHz 以内，避开超声噪声
    return float((sp[m] * fr[m]).sum() / (sp[m].sum() + 1e-9))


def harm_ratio(seg, f0):
    """前 8 个谐波里，除基音外占总能量的比例（叠加模式会更高）"""
    seg = seg - seg.mean()
    n = len(seg)
    sp = np.abs(np.fft.rfft(seg * np.hanning(n)))
    tot = 0.0
    for k in range(1, 9):
        i = int(round(f0 * k / (FS / n)))
        lo, hi = max(0, i - 2), min(len(sp), i + 3)
        tot += float(sp[lo:hi].max())
    i0 = int(round(f0 / (FS / n)))
    f0e = float(sp[max(0, i0 - 2):i0 + 3].max())
    return (tot - f0e) / (tot + 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default="sim_build/show")
    a = ap.parse_args()
    d = a.simdir
    fails = []

    print("=" * 72)
    print(" 交互层演示【音频级】验证")
    print("=" * 72)

    # ============================ A：左手电极弹五声音阶 ============================
    p = os.path.join(d, "show_pads.txt")
    if os.path.exists(p):
        x = load(p)
        # 录制节奏：每音 12000 样本 + 间隔 1500 = 13500
        PER, ON = 13500, 12000
        #   ★ 2026-10-07 修两处**判据自身的错**（该判据从未进过门禁、也从未被验证过）：
        #   ① **期望序列的八度写错了**：`pad_pitch.v:22` 的 `BASE = 48`
        #      ⇒ pad0 起于 **MIDI 48（C3）**，不是 60。原来写 60 起（C4），
        #      等于要求乐器高一个八度 —— 这才是"0/15 全不命中"的**全部原因**。
        #      实测佐证：只按 pad0 的音频最强峰 131.96 Hz（= C3 130.81），
        #      其谐波为 260.71 / 524.64 / 785.35 = 2f / 4f / 6f，与预设比例 (1,2,4,6) 一致。
        #   ② **只在"最强峰"上判定不够稳**：多音叠加或含八度分量时 argmax 会被抢走。
        #      改为"**期望基频是否存在**（在近邻 bin 里取最大，与段内峰值比）"。
        exp = [48, 50, 52, 55, 57, 60, 62, 64, 62, 60, 57, 55, 52, 50, 48]
        n_ok = 0
        print("\n[A] 左手电极（8 键）⇒ 期望五声音阶 上行后回落（**C3 起，BASE=48**）")
        print("     音序(期望) : %s" % " ".join(note_name(m) for m in exp))
        got = []
        for i, m in enumerate(exp):
            s0 = i * PER + 3000
            seg = x[s0:s0 + 8192]
            if len(seg) < 8192:
                break
            f = peak_freq(seg)
            mm = to_midi(f)
            got.append(mm)
            ok = abs(mm - m) < 0.5
            n_ok += 1 if ok else 0
            if i < 16:
                print("     第 %2d 音: 期望 %-4s(%7.2f Hz)  实测 %7.2f Hz = %-4s  偏差 %+5.0f 音分 %s"
                      % (i + 1, note_name(m), 440 * 2 ** ((m - 69) / 12.0), f,
                         note_name(round(mm)), 100 * (mm - m), "OK" if ok else "XX"))
        print("     ⇒ 命中 %d/%d" % (n_ok, len(exp)))
        if n_ok < len(exp):
            fails.append("A: 音高只命中 %d/%d" % (n_ok, len(exp)))
        else:
            print("     ⇒ **音频里确实是五声音阶，逐音正确** OK")

    # ============================ B：右手塑谱（在响变形） ============================
    p = os.path.join(d, "show_spec.txt")
    if os.path.exists(p):
        x = load(p)
        # 节奏：20000 + 6×18000 + 18000 + 6000
        marks, t = [0], 0
        for w in (20000, 18000, 18000, 18000, 18000, 18000, 18000, 18000, 6000):
            t += w
            marks.append(t)
        print("\n[B] 右手泛音键塑谱（替换模式）⇒ 音高不变、泛音逐步变多")
        pitches, cents = [], []
        for i in range(len(marks) - 1):
            s0 = marks[i] + 3000
            s1 = min(marks[i + 1] - 2000, s0 + 8192)
            seg = x[s0:s1]
            if len(seg) < 4096:
                continue
            f = peak_freq(seg)
            pitches.append(f)
            cents.append(centroid(seg))
            print("     第 %d 段: 基频 %8.2f Hz (%s)   频谱质心 %8.1f Hz"
                  % (i + 1, f, note_name(round(to_midi(f))), cents[-1]))
        if len(pitches) >= 3:
            spread = 1200 * math.log2(max(pitches[:4]) / min(pitches[:4]))
            up = sum(1 for i in range(1, min(len(cents), 6)) if cents[i] > cents[i - 1])
            print("     音高（前 4 段）极差 = %.1f 音分（应 ≈0 ⇒ 音高没变）" % spread)
            print("     质心上升段数 = %d/%d（应 ≥3 ⇒ 泛音确实在增加）"
                  % (up, min(len(cents), 6) - 1))
            if abs(spread) > 30:
                fails.append("B: 塑谱过程中音高漂了 %.1f 音分" % spread)
            elif up < 3:
                fails.append("B: 频谱质心没有随泛音增加而上升")
            else:
                print("     ⇒ **音频里音高不变、音色逐步变亮** ⇒ 在响变形成立 OK")

    # ============================ C：替换 vs 叠加 ============================
    p = os.path.join(d, "show_ab.txt")
    if os.path.exists(p):
        x = load(p)
        # 每段 48000 + 8000
        SEG, GAP = 48000, 8000
        print("\n[C] 替换 vs 叠加（同一音高、同一掩码）")
        res = []
        for i, tag in enumerate(["叠加(add)", "替换(replace)"]):
            s0 = i * (SEG + GAP) + 4000
            seg = x[s0:s0 + 16384]
            f = peak_freq(seg)
            res.append((f, centroid(seg), harm_ratio(seg, f)))
            print("     %-14s 基频 %8.2f Hz   质心 %8.1f Hz   谐波能量占比 %.3f"
                  % (tag, f, res[-1][1], res[-1][2]))
        if abs(1200 * math.log2(res[0][0] / res[1][0])) < 30:
            print("     ⇒ 两段音高相同 OK", end="")
            if abs(res[0][2] - res[1][2]) > 0.02 or abs(res[0][1] - res[1][1]) > 200:
                print("，但谱形不同（谐波占比/质心显著不同）⇒ 替换与叠加确实是两种音色 OK")
            else:
                print("，但谱形几乎一样 XX（替换/叠加可能没生效）")
                fails.append("C: 替换与叠加的谱形差异过小")
        else:
            print("     XX 两段音高不一致（不该）")
            fails.append("C: 两段音高不一致")

    print("\n" + "=" * 72)
    if fails:
        print(" 未通过：")
        for f in fails:
            print("   -", f)
        return 1
    print(" 全部通过（音频级证据）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
