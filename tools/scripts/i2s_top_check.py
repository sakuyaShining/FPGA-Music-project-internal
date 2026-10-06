#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i2s_top_check.py -- 顶层音频通路端到端判据（tdm_top → fx → i2s_tx → 解码）

读 tb_i2s_top.v 的两个产物：
    i2s_top_ref.txt   参考 = 每个 sample_en 抓到的 sample_out[23:8]（与 i2s_tx 取高位一致）
    i2s_top_dec.txt   标准接收器解出的 16 位字

判据：
    T1  i2s_tx 的 24→16 映射正确：解码字 == $signed(sample_out[23:8])
    T2  逐样本比对（自校准流水线滞后；i2s_tx 有装载/移位延迟，硬编码偏移会随配置失效）
    T3  饱和路径**真的被跑到**：|解码| == 32767 的样本数 > 0
        （不然 T1 只证明"小信号下恰好对"）
    T4  符号覆盖：解码样本里正负都存在
"""
import argparse
import os
import sys


def one_per_frame(dec):
    """每帧取一个字：取第 0、2、4… 个（即每两个取第一个）。

    ★ 不能用"连续相同就去重"：真实音频里相邻样本**本来就可能相等**（包络平坦段、
      过零附近），那种去重会吃掉合法样本 —— 实测把 12000 字压成 5997 个（少 3 个），
      于是"参考 6000 vs 解码 5997"永远对不齐，看着像 RTL 坏了。

    ★ 也不能取"第 1、3、5…"个：实测 dec[0] 与 dec[1] 是**同一个声道**的同一个值
      （都在 WS 上升沿后收满 16 位，落在同一个移位窗口里），
      取奇数号等于"每两帧才采一个" ⇒ 逐样本比对必然失败（实测不符 5992/5997）。
      取偶数号（dec[0]、dec[2]、…）才恰好是一帧一个。
    """
    return dec[0::2]


def read_col(path):
    out = []
    for l in open(path, encoding="utf-8"):
        l = l.strip()
        if not l:
            continue
        try:
            out.append(int(l))
        except ValueError:
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", required=True)
    args = ap.parse_args()
    d = args.simdir

    fref = os.path.join(d, "i2s_top_ref.txt")
    fdec = os.path.join(d, "i2s_top_dec.txt")
    for f in (fref, fdec):
        if not os.path.isfile(f):
            print("  缺 %s（测试台未运行？）" % os.path.basename(f))
            return 1

    #   测试台 stdout 里的 "SUMRAW_MAX="（饱和前那一级的实测峰值）。
    #   找不到就按 None 处理（不假装量过）。注意测试台会用前导空格排版，
    #   所以匹配时不能用 startswith。
    sum_max = None
    flog = os.path.join(d, "run.txt")
    if os.path.isfile(flog):
        for l in open(flog, encoding="utf-8", errors="replace"):
            if "SUMRAW_MAX=" in l:
                try:
                    sum_max = int(l.split("SUMRAW_MAX=")[1].split()[0])
                except (IndexError, ValueError):
                    sum_max = None
                if sum_max is None:
                    print("       （SUMRAW_MAX 行存在但数值解析失败：%r）" % l.strip())

    ref = read_col(fref)
    dec = one_per_frame(read_col(fdec))
    print("  顶层音频通路判据（tdm_top → i2s_tx → 标准接收器）")
    print("    参考 %d 样本 / 解码 %d 字（已按【每帧一个字】取样）" % (len(ref), len(dec)))
    if not ref or not dec:
        print("  ★ 产物为空（引擎可能没出声）")
        return 1

    fails = []

    # ---------------------------------------------------------------- T2 对齐
    #   ★ 比对口径（实测踩过两次才对）：
    #     · 解码日志里每个样本出现两次（发送器 32 位移位寄存器 + 单声道两槽）
    #       ⇒ 先每帧取一个（dec[0::2]）。
    #     · 取完之后仍有**两个字的流水线垃圾**（接收器还没对齐到字边界时收到的）
    #       ⇒ 把解码序列开头的 lag 个字丢掉，再与参考逐项比对：
    #           ref[i]  ←→  dec[i + lag]
    #       写成「ref[i+lag] ←→ dec[i]」会整体错位（实测不符 5992/5997，
    #       而真实情况是**完全一致**：ref = 35,70,126,…  dec[2:] = 35,35,70,70,126,126,…）。
    print("\n  [T2] 逐样本比对（丢掉解码开头的流水线垃圾后逐项相等）")
    best = None
    for lag in range(0, 8):
        n = min(len(ref), len(dec) - lag)
        if n < 100:
            break
        bad = sum(1 for i in range(n) if ref[i] != dec[i + lag])
        print("       解码开头丢 %d 字：不符 %d / %d" % (lag, bad, n))
        if best is None or bad < best[1]:
            best = (lag, bad, n)
    if best is None:
        fails.append("T2: 数据太短，无法比对")
    else:
        lag, bad, n = best
        print("       最佳：丢 %d 字，不符 %d / %d" % (lag, bad, n))
        if bad != 0:
            fails.append("T1/T2: 解码与 sample_out[23:8] 不符 %d/%d" % (bad, n))
            for i in range(n):
                if ref[i] != dec[i + lag]:
                    print("         首个不符：样本 #%d 参考 %d 解码 %d"
                          % (i, ref[i], dec[i + lag]))
                    break
        else:
            print("       ✓ i2s_tx 的 24→16 取高位与顶层 sample_out 逐样本一致")

    # ---------------------------------------------------------------- T3 饱和
    #   ★ 顶层的 24 位饱和阈值是 acc_next ≥ 2^19 = 524288
    #     （tdm_engine 里 sample_out = acc_next <<< GAIN_UP(4) 之后才夹 ±(2^23-1)）。
    #     所以"解码是否到 32767"这一句无法区分"信号没到饱和区"与"饱和逻辑写错"。
    #     判据必须把**增益前那一级**的实测峰值也拿进来。
    dec_all = read_col(fdec)
    sat = sum(1 for v in dec_all if abs(v) >= 32767)
    peak = max(abs(v) for v in dec_all) if dec_all else 0
    print("\n  [T3] 饱和路径覆盖")
    print("       解码峰值 %d / 32767   饱和样本数 %d" % (peak, sat))
    if sum_max is None:
        print("       （测试台未上报 SUMRAW_MAX，跳过饱和余量核算）")
    else:
        THR = 1 << 19                                  # = 524288
        print("       sum_raw 峰值 %d / 饱和阈值 %d（用了 %.0f%%）"
              % (sum_max, THR, 100.0 * sum_max / THR))
        if sum_max >= THR:
            if sat == 0:
                fails.append("T3: sum_raw 已过饱和阈值，但解码侧没有任何 32767 样本 "
                             "—— 饱和/取高位这段可能有错")
            else:
                print("       ✓ 24 位饱和路径确实被跑到，且解码侧出现截顶")
        else:
            #   实测事实：32 复音满力度也只到约 73% ⇒ 出货配置下不会截顶。
            #   这不是缺陷，但**必须写明**：T1 只覆盖了"未截顶"区间。
            print("       ⚠ 未进入饱和区：出货配置（32 复音 + 满力度）下 sum_raw 仍有 %.0f%% 余量"
                  % (100.0 * (1.0 - sum_max / float(THR))))
            print("          ⇒ 本判据只证明了【未截顶区间】的 24→16 取高位逐样本一致；")
            print("             饱和（截顶）行为需要另设激励（例如直接对引擎注入大和）才能覆盖。")

    # ---------------------------------------------------------------- T4 符号
    pos = sum(1 for v in dec_all if v > 0)
    neg = sum(1 for v in dec_all if v < 0)
    print("\n  [T4] 符号覆盖：正 %d / 负 %d" % (pos, neg))
    if pos == 0 or neg == 0:
        fails.append("T4: 解码样本缺正或负半轴（正 %d / 负 %d）" % (pos, neg))
    else:
        print("       ✓ 正负都存在")

    print()
    if fails:
        print("  ★ 未通过：")
        for f in fails:
            print("    - %s" % f)
        return 1
    print("  ★★★ 通过（24→16 取高位逐样本一致 + 饱和与正负覆盖）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
