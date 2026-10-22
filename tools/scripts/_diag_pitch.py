# -*- coding: utf-8 -*-
"""诊断 audio_check.py 的 B 段（音高识别 6/7）：把每一拍的
   ① 期望音（曲谱）② HPS 判定 ③ 可靠方法(FFT 峰值+抛物线插值) 三者并列，
   看差异是"八度错"、"判到邻音"、还是"判据窗口/相位问题"。
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, "tools/scripts")
import audio_check as ac

FS = ac.FS


def fft_peak_note(x):
    """可靠方法：FFT 峰值 + 抛物线插值（show_check.py 里实测 ±2 音分 ✓）"""
    if len(x) < 4096:
        return None, None
    seg = np.array(x[:16384], dtype=float)
    seg = seg - seg.mean()
    w = np.hanning(len(seg))
    sp = np.abs(np.fft.rfft(seg * w))
    k = int(np.argmax(sp[1:]) + 1)
    a, b, c = sp[k - 1], sp[k], sp[k + 1]
    d = 0.5 * (a - c) / (a - 2 * b + c + 1e-12) if (a - 2 * b + c) else 0.0
    f = (k + d) * FS / len(seg)
    return f, 69 + 12 * math.log2(f / 440.0)


def main():
    d = "sim_build/audio"
    p = os.path.join(d, "audio_proto.txt")
    if not os.path.exists(p):
        print("缺 %s" % p); return 1
    x = ac.load_dump(p)
    print("dump 样本数 = %d" % len(x))

    # 复刻 audio_check 的取窗方式：每拍取"中段 16384 点"
    # （具体拍长/位置从脚本里抄：见 audio_check.main 的 B 段）
    import re
    src = open("tools/scripts/audio_check.py", encoding="utf-8").read()
    print("  B 段取窗代码：")
    for m in re.finditer(r"^.*(s0|s1|bpm|beat|16384|notes).*$", src, re.M):
        t = m.group(0).strip()
        if t.startswith("#") or "=" in t:
            print("    " + t[:96])
    return 0


if __name__ == "__main__":
    sys.exit(main())
