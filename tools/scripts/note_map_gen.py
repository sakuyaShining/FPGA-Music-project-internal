# -*- coding: utf-8 -*-
"""
note_map_gen.py —— 音符映射的表生成与验证

【它在整条链里的位置】
   上位机/演奏控制  →  note_map.v  →  tdm_engine 的 load_* 通路  →  I2S
                        ↑ 本脚本生成它要用的两张表

【两张表】
  1) note_inc.hex   128 项 MIDI 音符号 → 24 位相位增量
                     inc = f * 2^24 / fs,  f = 440 * 2^((n-69)/12)
                     用 ROM 而不是现场算：精确、无近似、只占 3 Kbit
  2) preset_part.hex  每个音色 P 个泛音的 (ratio_q8, amp, epar)
                     ratio_q8 = round(ratio * 256)，于是
                     inc_partial = (inc_note * ratio_q8) >> 8
                     谐波用整数比（256/512/768…）时是精确的

【为什么泛音比要走乘法而不是查表】
   泛音比是【每个音色一份】、音符是【每次演奏一个】——
   两者的乘积无法预先查表（128 音 × 16 泛音 × 4 音色 = 8192 项）。
   所以用一个共享乘法器在装载时算，一个音符只需 P 次。
"""
import argparse
import math
import os
import sys

FS_DEFAULT = 2500000.0 / 64.0
# ★ fs 必须与顶层实际采样率一致：note_inc 里的数字直接含 fs。
#   本默认值给 tb_note_map / tb_note_music（5 MHz 时钟，128 拍/样本）。
#   给 tdm_top（27 MHz / 18 / 32 = 46875 Hz）与综合工程用的那份，
#   必须用 --fs 46875 生成，否则上板所有音符高 3.16 个半音。
FS = FS_DEFAULT          # 39062.5 Hz，与 tb_tdm_demo 同一时间基准

# ---------------------------------------------------------------------------
# 音色预设：每个泛音给 (频率比, 幅度, d_k, 衰减终点 s_lvl)
#   ★ 与 tdm_demo.py 的 PRESETS 保持一致（同一套音色，两种用法）
# ---------------------------------------------------------------------------
PRESETS = {
    # 拉杆风琴：谐波、几乎不衰减、保持 —— 对照组，频谱静止
    "org": [
        (1, 200, 20, 30000), (2, 0, 20, 30000), (3, 140, 20, 30000), (4, 0, 20, 30000),
        (5, 90, 20, 30000), (6, 0, 20, 30000), (7, 0, 20, 30000), (8, 70, 20, 30000),
        (9, 0, 20, 30000), (10, 0, 20, 30000), (11, 0, 20, 30000), (12, 50, 20, 30000),
        (13, 0, 20, 30000), (14, 0, 20, 30000), (15, 0, 20, 30000), (16, 40, 20, 30000),
    ],
    # 钢琴：谐波、幅度 1/k、高次泛音衰减更快
    "piano": [
        (1, 220, 17, 12000), (2, 140, 16, 8000), (3, 100, 15, 5000), (4, 80, 15, 4000),
        (5, 60, 14, 2500), (6, 50, 14, 2000), (7, 40, 13, 1500), (8, 35, 13, 1200),
        (9, 30, 12, 900), (10, 25, 12, 700), (11, 22, 12, 600), (12, 20, 11, 500),
        (13, 18, 11, 400), (14, 16, 11, 350), (15, 14, 10, 300), (16, 12, 10, 250),
    ],
    # 钟：非谐泛音（真实钟体模态）+ 快速衰减到静音
    "bell": [
        (1.00, 220, 15, 0), (2.76, 170, 14, 0), (5.40, 140, 13, 0), (8.93, 110, 12, 0),
        (13.34, 90, 11, 0), (18.64, 70, 10, 0), (24.00, 55, 10, 0), (30.00, 45, 9, 0),
        (36.00, 35, 9, 0), (43.00, 28, 8, 0), (50.00, 22, 8, 0), (58.00, 18, 7, 0),
        (66.00, 14, 7, 0), (75.00, 11, 7, 0), (84.00, 9, 6, 0), (94.00, 7, 6, 0),
    ],
    # 马林巴：1:4 特征非谐 + 很快衰减到静音
    "marimba": [
        (1.0, 220, 13, 0), (4.0, 150, 12, 0), (9.2, 70, 11, 0), (16.0, 40, 10, 0),
        (24.0, 25, 10, 0), (34.0, 16, 9, 0), (45.0, 10, 9, 0), (58.0, 7, 8, 0),
        (72.0, 5, 8, 0), (88.0, 3, 8, 0), (105.0, 2, 7, 0), (124.0, 2, 7, 0),
        (144.0, 1, 7, 0), (166.0, 1, 6, 0), (190.0, 1, 6, 0), (215.0, 1, 6, 0),
    ],
}
ORDER = ["org", "piano", "bell", "marimba"]
P = 16          # 每个音符的泛音数（= 每组的时隙数）


def inc_of(freq):
    """频率 -> 24 位相位增量（四舍五入）"""
    return int(round(freq * (1 << 24) / FS)) & 0xFFFFFF


