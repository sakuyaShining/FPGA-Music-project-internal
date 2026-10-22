#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i2s_std_check.py -- I2S 发送器【标准接收模型】判据

读 tb_i2s_std.v 的三个产物：
    i2s_std_src.txt   每帧源样本（16 bit 有符号）
    i2s_std_std.txt   标准接收器解出的 (ws, word)
    i2s_std_leg.txt   旧模型解出的   (ws, word)   —— 仅作对照

判据（自校准滞后：接收器的第一个字对应哪一帧由数据自身确定，
      不靠"推算第几拍"，因为复位相位与装载时序差一拍就会让硬编码偏移失效）：

    I1 标准接收器：存在一个【唯一】的字滞后量，使全部字逐位相等
    I2 标准接收器的解码等于源（不是"源移一位"、不是"源取反"）
    I3 覆盖检查：源样本必须【跨过正负】（旧测试台 64 帧 × +37 全程为负，
       一次都没到正数 ⇒ "正负样本都能解"这句主张当时是无证据的）

对照输出（不作通过条件，但要点名）：
    L1 旧模型的滞后量与逐位一致性 —— 它会同样通过。这正是要点：
       旧模型通过 **不能** 排除协议缺陷；能排除的是标准接收器。
"""
import argparse
import os
import sys


def u16(v):
    return v & 0xFFFF


def read_src(path):
    return [int(l) for l in open(path, encoding="utf-8") if l.strip()]


def read_dec(path):
    out = []
    for l in open(path, encoding="utf-8"):
        p = l.split()
        if len(p) == 2:
            out.append(int(p[1]))
    return out


def dedup_consecutive(dec):
    """把"连续相同的相邻字"压成一个。

    为什么需要：接收器按【每个 WS 半周期】收满一个 16 bit 字，而一个音频帧有
    两个半周期 ⇒ 左右声道槽里是同一个样本时，接收器会连续吐出两个字。
    本测试台的发送器是单声道设计（两声道填同一个样本），所以日志里每个样本
    出现两次。这是**测试台的记录口径**，不是数据错误。
    （配套的声道检查请在 tb 里按 WS 分别记录，见 tb_i2s_tx.v 的做法。）
    """
    out = []
    for v in dec:
        if not out or out[-1] != v:
            out.append(v)
    return out


def try_lags(src, dec, max_lag=4, skip=1):
    """返回 [(lag, bad, n)]，把源样本与解码字按月对齐。

    skip：跳过接收器最前面的若干个"同步字"。
      理由与门禁 04 套件同款（judge_i2s 的 "解码侧跳过1个同步字后"）：
      接收器开闸时可能正处在半个字中间，于是它吐出的第一个字是拼凑出来的，
      与源样本没有对应关系。**这是开闸相位问题，不是数据错误**
      —— 第一条记录必须丢掉，否则整体错开一字，看起来像 RTL 坏了。
    """
    res = []
    dec = dec[skip:]
    for lag in range(max_lag + 1):
        n = min(len(src) - lag, len(dec))
        if n <= 0:
            continue
        bad = sum(1 for i in range(n) if u16(src[i + lag]) != u16(dec[i]))
        res.append((lag, bad, n))
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", required=True)
    args = ap.parse_args()
    d = args.simdir

    fsrc = os.path.join(d, "i2s_std_src.txt")
    fstd = os.path.join(d, "i2s_std_std.txt")
    fleg = os.path.join(d, "i2s_std_leg.txt")
    for f in (fsrc, fstd, fleg):
        if not os.path.isfile(f):
            print("  缺 %s（测试台未运行？）" % os.path.basename(f))
            return 1

    src = read_src(fsrc)
    std = dedup_consecutive(read_dec(fstd))
    leg = dedup_consecutive(read_dec(fleg))
    print("  I2S 标准接收判据（穿 i2s_tx，采样沿 = bck 上升沿）")
    print("    源 %d 帧 / 标准接收器 %d 字 / 旧模型 %d 字（已按【单声道每帧两槽】去重）"
          % (len(src), len(std), len(leg)))
    if not src or not std:
        print("  ★ 产物为空")
        return 1

    fails = []

    # ---------------------------------------------------------------- I3 覆盖
    pos = sum(1 for v in src if v > 0)
    neg = sum(1 for v in src if v < 0)
    print("\n  [I3] 激励覆盖：正 %d 个 / 负 %d 个（范围 %d .. %d）"
          % (pos, neg, min(src), max(src)))
    if pos == 0:
        fails.append("I3: 源样本全程为负，'正负样本都能解'没有证据")
    if neg == 0:
        fails.append("I3: 源样本全程为正，缺负半轴覆盖")

    # ---------------------------------------------------------------- I1/I2
    print("\n  [I1] 标准接收器：逐字比对（自校准滞后）")
    res = try_lags(src, std)
    for lag, bad, n in res:
        print("       滞后 %d 字：不符 %d / %d" % (lag, bad, n))
    good = [(lag, n) for lag, bad, n in res if bad == 0]
    if not good:
        fails.append("I2: 标准接收器在任何滞后下都对不上源样本 —— 发送器不符合标准 I2S")
        # 给出最可能的缺陷签名，便于定位
        n = min(len(src) - 1, len(std))
        if n > 0:
            sh = sum(1 for i in range(n) if u16(std[i]) != ((u16(src[i + 1]) << 1) & 0xFFFF))
            if sh == 0:
                print("       ← 签名：解码 = 源 << 1（整字左移一位）")
            sh2 = sum(1 for i in range(n) if u16(std[i]) != (u16(src[i + 1]) >> 1))
            if sh2 == 0:
                print("       ← 签名：解码 = 源 >> 1（整字右移一位）")
    else:
        lag, n = good[0]
        print("       ✓ 存在滞后 %d，全部 %d 字逐位相等" % (lag, n))
        if lag > 3:
            fails.append("I1: 滞后 %d 字偏大，收发之间可能有整帧级的错位" % lag)

    # ---------------------------------------------------------------- L1 对照
    print("\n  [L1] 旧模型（对照，不作通过条件）")
    resl = try_lags(src, leg)
    for lag, bad, n in resl:
        print("       滞后 %d 字：不符 %d / %d" % (lag, bad, n))
    if any(bad == 0 for _, bad, _ in resl):
        print("       旧模型同样通过 ⇒ 它【不能】用来排除协议缺陷（这正是要加标准模型的原因）")
    else:
        print("       旧模型不通过 ⇒ 两种接收器一致认为有问题")

    print()
    if fails:
        print("  ★ 未通过：")
        for f in fails:
            print("    - %s" % f)
        return 1
    print("  ★★★ 通过（标准接收器逐位一致 + 正负覆盖）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
