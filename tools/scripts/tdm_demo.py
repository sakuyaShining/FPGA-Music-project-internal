# -*- coding: utf-8 -*-
"""
tdm_demo.py —— TDM 引擎的"音色预设 → 仿真 → WAV + 频谱演化"工具

【它回答的问题】
   "每泛音独立包络"加上去之后，听起来到底有没有区别？

【两个子命令】
  gen      : 生成预设参数表 preset.hex（测试台 $readmemh 读它）
  render   : 把仿真的每样本输出转成 WAV，并打印"频谱随时间演化"的量化结果

【为什么预设定义放在 Python 而不是 Verilog】
   音色是"要反复调"的东西。放在 Python 里改一个数字就能重跑，
   不用碰 RTL，也不用重新综合。Verilog 那边只负责 $readmemh。

【时间基准】
   clk = 2.5 MHz，NSLOT = 64  ->  fs = 39062.5 Hz（真实音频率，可直接播放）
   inc = f * 2^24 / fs
"""
import argparse
import math
import os
import struct
import sys

FS = 2500000.0 / 64.0          # 39062.5 Hz
NOTE_C4 = 261.6256             # 中央 C

# ---------------------------------------------------------------------------
# 音色预设
#   每个泛音给四样东西：频率比 ratio、幅度 amp、指数衰减 d_k、衰减终点 s_lvl
#     τ ≈ 2^d_k / d_m 个样本   （d_m 固定取 3）
#     d_k 每减 1，衰减时间常数【减半】
#     s_lvl = 0 表示"衰减到静音"（钟、马林巴）；非 0 表示"衰减到某个电平后保持"（风琴）
#
#   ★ 频率比是这套东西真正的分量所在：
#     谐波（1,2,3,4...）   -> 风琴/钢琴/弦乐
#     非谐（1,2.76,5.4...） -> 钟、钟琴（金属感就来自这里）
# ---------------------------------------------------------------------------
PRESETS = {}

# --- 1) 拉杆风琴：谐波、全泛音几乎不衰减、衰减到高电平后一直保持 -------------
#     这是 Hammond(1935) 的做法，也是"只有每泛音音高+幅度"能做到的上限。
#     用它当【对照组】：它的频谱在时间上是【不动】的。
PRESETS["org"] = {
    "desc": "拉杆风琴：谐波、几乎不衰减、保持（对照组：频谱不随时间变）",
    "partials": [
        # (ratio, amp, d_k, s_lvl)
        (1,  200, 20, 30000), (2,   0, 20, 30000), (3,  140, 20, 30000), (4,   0, 20, 30000),
        (5,   90, 20, 30000), (6,   0, 20, 30000), (7,   0, 20, 30000), (8,  70, 20, 30000),
        (9,   0, 20, 30000), (10,  0, 20, 30000), (11,  0, 20, 30000), (12, 50, 20, 30000),
        (13,  0, 20, 30000), (14,  0, 20, 30000), (15,  0, 20, 30000), (16, 40, 20, 30000),
    ],
}

# --- 2) 钢琴：谐波、幅度按 1/k 递减、高次泛音衰减明显更快、衰减到中等电平 -----
PRESETS["piano"] = {
    "desc": "钢琴：谐波、幅度 1/k、高次泛音衰减更快（频谱随时间变暗）",
    "partials": [
        (1,  220, 17, 12000), (2,  140, 16,  8000), (3,  100, 15,  5000), (4,   80, 15,  4000),
        (5,   60, 14,  2500), (6,   50, 14,  2000), (7,   40, 13,  1500), (8,   35, 13,  1200),
        (9,   30, 12,   900), (10,  25, 12,   700), (11,  22, 12,   600), (12,  20, 11,   500),
        (13,  18, 11,   400), (14,  16, 11,   350), (15,  14, 10,   300), (16,  12, 10,   250),
    ],
}

