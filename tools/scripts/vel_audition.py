#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vel_audition.py —— 力度-亮度 的【一键试听 + 证据落盘】

【为什么要有这条命令】
    "力度调音"必须靠耳朵定（31 号文档 D-04：曲线形状只能听出来）。
   但在这次之前，试听是**手工跑仿真 + 手工转 wav**：换一次 vel_wtab.hex
   就得重来一遍，而且产物散在 sim_build/velaudio/ 里、没有任何记录说明
   它是哪一版表跑出来的 —— 也就是说"我听过、听着还行"这句话不可复核。

   本脚本把整条链收成一条命令：
      编译 → 跑仿真 → 导出 4 个 wav → 算谱心对照 → 落盘报告

【它产出什么】
   <outdir>/L_flat.txt … H_shape.txt   原始样本（n 值）
   <outdir>/*.wav                      44.1 kHz 与仿真采样率两版（可丢进任何播放器）
   <outdir>/audition_report.txt        谱心/能量对照 + 结论（人可读，可贴进报告）
   <outdir>/out.txt                    仿真原始日志（含采样率自检）

【为什么四个用例是"同响度开/关"而不是"轻 vs 重"】
   直接比"轻"和"重"，重的那条只是更响（v14 比 v4 响约 7 倍），
   听不出音色差别。所以：
       L_flat  (v=4 , 0x6E=0)   轻、功能关   ← 基准
       L_shape (v=4 , 0x6E=1)   轻、功能开   ← 与上一行【同响度】，只差音色
       H_flat  (v=14, 0x6E=0)   重、功能关
       H_shape (v=14, 0x6E=1)   重、功能开
   这样"听不听得出差别"就是纯粹的**音色**差别。

用法：
   python tools/scripts/vel_audition.py                 # 用仓库里的表
   python tools/scripts/vel_audition.py --table D:\\tmp\\my_vel.hex   # 试一版新表
   python tools/scripts/vel_audition.py --nsamp 60000 --open          # 加长并直接播放
"""
import argparse
import os
import shutil
import struct
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
IV = r"D:\iverilog\bin"
SYNTH = os.path.join(ROOT, "src", "gowin", "tdm_synth")
TB = os.path.join(ROOT, "src", "sim", "tb_vel_audio.v")

#   运行期依赖表（缺一个就会让 $readmemh 失败 → 音频全 X → 试听文件是静音）
NEED_HEX = ("sine256.hex", "note_inc.hex", "preset_part.hex", "recip_inc.hex",
            "vel_wtab.hex", "tilt_wtab.hex")

RTL = ["tdm_top.v", "tdm_engine.v", "pitch_mod.v", "note_map.v", "vel_shape.v",
       "song_seq.v", "reg_bank.v", "uart_rx.v", "uart_tx.v", "audio_clk_en.v",
       "i2s_tx.v", "fx_delay.v", "osc_env.v", "pad_scan.v", "pad_pitch.v",
       "strip_ctrl.v", "led_ind.v"]

CASES = [("L_flat", 4, False), ("L_shape", 4, True),
         ("H_flat", 14, False), ("H_shape", 14, True)]


# ---------------------------------------------------------------- 读样本
def read_dump(path):
    v = []
    for line in open(path, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        try:
            v.append(float(line.split()[1]))
        except (ValueError, IndexError):
            pass
    return v


def write_wav(path, samples, rate):
    peak = max(1.0, max(abs(x) for x in samples))
    scale = (0.891 * 32767.0) / peak                # -1 dBFS
    data = bytearray()
    for x in samples:
        q = int(round(x * scale))
        q = -32768 if q < -32768 else (32767 if q > 32767 else q)
        data += struct.pack("<h", q)
    hdr = (b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
           + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
           + b"data" + struct.pack("<I", len(data)))
    with open(path, "wb") as fh:
        fh.write(hdr)
        fh.write(bytes(data))
    return path


def resample_linear(x, src, dst):
    if abs(src - dst) < 1e-9:
        return list(x)
    n = int(len(x) * dst / src)
    out = []
    for i in range(n):
        p = i * src / dst
        i0 = int(p)
        i1 = min(i0 + 1, len(x) - 1)
        fr = p - i0
        out.append(x[i0] * (1.0 - fr) + x[i1] * fr)
    return out


# ---------------------------------------------------------------- 频谱
def spectrum(x, fs):
    """返回 (freqs_Hz, mags)；无 numpy 时返回 (None, None)。

    两个曾写错、值得记住的点：
      · np.fft.rfftfreq(n, d) 的 d 是【采样间隔秒】。写成 1.0 得到的是
        "每样本周期数"（0..0.5），谱心会算出 0.0 Hz —— 看起来像"没声音"，
        其实只是横轴没换算。必须传 1.0/fs。
      · 去均值：直流分量往往远大于任何泛音，不去掉会把谱心整体拖向 0。
    """
    try:
        import numpy as np
    except ImportError:
        return None, None
    a = np.array(x, dtype=float)
    a = a - a.mean()
    w = np.hanning(len(a))
    S = np.abs(np.fft.rfft(a * w))
    return np.fft.rfftfreq(len(a), 1.0 / fs), S


def centroid_hz(freqs, mags):
    """谱心（Hz）：能量重心。这是"亮度"最常用的客观量。"""
    import numpy as np
    m = mags.copy()
    m[0] = 0.0
    den = m.sum()
    if den <= 0:
        return 0.0
    return float((freqs * m).sum() / den)


def fundamental_hz(freqs, mags, lo=80.0, hi=1200.0):
    """基频 = 低频段里的最大峰。用于把"高次占比"锚在真实基频上。"""
    import numpy as np
    m = mags.copy()
    m[0] = 0.0
    band = (freqs >= lo) & (freqs <= hi)
    if not band.any():
        return 0.0
    idx = np.argmax(np.where(band, m, 0.0))
    return float(freqs[idx])


def high_ratio(freqs, mags, f0, kmin=3):
    """k>=kmin 的泛音能量占总能量比例（0..1）——**本脚本的主亮度指标**。

    ★ 为什么不用谱心当主指标（2026-10-06 实测踩到）：
      谱心是"全谱的能量重心"。本功能在低力度时会**砍掉高次泛音**（条数机制），
      高次一没，重心就被拉回低处 —— 于是出现"听起来更亮、谱心却更低"的矛盾：
        v=14  功能关：峰 264/791/1301/2092/3146/4184 Hz，谱心 1666 Hz
        v=14  功能开：峰 264/791/1301/2092/3146 Hz（4184 被砍），谱心 1601 Hz
      但**逐峰比较是变亮的**（791 Hz 那根 0.650→0.710，1301 Hz 0.402→0.475）。
      也就是：谱心对"砍掉高次"这件事的方向判断是反的。
      能量占比（高次能量 / 总能量）没有这个问题，且与听感一致。

    下限用 kmin-0.5 个基频（而不是某个固定 Hz），保证换音高时判据含义不变。
    """
    import numpy as np
    if f0 <= 0:
        return 0.0
    m = mags.copy()
    m[0] = 0.0
    tot = m.sum()
    if tot <= 0:
        return 0.0
    band = (freqs >= f0 * (kmin - 0.5)) & (freqs <= f0 * 30.0)
    return float(m[band].sum() / tot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", default=os.path.join(ROOT, "sim_build", "velaudio"))
    ap.add_argument("--table", default=None, help="替换 vel_wtab.hex（试新表用）")
    ap.add_argument("--nsamp", type=int, default=20000, help="每个用例采集的样本数")
    ap.add_argument("--open", action="store_true", help="跑完自动播放 44.1k 版")
    args = ap.parse_args()

    d = os.path.abspath(args.outdir)
    os.makedirs(d, exist_ok=True)

    # ---- 数据文件：缺表必须在编译前就报出来（否则音频全 X，白跑一轮）
    missing = [h for h in NEED_HEX if not os.path.isfile(os.path.join(SYNTH, h))]
    if missing and not (args.table and "vel_wtab.hex" in missing):
        print("★ 缺运行期数据表：%s" % ", ".join(missing))
        print("  源目录 = %s" % SYNTH)
        return 1
    for h in NEED_HEX:
        p = os.path.join(SYNTH, h)
        if os.path.isfile(p):
            shutil.copy(p, d)
    if args.table:
        if not os.path.isfile(args.table):
            print("★ --table 指定的文件不存在：%s" % args.table)
            return 1
        shutil.copy(args.table, os.path.join(d, "vel_wtab.hex"))
        print("使用替换表：%s" % args.table)

    # ---- 编译
    srcs = [os.path.join(ROOT, "src", "rtl", f) for f in RTL] + [TB]
    cmd = [os.path.join(IV, "iverilog.exe"), "-g2005", "-DSIM_INIT",
           "-o", "va.vvp", "-s", "tb_vel_audio",
           "-P", "tb_vel_audio.NSAMP=%d" % args.nsamp] + srcs
    p = subprocess.run(cmd, cwd=d, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if p.returncode != 0:
        print("★ 编译失败：\n%s" % p.stdout.decode("utf-8", "replace"))
        return 1

    # ---- 运行
    print("跑仿真（%d 样本 × 4 用例）……" % args.nsamp)
    p = subprocess.run([os.path.join(IV, "vvp.exe"), "va.vvp"], cwd=d,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = p.stdout.decode("utf-8", "replace")
    open(os.path.join(d, "out.txt"), "w", encoding="utf-8").write(log)
    if p.returncode != 0:
        print("★ 仿真失败（rc=%d）：\n%s" % (p.returncode, log[-2000:]))
        return 1

    # ---- 采样率：从日志里的自检行读，读不到就用顶层参数推算
    import re
    fs = None
    m = re.search(r"sample_en 周期\s*≈?\s*(\d+)\s*ns", log)
    if m and int(m.group(1)) > 0:
        fs = 2.0e9 / (int(m.group(1)) / 2.0) if False else None
    #   日志行格式见 tb_vel_audio：打印的是"3 个样本的间隔"与"每样本 ns"
    m = re.search(r"每样本约\s*(\d+)\s*ns", log)
    if m and int(m.group(1)) > 0:
        fs = 1.0e9 / int(m.group(1))
    if fs is None:
        fs = 52734.375          # 兜底：27 MHz / (18×32) 之外的仿真配置（见 tb 注释）
        print("（日志里没有采样率自检行，按默认 %.1f Hz 处理）" % fs)
    else:
        print("仿真采样率 = %.1f Hz" % fs)

    # ---- 逐用例：读样本 → wav → 频谱
    print()
    print("=" * 72)
    print(" 用例              RMS      峰值    谱心(Hz)   高次占比")
    print("=" * 72)
    rows = {}
    for name, vel, on in CASES:
        txt = os.path.join(d, name + ".txt")
        if not os.path.isfile(txt):
            print("  ★ 缺 %s.txt" % name)
            return 1
        x = read_dump(txt)
        nz = sum(1 for v in x if v != 0)
        if nz < len(x) * 0.2:
            print("  ★ %s 非零样本只有 %.1f%% —— 很可能是【表没装进去】导致的全 X/静音"
                  % (name, 100.0 * nz / max(1, len(x))))
            return 1
        #   ★ 响度归一后再比谱心：wav 写盘时是按峰值归一的（-1 dBFS），
        #     也就是说"听的人实际听到的是归一化之后的版本"。若直接拿原始 RMS
        #     比，会把"力度该有的响度差"混进"音色差"里，结论就说不清了。
        rms = (sum(v * v for v in x) / max(1, len(x))) ** 0.5
        pk = max(abs(v) for v in x) if x else 0
        write_wav(os.path.join(d, name + "_%.0f.wav" % fs), x, int(round(fs)))
        write_wav(os.path.join(d, name + "_44100.wav"), resample_linear(x, fs, 44100.0), 44100)
        fr, mg = spectrum(x, fs)
        if fr is not None and len(x) >= 512:
            f0 = fundamental_hz(fr, mg)
            cen = centroid_hz(fr, mg)
            hr = high_ratio(fr, mg, f0)
        else:
            f0 = cen = hr = 0.0
        rows[name] = dict(rms=rms, peak=pk, cen=cen, f0=f0, hr=hr,
                          vel=vel, on=on, nsamp=len(x))
        print("  %-14s %9.0f %8.0f %9.1f %10.1f%%   (v=%d, 功能%s)"
              % (name, rms, pk, f0, 100 * hr, vel, "开" if on else "关"))

    # ---- 对照结论
    rep = []
    rep.append("力度-亮度 试听报告")
    rep.append("  生成时间：%s" % __import__("time").strftime("%Y-%m-%d %H:%M:%S"))
    rep.append("  仿真采样率：%.1f Hz      每用例样本数：%d" % (fs, args.nsamp))
    rep.append("  权重表：%s" % (args.table or os.path.join(SYNTH, "vel_wtab.hex")))
    rep.append("")
    rep.append("  %-10s %8s %9s %10s %10s" % ("用例", "RMS", "基频Hz", "高次占比", "谱心Hz"))
    for name, _, _ in CASES:
        r = rows[name]
        rep.append("  %-10s %8.0f %9.1f %9.1f%% %10.1f"
                   % (name, r["rms"], r["f0"], 100 * r["hr"], r["cen"]))
    rep.append("")
    ok = True

    def line(txt):
        rep.append(txt)
        print(txt)

    lo, ls = rows["L_flat"], rows["L_shape"]
    ho, hs = rows["H_flat"], rows["H_shape"]

    #   主比较量 = 高次能量占比（听感一致、且单调）；谱心列为旁证（会与前者矛盾，见
    #   high_ratio 的说明）。wav 是按峰值归一的，听的人听到的就是那一版，
    #   所以占比本来就不受响度影响，不需要额外归一。
    line("  [A] 同一力度：功能关 vs 功能开（只差音色）")
    ratio_a = {}
    for lname, hname, v in (("L_flat", "L_shape", 4), ("H_flat", "H_shape", 14)):
        if rows[lname]["hr"] > 0:
            ratio_a[v] = rows[hname]["hr"] / rows[lname]["hr"]
            line("      v=%-2d 高次占比 %.1f%% → %.1f%%（%.2f 倍）  谱心 %.0f → %.0f Hz"
                 % (v, 100 * rows[lname]["hr"], 100 * rows[hname]["hr"], ratio_a[v],
                    rows[lname]["cen"], rows[hname]["cen"]))
    if 4 in ratio_a:
        if ratio_a[4] >= 1.0:
            line("      ⚠ v=4 开启后高次没有减少：本表的恒等点在 v=8，轻力度应当更暗")
        else:
            line("      ✓ v=4 开启后变暗（轻力度更暗 = 表的中轴语义正确）")
    if 14 in ratio_a:
        if ratio_a[14] > 1.0:
            line("      ✓ v=14 开启后变亮（重力度更亮 = 方向正确）")
        else:
            line("      ✗ v=14 开启后没有变亮 —— 检查 0x6E 是否真的写进去了")
            ok = False

    line("  [B] 力度 -> 亮度（同一功能状态下）")
    if ls["hr"] > 0:
        ratio = hs["hr"] / ls["hr"]
        line("      功能开：高次占比 轻(v=4) %.1f%% → 重(v=14) %.1f%%（%.2f 倍）"
             % (100 * ls["hr"], 100 * hs["hr"], ratio))
        if ratio < 1.15:
            line("      ✗ 功能开时力度带来的亮度差不足 1.15 倍 —— 表或预设谱需要调")
            ok = False
        else:
            line("      ✓ 力度确实改变音色（不只是音量）")
    if lo["hr"] > 0:
        ratiof = ho["hr"] / lo["hr"]
        line("      功能关：高次占比 轻 %.1f%% → 重 %.1f%%（%.2f 倍）← 应≈1.00"
             % (100 * lo["hr"], 100 * ho["hr"], ratiof))
        if ratiof < 0.97 or ratiof > 1.03:
            line("      ✗ 功能关时力度就改变了音色 —— 说明关不干净")
            ok = False

    if "v=14 开启后没有变亮" in "\n".join(rep):
        ok = False

    line("  [C] 响度差（应有差别，这是力度该做的事）")
    line("      RMS：轻 %.0f → 重 %.0f（%.1f 倍）" % (ls["rms"], hs["rms"],
                                                hs["rms"] / max(1.0, ls["rms"])))
    line("  [D] 旁证：谱心（会与高次占比矛盾，原因见脚本内 high_ratio 说明）")
    line("      功能开：%.0f → %.0f Hz" % (ls["cen"], hs["cen"]))
    rep.append("")
    rep.append("  【怎么用这份报告】")
    rep.append("    ① 先听 L_flat vs L_shape：这两条同响度，差别就是'音色'。")
    rep.append("       听着像'变亮/更亮'⇒ 方向对；像'变响'或'变尖刺'⇒ 改表。")
    rep.append("    ② 再听 H_shape：重力度应该明显更'亮'，而不是只是更响。")
    rep.append("    ③ 改 tools/scripts/gen_vel_wtab.py 重新生成表，重跑本脚本对比数字。")
    rep.append("    ④ 数字只作旁证：最终由 31 号文档 D-04 说的'耳朵'拍板。")
    rep.append("")
    rep.append("  => %s" % ("证据链完整 ✓" if ok else "★ 有项目未通过，见上面 ✗ 行"))

    rp = os.path.join(d, "audition_report.txt")
    open(rp, "w", encoding="utf-8").write("\n".join(rep) + "\n")
    print()
    print("报告：%s" % rp)
    print("wav ：%s/*.wav（44.1 kHz 与仿真率两版）" % d)

    if args.open:
        wav = os.path.join(d, "L_shape_44100.wav")
        if os.path.isfile(wav):
            os.startfile(wav)                 # noqa: 只在 Windows 上被调用
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
