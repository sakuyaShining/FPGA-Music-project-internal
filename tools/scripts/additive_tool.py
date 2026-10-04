#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
additive_tool.py -- 加法合成引擎的「激励生成」与「输出分析」

用途：让整个设计可以【只靠仿真】完成验证 —— 不需要开发板、不需要任何外设。

  gen      : 生成正弦查找表 + 各泛音的频率增量/幅度  ->  .hex 文件（给 $readmemh 用）
  analyze  : 读取仿真 dump 出来的样本 -> 写成 .wav（可以听！）-> FFT -> 出报告

模型约定：
  采样率  fs = 50 000 Hz   （仿真里 1 个时钟 = 1 个样本，时钟周期 20 µs）
  相位位宽 PHASE_W = 24
  频率增量 inc = round(f * 2^PHASE_W / fs)
  正弦表   256 项，16 bit 有符号（Q1.15）
  幅度     8 bit 无符号（0..255），实际增益 = amp/256
"""
import argparse
import json
import os
import struct
import sys
import wave

import numpy as np

# ---------------------------------------------------------------- 模型常量
FS        = 50000          # Hz，与 testbench 里的时钟周期一一对应
PHASE_W   = 24
TAB_AW    = 8
TAB_N     = 1 << TAB_AW
NUM_PART  = 8
F0        = 220.0          # 基频 Hz
N_SAMPLES = 12000          # 每个测试的样本数（0.24 s）


def freq_to_inc(f_hz):
    """频率 -> 24 位相位增量"""
    return int(round(f_hz * (1 << PHASE_W) / FS))


# 两个测试用例：
#   A 谐波   : 220, 440, 660, 880, 1100, 1320, 1540, 1760   （f0 的 1..8 次谐波）
#   B 非谐波 : 把第 3 个泛音改成 2.76 倍（钟/锣类非谐比例），其余不动
RATIOS_HARM   = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
RATIOS_INHARM = [1.0, 2.0, 2.76, 4.0, 5.0, 6.0, 7.0, 8.0]
AMPS          = [200, 120, 80, 60, 45, 36, 30, 26]   # 1/n 左右的衰减，0..255


# ---------------------------------------------------------------- gen
def cmd_gen(outdir):
    os.makedirs(outdir, exist_ok=True)

    # --- 1) 正弦表：256 项，16 bit 有符号，二进制补码十六进制 ---
    idx = np.arange(TAB_N)
    val = np.round(32767.0 * np.sin(2 * np.pi * idx / TAB_N)).astype(np.int64)
    val = np.clip(val, -32768, 32767)
    with open(os.path.join(outdir, "sine256.hex"), "w") as f:
        for v in val:
            f.write("%04x\n" % (int(v) & 0xFFFF))

    # --- 2) 频率增量：16 行 = 前 8 行谐波，后 8 行非谐波 ---
    incs = [freq_to_inc(F0 * r) for r in RATIOS_HARM] + \
           [freq_to_inc(F0 * r) for r in RATIOS_INHARM]
    with open(os.path.join(outdir, "inc.hex"), "w") as f:
        for v in incs:
            f.write("%06x\n" % (v & 0xFFFFFF))

    # --- 3) 各泛音幅度：8 行，8 bit ---
    with open(os.path.join(outdir, "amp.hex"), "w") as f:
        for v in AMPS:
            f.write("%02x\n" % (v & 0xFF))

    meta = {
        "fs": FS, "phase_w": PHASE_W, "tab_n": TAB_N, "num_partials": NUM_PART,
        "f0": F0, "n_samples": N_SAMPLES,
        "ratios_harmonic": RATIOS_HARM,
        "ratios_inharmonic": RATIOS_INHARM,
        "amps": AMPS,
        "inc_harmonic": incs[:NUM_PART],
        "inc_inharmonic": incs[NUM_PART:],
        "freqs_harmonic":   [F0 * r for r in RATIOS_HARM],
        "freqs_inharmonic": [F0 * r for r in RATIOS_INHARM],
    }
    with open(os.path.join(outdir, "stimulus_meta.json"), "w") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print("[gen] 输出目录:", outdir)
    print("       sine256.hex  (%d 项)" % TAB_N)
    print("       inc.hex      (16 行: 8 谐波 + 8 非谐波)")
    print("       amp.hex      (%d 行)" % NUM_PART)
    print("       stimulus_meta.json")
    print("       谐波频率  :", ["%.0f" % x for x in meta["freqs_harmonic"]])
    print("       非谐波频率:", ["%.2f" % x for x in meta["freqs_inharmonic"]])


# ---------------------------------------------------------------- 分析工具
def read_samples(path):
    vals = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                vals.append(int(line))
            except ValueError:
                pass
    return np.array(vals, dtype=np.int64)


def write_wav(path, samples, fs):
    """把仿真样本写成 16 bit 单声道 WAV（自动归一化到 -0.9..0.9）"""
    x = samples.astype(np.float64)
    peak = np.max(np.abs(x)) if len(x) else 0.0
    if peak <= 0:
        peak = 1.0
    y = x / peak * 0.9
    pcm = np.clip(np.round(y * 32767.0), -32768, 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(round(fs)))
        w.writeframes(pcm.tobytes())


def find_peaks(spec_db, freqs, thresh_db=-60.0, min_sep_hz=25.0):
    """找显著谱峰，按频率排序，返回 [(freq, level_db), ...]"""
    peaks = []
    n = len(spec_db)
    for i in range(1, n - 1):
        if spec_db[i] > thresh_db and spec_db[i] >= spec_db[i-1] and spec_db[i] > spec_db[i+1]:
            peaks.append((freqs[i], spec_db[i]))
    # 抑制邻近的小峰
    peaks.sort(key=lambda p: -p[1])
    kept = []
    for f, lv in peaks:
        if all(abs(f - kf) >= min_sep_hz for kf, _ in kept):
            kept.append((f, lv))
    kept.sort(key=lambda p: p[0])
    return kept


def cmd_analyze(indir, outdir, meta_path):
    with open(meta_path) as f:
        meta = json.load(f)
    fs = meta["fs"]
    f0 = meta["f0"]

    os.makedirs(outdir, exist_ok=True)
    report = []
    report.append("# 加法合成引擎 —— 纯仿真验证报告\n")
    report.append("> 本报告**完全由仿真产生**，未使用任何开发板或外设。\n")
    report.append("## 模型参数\n")
    report.append("| 项 | 值 |")
    report.append("|---|---|")
    report.append("| 采样率 fs | %d Hz |" % fs)
    report.append("| 相位位宽 | %d bit |" % meta["phase_w"])
    report.append("| 正弦表 | %d 项 × 16 bit |" % meta["tab_n"])
    report.append("| 泛音数 | %d |" % meta["num_partials"])
    report.append("| 基频 f0 | %.0f Hz |" % f0)
    report.append("| 每测试样本数 | %d (%.3f s) |" % (meta["n_samples"], meta["n_samples"] / fs))
    report.append("")

    all_ok = True

    for tag, key_freqs in (("harmonic", meta["freqs_harmonic"]),
                           ("inharmonic", meta["freqs_inharmonic"])):
        src = os.path.join(indir, "samples_%s.txt" % tag)
        if not os.path.exists(src):
            report.append("## %s\n\n**样本文件缺失: %s**\n" % (tag, src))
            all_ok = False
            continue

        x = read_samples(src)
        n = len(x)

        # --- 写 WAV（可以听）---
        wav = os.path.join(outdir, "additive_%s.wav" % tag)
        write_wav(wav, x, fs)

        # --- FFT ---
        win = np.hanning(n)
        X = np.fft.rfft(x * win)
        freqs = np.fft.rfftfreq(n, d=1.0 / fs)
        mag = np.abs(X)
        # 归一化到峰值 0 dB（便于读数），并加窗补偿
        mag_db = 20 * np.log10(np.maximum(mag, 1e-12) / (np.max(mag) + 1e-12))
        peaks = find_peaks(mag_db, freqs, thresh_db=-45.0, min_sep_hz=25.0)

        report.append("## 测试 %s\n" % tag)
        report.append("样本数 %d，WAV 输出：`%s`\n" % (n, os.path.basename(wav)))
        report.append("### 期望的泛音频率\n")
        report.append("```")
        report.append("  ".join("%.1f" % f for f in key_freqs))
        report.append("```\n")
        report.append("### 实测谱峰（阈值 −45 dB）\n")
        report.append("| # | 实测频率 (Hz) | 相对电平 (dB) | 期望频率 (Hz) | 误差 (Hz) |")
        report.append("|---|---|---|---|---|")

        matched = 0
        for i, (f, lv) in enumerate(peaks):
            # 找最近的期望频率
            exp = min(key_freqs, key=lambda e: abs(e - f))
            err = f - exp
            ok = abs(err) < 5.0
            if ok:
                matched += 1
            report.append("| %d | %.2f | %.1f | %.1f | %+.2f %s |"
                          % (i + 1, f, lv, exp, err, "OK" if ok else "**偏差**"))

        report.append("")
        report.append("**匹配结果：%d / %d 个期望泛音被找到**\n" % (matched, len(key_freqs)))
        if matched < len(key_freqs):
            all_ok = False

        # 导出频谱 CSV
        csv = os.path.join(outdir, "spectrum_%s.csv" % tag)
        with open(csv, "w") as f:
            f.write("freq_hz,level_db\n")
            for fr, lv in zip(freqs, mag_db):
                if fr <= 4000:            # 只导出有意义的频段
                    f.write("%.3f,%.3f\n" % (fr, lv))

        # 关键指标
        thd_peaks = [p for p in peaks if p[0] > 10]
        report.append("### 关键观察\n")
        report.append("- 谱峰总数：**%d**" % len(peaks))
        if len(peaks) > 1:
            report.append("- 最低峰 %.1f Hz，最高峰 %.1f Hz" % (peaks[0][0], peaks[-1][0]))
        report.append("")

    # --- 独立性检验：两个测试的差异应该只在第 3 个泛音 ---
    report.append("## 独立性检验（核心）\n")
    report.append("对比 `harmonic` 与 `inharmonic` 两个测试：")
    report.append("只有**第 3 个泛音**的频率被改动（3.00× → 2.76×），其余 7 个完全不变。\n")
    report.append("| 泛音 # | 比例(谐波) | 比例(非谐波) | 期望频率(谐波) | 期望频率(非谐波) |")
    report.append("|---|---|---|---|---|")
    for i, (a, b) in enumerate(zip(meta["ratios_harmonic"], meta["ratios_inharmonic"])):
        mark = "  ← **只改这个**" if abs(a - b) > 1e-9 else ""
        report.append("| %d | %.2f | %.2f | %.1f | %.1f |%s"
                      % (i + 1, a, b, f0 * a, f0 * b, mark))
    report.append("")
    report.append("→ 如果两个测试的 FFT 中，除第 3 峰外其余峰位置**完全一致**，")
    report.append("  就证明了 **每个泛音拥有独立的相位累加器与频率控制**。\n")

    report.append("## 结论\n")
    report.append("**总体：%s**\n" % ("全部通过 ✅" if all_ok else "存在偏差 ⚠️"))

    rpt = os.path.join(outdir, "仿真验证报告.md")
    with open(rpt, "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    print("[analyze] 输入目录:", indir)
    print("          输出目录:", outdir)
    print("          报告:", rpt)
    print("          结论:", "全部通过" if all_ok else "存在偏差")
    return 0 if all_ok else 2


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gen")
    g.add_argument("--outdir", required=True)

    a = sub.add_parser("analyze")
    a.add_argument("--indir", required=True)
    a.add_argument("--outdir", required=True)
    a.add_argument("--meta", required=True)

    args = ap.parse_args()
    if args.cmd == "gen":
        cmd_gen(args.outdir)
        return 0
    else:
        return cmd_analyze(args.indir, args.outdir, args.meta)


if __name__ == "__main__":
    sys.exit(main())