# --- 3) 钟：非谐泛音（金属体的振动模式）、衰减快、衰减到静音 -------------------
#     频率比取自真实钟体的前几个模态：1, 2.76, 5.40, 8.93, 13.34, 18.64 ...
#     ★ 这一条【只有每泛音独立音高】才做得出来 —— 是全并行版也能做的部分；
#       但"高次泛音先死"必须靠每泛音独立衰减，那是 TDM 才做得出的部分。
PRESETS["bell"] = {
    "desc": "钟：非谐泛音 + 快速衰减到静音（撞击瞬间频谱很宽，随后高次逐层消失）",
    "partials": [
        (1.00, 220, 15, 0), (2.76, 170, 14, 0), (5.40, 140, 13, 0), (8.93, 110, 12, 0),
        (13.34, 90, 11, 0), (18.64, 70, 10, 0), (24.00, 55, 10, 0), (30.00, 45,  9, 0),
        (36.00, 35,  9, 0), (43.00, 28,  8, 0), (50.00, 22,  8, 0), (58.00, 18,  7, 0),
        (66.00, 14,  7, 0), (75.00, 11,  7, 0), (84.00,  9,  6, 0), (94.00,  7,  6, 0),
    ],
}

# --- 4) 马林巴：1:4 的强非谐（木条的特征）、衰减很快、衰减到静音 ---------------
PRESETS["marimba"] = {
    "desc": "马林巴：1:4 非谐 + 很快衰减到静音（木条的特征音）",
    "partials": [
        (1.0, 220, 13, 0), (4.0, 150, 12, 0), (9.2,  70, 11, 0), (16.0, 40, 10, 0),
        (24.0, 25, 10, 0), (34.0, 16,  9, 0), (45.0, 10,  9, 0), (58.0,  7,  8, 0),
        (72.0,  5,  8, 0), (88.0,  3,  8, 0), (105.0, 2,  7, 0), (124.0, 2,  7, 0),
        (144.0, 1,  7, 0), (166.0, 1,  6, 0), (190.0, 1,  6, 0), (215.0, 1,  6, 0),
    ],
}

ORDER = ["org", "piano", "bell", "marimba"]


def inc_of(freq):
    """频率 -> 24 位相位增量"""
    return int(round(freq * (1 << 24) / FS)) & 0xFFFFFF


def gen_hex(path):
    """生成 preset.hex：每行一个 48 位字，共 4 组 × 16 泛音 = 64 行

       位域： {inc[23:0], amp[7:0], epar[23:0]}   （12 个十六进制字符）

       epar = {s_lvl[15:0], d_m[1:0], d_k[4:0]}

       为什么一行一个 48 位字而不是三个字段：$readmemh 是"按空白切词"的，
       一行三列会被当成三行读进去。一行一个字最不容易出错。
    """
    lines = []
    for name in ORDER:
        for (ratio, amp, dk, slvl) in PRESETS[name]["partials"]:
            f = NOTE_C4 * ratio
            dk = max(0, min(31, dk))
            slvl = max(0, min(32767, slvl))
            epar = ((slvl & 0xFFFF) << 7) | (3 << 5) | (dk & 0x1F)
            # ★ 位域必须【互不重叠】：inc 24 + amp 8 + epar 24 = 56 位。
            #   曾经写成 (inc<<24)|(amp<<16)|epar —— amp 占 [23:16] 而 epar 占 [23:0]，
            #   两者重叠，幅度的高位漏进了 s_lvl。
            #   实测症状：epar_mem 读回 0x5C006F（应为 0x00006F），
            #             于是 s_lvl 变成 47104，包络早早停在 SUS，音色完全不变。
            word = ((inc_of(f) & 0xFFFFFF) << 32) | ((amp & 0xFF) << 24) | (epar & 0xFFFFFF)
            lines.append("%014X" % word)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("已写出 %s：%d 行（%d 个音色 × %d 个泛音）"
          % (path, len(lines), len(ORDER), len(PRESETS[ORDER[0]]["partials"])))
    for i, name in enumerate(ORDER):
        print("   组 %d : %-8s %s" % (i, name, PRESETS[name]["desc"]))


