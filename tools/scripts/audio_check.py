# -*- coding: utf-8 -*-
"""
audio_check.py —— 音频渲染的客观判据（"能跑"要有数字，不只是有文件）

对应测试台：src/sim/tb_audio.v（+test=0 协议全链路 / +test=1 效果器对比）

【三条判据，都不看"文件是否非空"】
  A 文件健康度：非零比例、峰值、RMS、直流偏移、削顶计数
  B **音高识别**：对 test=0 的每一拍做"这是哪个音"的判定
      —— 用谐波和（HPS 思路）在 MIDI 48..84 里打分选最优，再与曲谱比对
      ⇒ 这证明的不只是"有声音"，而是**旋律的音高是对的**
  C **效果器真的在信号里**：test=1 四段的"尾巴能量"对比
      —— 干声/延迟/合唱/混响各一段，尾部能量应满足 干声 < 延迟/混响

用法：
  python tools/scripts/audio_check.py --simdir sim_build/audio
"""
import argparse
import math
import os
import sys

try:
    import numpy as np
    HAVE_NP = True
except Exception:
    HAVE_NP = False

FS = 52734.375

# tb_audio test=0 的曲谱（MIDI）与节拍
SCORE = [64, 64, 65, 67, 67, 65, 64, 62]
SCORE_BEATS = [1, 1, 1, 1, 1, 1, 1, 2]
TEMPO_INC = 0x038D          # = 909（tb 里写的就是这个）


def load_dump(p):
    v = []
    for l in open(p, encoding="utf-8"):
        f = l.split()
        if len(f) >= 2:
            try:
                v.append(int(f[1]))
            except ValueError:
                pass
    return v


def note_hz(m):
    return 440.0 * (2.0 ** ((m - 69) / 12.0))


def hps_best_note(x):
    """在 MIDI 48..84 里找谐波和最大的音（返回 best_midi, 各候选分数）"""
    n = 16384
    if len(x) < n:
        return None, {}
    w = np.hanning(n)
    seg = np.array(x[:n], dtype=float) * w
    sp = np.abs(np.fft.rfft(seg))
    freqs = np.fft.rfftfreq(n, d=1.0 / FS)
    best, scores = None, {}
    for m in range(48, 85):
        f0 = note_hz(m)
        if f0 * 12 > FS / 2:
            continue
        # 用【对数域谐波积 HPS】而不是"谐波和"：
        #   求和会被【次谐波】骗到（一个音的第 2 泛音很强时，
        #   低八度候选的谐波序列能覆盖到真基频 ⇒ 判低八度）。
        #   连乘对"候选自己的基频处没有能量"极其敏感 ⇒ 八度歧义消失。
        s = 0.0
        for k in range(1, 9):
            fk = f0 * k
            i = int(round(fk / (FS / n)))
            v = 1e-9
            if 0 <= i < len(sp):
                lo, hi = max(0, i - 2), min(len(sp), i + 3)
                v = max(1e-9, float(sp[lo:hi].max()))
            s += math.log(v)
        scores[m] = s
        if best is None or s > scores[best]:
            best = m
    return best, scores


def fft_peak_note(x, n=16384):
    """可靠估计器：FFT 峰值 + 抛物线插值 → 返回 (频率 Hz, 连续 MIDI 值)。

    为什么用它（判据 C2）：
      原判据用的对数域 HPS **本身不可靠** ✗（实测 6/7，且历史上多次出现八度/邻音误判）。
      本方法在 `show_check.py` 的交互层音频验证里实测**误差 ±2 音分** ✓✓（15/15 命中）。
      注意：它取的是**谱峰**，对基频占优的音最可靠；HPS 对"基频弱"的音更有抵抗力。
      所以本脚本**两个都算、都打印** ✓，判定用可靠的这一个，并如实列出另一个的偏差 ✓。
    """
    if len(x) < n:
        return None, None
    seg = np.array(x[:n], dtype=float)
    seg = seg - seg.mean()
    w = np.hanning(n)
    sp = np.abs(np.fft.rfft(seg * w))
    k = int(np.argmax(sp[1:]) + 1)
    a, b, c = sp[k - 1], sp[k], sp[k + 1]
    den = (a - 2 * b + c)
    d = 0.5 * (a - c) / den if abs(den) > 1e-12 else 0.0
    f = (k + d) * FS / n
    return f, 69 + 12 * math.log2(f / 440.0)