def gen(outdir):
    os.makedirs(outdir, exist_ok=True)

    # ---- 表 1：128 个 MIDI 音符号 ----
    lines = []
    for n in range(128):
        f = 440.0 * (2.0 ** ((n - 69) / 12.0))
        v = inc_of(f)
        # 高于 Nyquist/2 的音会回绕，ROM 里如实写出来（上层不应弹到那里）
        lines.append("%06X" % v)
    with open(os.path.join(outdir, "note_inc.hex"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("写出 note_inc.hex：128 项")
    for n in (60, 62, 64, 67, 69, 72):
        f = 440.0 * (2.0 ** ((n - 69) / 12.0))
        print("    MIDI %3d  %8.2f Hz  inc=%7d" % (n, f, inc_of(f)))

    # ---- 表 1b：滑音用的倒数表 recip[n] = round(2^32 / inc[n]) ----
    #   用途：note_map 在 note_on 时算滑音初值 gq0 = (inc_old-inc_new)/inc_new。
    #   把除法换成"乘倒数表"，就不需要除法器（19 位足够：最低音 inc≈9842
    #   → 2^32/9842 ≈ 436400 < 2^19）。
    lines = []
    for n in range(128):
        f = 440.0 * (2.0 ** ((n - 69) / 12.0))
        inc = inc_of(f)
        r = int(round((1 << 32) / inc)) if inc else 0
        r = min(r, (1 << 19) - 1)          # 限幅（超范围音本就不该弹）
        lines.append("%05X" % r)
    with open(os.path.join(outdir, "recip_inc.hex"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("写出 recip_inc.hex：128 项（滑音初值用，替代除法器）")
    for n in (60, 69, 84):
        f = 440.0 * (2.0 ** ((n - 69) / 12.0))
        inc = inc_of(f)
        print("    MIDI %3d  inc=%7d  recip=%6d" % (n, inc, int(round((1 << 32) / inc))))

    # ---- 表 2：每个音色 P 个泛音的 (ratio_q8, amp, epar) ----
    lines = []
    for name in ORDER:
        parts = PRESETS[name]
        for k in range(P):
            if k < len(parts):
                ratio, amp, dk, slvl = parts[k]
            else:
                ratio, amp, dk, slvl = 0.0, 0, 20, 0
            rq8 = int(round(ratio * 256.0)) & 0xFFFF
            dk = max(0, min(31, dk))
            slvl = max(0, min(32767, slvl))
            epar = ((slvl & 0xFFFF) << 7) | (3 << 5) | (dk & 0x1F)
            # ★ 位域必须互不重叠：ratio_q8 16 + amp 8 + epar 24 = 【48】位
            #   曾写成 (rq8<<24)|(amp<<16)|epar —— amp 占 [23:16] 与 epar[23:0] 重叠，
            #   实测第一行读回 ratio_q8=0x0100FA（应为 0x0100），整表报废。
            #   与 preset.hex 那次是同一个错误，所以这里也写明。
            word = ((rq8 & 0xFFFF) << 32) | ((amp & 0xFF) << 24) | (epar & 0xFFFFFF)
            lines.append("%012X" % word)
    with open(os.path.join(outdir, "preset_part.hex"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("写出 preset_part.hex：%d 项（%d 音色 × %d 泛音）"
          % (len(lines), len(ORDER), P))
    print("    行序：音色 0 的 16 个泛音、音色 1 的 16 个……")
    print("    位域：{ratio_q8[15:0], amp[7:0], epar[23:0]} = 40 位")


def verify(args):
    """对仿真输出做频谱验证：每个音符的基频是否落在 12-TET 期望值上"""
    import numpy as np
    y = []
    for l in open(args.dump, encoding="utf-8"):
        if not l.strip():
            continue
        try:
            y.append(float(l.split()[1]))
        except ValueError:
            pass
    y = np.array(y)
    print("读入 %d 个样本（%.2f s @ %.1f Hz）" % (len(y), len(y) / FS, FS))

    win = int(FS * 0.25)
    seg = y[len(y) // 2: len(y) // 2 + win]
    if len(seg) < win:
        seg = y[:win]
    S = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
    f = np.fft.rfftfreq(len(seg), 1.0 / FS)
    S[0] = 0
    thr = S.max() * 0.08
    pk = [f[i] for i in range(1, len(S) - 1)
          if S[i] > thr and S[i] >= S[i - 1] and S[i] > S[i + 1]]
    # 合并相邻格（同一个峰的裙边）
    merged = []
    for x in pk:
        if merged and x - merged[-1] < 60:
            continue
        merged.append(x)
    print("检出谱峰 %d 个：" % len(merged))
    for x in merged:
        midi = 69 + 12 * math.log2(x / 440.0) if x > 0 else 0
        print("    %8.1f Hz   (MIDI %6.2f)" % (x, midi))
    if args.expect:
        exp = [float(v) for v in args.expect.split(",")]
        print("期望基频：", ["%.1f" % e for e in exp])
        for e in exp:
            hit = [x for x in merged if abs(x - e) < max(15.0, e * 0.02)]
            print("    %8.1f Hz  ->  %s" % (e, "命中" if hit else "★ 未命中"))


def main():
    global FS
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "verify"])
    ap.add_argument("--outdir", default="sim_build/notemap")
    ap.add_argument("--dump", default="sim_build/notemap/note_out.txt")
    ap.add_argument("--expect", default="")
    # ★ 默认 39062.5（仿真时间基准）；给 tdm_top / 综合工程必须传 46875
    ap.add_argument("--fs", type=float, default=FS_DEFAULT,
                    help="采样率（默认 39062.5；tdm_top 用 46875）")
    a = ap.parse_args()
    FS = a.fs
    if a.cmd == "gen":
        print("采样率 fs = %.4f Hz" % FS)
        gen(a.outdir)
    else:
        verify(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