def write_wav(path, samples):
    """16 位单声道 WAV（重采样到 48000 Hz 标准速率）

    ★ 2026-10-02：仿真 fs=39062.5 Hz 是非标准速率，部分 Windows 音频栈
      （本机 Intel SST 只稳定支持 44100/48000）会【静默拒绝播放】——
      表现为"双击没声音"，与文件太短无关。此处用 FFT 域重采样到
      48000 Hz（39062.5 × 1.2288 = 48000，整除关系），保证任何设备可播。
      上变频无混叠风险（源 Nyquist 19.5 kHz < 目标 24 kHz）。
    """
    import wave as _wave
    import numpy as _np

    peak = max(1, max(abs(x) for x in samples))
    scale = (0.891 * 32767.0) / peak
    x = _np.array(samples, dtype=_np.float64) * scale

    DST = 48000
    n_out = int(round(len(x) * DST / FS))
    X = _np.fft.rfft(x)
    Y = _np.zeros(n_out // 2 + 1, dtype=complex)
    m = min(len(X), len(Y))
    Y[:m] = X[:m] * (n_out / len(x))
    y = _np.clip(_np.fft.irfft(Y, n_out), -32768, 32767).astype(_np.int16)

    with _wave.open(path, "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(DST)
        fh.writeframes(y.tobytes())
    print("  写出 %s  (%.2f s, 重采样 %d -> %d Hz)"
          % (path, len(y) / DST, int(round(FS)), DST))


def spectrum_bands(x, fs, nfft=4096):
    """返回 (频率轴, 幅度)"""
    import numpy as np
    w = np.hanning(len(x))
    S = np.abs(np.fft.rfft(x * w, n=nfft))
    return np.fft.rfftfreq(nfft, 1.0 / fs), S


def _load_dump(path):
    """读每样本输出。★ 第一拍往往是 X（流水线还没建立）——
       直接 int() 会崩，而崩掉会让人误以为"设计坏了"。显式跳过并说明。"""
    import numpy as np
    v, nskip = [], 0
    for l in open(path, encoding="utf-8"):
        if not l.strip():
            continue
        try:
            v.append(float(l.split()[1]))
        except ValueError:
            nskip += 1
    if nskip:
        print("  （%s 跳过 %d 个非数值样本 —— 流水线建立前的正常现象）"
              % (os.path.basename(path), nskip))
    return np.array(v)


def render(prefix, outdir):
    import numpy as np
    segs = []
    for i, name in enumerate(ORDER):
        p = "%s_%d.txt" % (prefix, i)
        if not os.path.exists(p):
            print("缺少 %s，先跑全部 4 次仿真" % p)
            return 1
        segs.append(_load_dump(p))

    os.makedirs(outdir, exist_ok=True)
    print()
    for name, seg in zip(ORDER, segs):
        write_wav(os.path.join(outdir, "tdm_%s.wav" % name), list(seg))

    print()
    print("=== 频谱随时间演化（'每泛音独立包络'到底改变了什么）===")
    print("   每段取 3 个时间窗做 FFT，统计【高频能量 / 总能量】的占比")
    print("   占比随时间下降 = 频谱在变暗 = 高次泛音先死")
    print()
    print("   %-8s %9s %9s %9s" % ("音色", "t=50ms", "t=250ms", "t=450ms"))
    for name, seg in zip(ORDER, segs):
        row = []
        # ★ 窗口必须落在段内：450ms(=17578) + 4096 = 21674 < 31250 样本（0.8 s）
        #   原来取 700ms(27343) + 4096 > 31250，越界 -> 长度不足 -> nan
        for t_ms in (50, 250, 450):
            a = int(t_ms / 1000.0 * FS)
            win = seg[a:a + 4096]
            if len(win) < 4096:
                row.append(float("nan"))
                continue
            f, S = spectrum_bands(win, FS)
            lo = S[(f >= 200) & (f < 1500)].sum()
            hi = S[(f >= 1500) & (f < 15000)].sum()
            row.append(hi / (lo + hi + 1e-9))
        print("   %-8s %8.1f%% %8.1f%% %8.1f%%"
              % (name, row[0] * 100, row[1] * 100, row[2] * 100))
    print()
    print("   风琴那一行应基本不变（频谱静止）；钟 / 马林巴应明显下降。")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "render"])
    ap.add_argument("--out", default="sim_build/demo/preset.hex")
    # ★ render 读 4 个文件 <prefix>_0.txt .. <prefix>_3.txt
    #   （测试台一次只放一个音色：分四次跑，每次都是干净的起音，比较才有意义）
    ap.add_argument("--prefix", default="sim_build/demo/demo_out")
    ap.add_argument("--outdir", default="sim_build/demo")
    a = ap.parse_args()
    if a.cmd == "gen":
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
        gen_hex(a.out)
    else:
        return render(a.prefix, a.outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