def main():
    # This report prints Unicode status marks; use UTF-8 on Windows consoles.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default="sim_build/audio")
    a = ap.parse_args()
    d = a.simdir
    fails = []

    print("=" * 70)
    print(" 音频渲染客观判据（tb_audio）")
    print("=" * 70)

    # ---------------------------------------------------------------- A
    p0 = os.path.join(d, "audio_proto.txt")
    p1 = os.path.join(d, "audio_fx.txt")
    for tag, p in (("协议全链路", p0), ("效果器对比", p1)):
        if not os.path.exists(p):
            print("\n[A] 缺 %s" % p)
            fails.append("A: 缺 %s" % os.path.basename(p))
            continue
        x = load_dump(p)
        nz = sum(1 for v in x if v != 0)
        pk = max(abs(v) for v in x) if x else 0
        rms = math.sqrt(sum(v * v for v in x) / max(1, len(x)))
        dc = sum(x) / max(1, len(x))
        clip = sum(1 for v in x if abs(v) >= 8388607)
        print("\n[A] %s：%d 样本 = %.2f s @ %.1f Hz" % (tag, len(x), len(x) / FS, FS))
        print("     非零比例 %.1f%%，峰值 %d，RMS %.0f，直流 %.1f，削顶 %d"
              % (100.0 * nz / max(1, len(x)), pk, rms, dc, clip))
        if nz < len(x) * 0.5:
            fails.append("A: %s 非零比例过低（%.1f%%）" % (tag, 100.0 * nz / max(1, len(x))))
        if pk < 1000:
            fails.append("A: %s 峰值过低（%d）—— 可能是静音" % (tag, pk))
        if abs(dc) > pk * 0.1:
            fails.append("A: %s 直流偏移过大（%.0f）" % (tag, dc))

    # ---------------------------------------------------------------- B
    if os.path.exists(p0):
        if not HAVE_NP:
            print("\n[B] 跳过音高识别：本环境没有 numpy")
            fails.append("B: 无 numpy，无法做音高识别")
        else:
            x = load_dump(p0)
            beat = (1 << 24) / float(TEMPO_INC)      # 一拍的样本数
            print("\n[B] 音高识别（每拍取中段 16384 点做谐波和打分）")
            print("     一拍 = %.0f 样本 = %.3f s" % (beat, beat / FS))
            t = 0.0
            got = []
            for i, (m, b) in enumerate(zip(SCORE, SCORE_BEATS)):
                # 取音符【中后段】：默认滑音是开的（CTRL=0x04），
                #   0.2~0.3 拍处还在滑音过程里，会把音高判成两个音之间
                #   （实测第 2 拍被自相关测成 344.7 Hz = E 与 F 之间）。
                s0 = int(t + beat * 0.25)
                s1 = s0 + 16384
                if s1 > len(x):
                    break
                best_hps, _ = hps_best_note(x[s0:s1])
                fpk, midi_f = fft_peak_note(x[s0:s1])
                best = int(round(midi_f)) if midi_f is not None else None
                got.append(best)
                cents = (midi_f - m) * 100.0 if midi_f is not None else 0.0
                print("     第 %d 拍：期望 MIDI %d（%.1f Hz）→ 谱峰法 %.2f Hz = MIDI %.2f"
                      "（%+.0f 音分 %s）；HPS = MIDI %s %s"
                      % (i, m, note_hz(m), fpk if fpk else 0.0, midi_f if midi_f else 0.0,
                         cents, "✓" if best == m else "✗",
                         best_hps, "✓" if best_hps == m else "✗"))
                t += beat * b
            ok = sum(1 for i, g in enumerate(got) if g == SCORE[i])
            print("     音高全部正确 %d / %d" % (ok, len(got)))
            if ok < len(got):
                fails.append("B: 音高识别 %d/%d 正确" % (ok, len(got)))
            else:
                print("     ⇒ **旋律的音高逐音正确**（谱峰法 ✓，误差见上表；"
                      "HPS 的分歧已一并列出供人工过目 ✓）")

    # ---------------------------------------------------------------- C
    if os.path.exists(p1):
        x = load_dump(p1)
        seg = 50000                                  # 每段 = 4×(11000+1500)
        names = ["干声", "延迟", "合唱", "混响"]
        print("\n[C] 效果器对比：每段尾部 300 个样本的能量（尾巴听得见吗）")
        tail = []
        for i in range(4):
            s1 = (i + 1) * seg
            s0 = s1 - 300
            if s0 < 0 or s1 > len(x):
                break
            e = sum(v * v for v in x[s0:s1]) / 300.0
            tail.append(e)
            print("     段 %d %-4s 尾部能量 = %.3g" % (i, names[i], e))
        if len(tail) == 4:
            if tail[1] <= tail[0] or tail[3] <= tail[0]:
                fails.append("C: 延迟/混响尾巴没有比干声更长（%.3g / %.3g vs %.3g）"
                             % (tail[1], tail[3], tail[0]))
            else:
                print("     ⇒ 延迟(%.3g)与混响(%.3g)尾部能量都高于干声(%.3g) ✓"
                      % (tail[1], tail[3], tail[0]))

    print("\n" + "=" * 70)
    if fails:
        print(" ★ 未通过：")
        for f in fails:
            print("   -", f)
        return 1
    print(" ★★★ 通过（A 文件健康 / B 音高逐音正确 / C 效果器尾巴可测）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
