#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_vel_wtab.py -- 生成力度->谱形 的权重表 vel_wtab.hex

表结构：256 项 x 9 位（0..511）
    索引 = vel*16 + part          vel 0..15, part 0..15（0 = 基音）
    数值 = 该泛音的权重，256 = 1.0 倍（恒等）

设计说明（与《32-演奏表情问题总表》D-19/D-20 一致）：
  · 第一版由【现有公式】生成，保证换成查表后行为不变（判据可复用）
      w(v,k) = clamp(256 + tilt_n(v) * k, 0, 511)
      tilt_n(v) = clamp(bias + gain*v, -16, +16)
  · 条数机制（低力度少几条）由【把高次权重置 0】表达 —— 这正是表的优势：
      公式只能"压到门限"，表可以直接写 0。
  · 基音（k=0）权重恒不为 0：轻触也要有音高。
  · 之后要调"奇次优先/凹陷"等音色性格，直接改本文件重新生成即可。

用法：python tools/scripts/gen_vel_wtab.py > src/gowin/tdm_synth/vel_wtab.hex
"""
import sys

BIAS = -16          # 与 RTL 的钳位范围一致
GAIN = 2
TILT_CLAMP = 16

# 条数表：力度 -> 保留多少条（与 RTL 的 n_keep_of 一致，3 -> 16）
def n_keep(v):
    table = [3, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 15, 16]
    return table[v]


def tilt_n(v):
    t = BIAS + GAIN * v
    return max(-TILT_CLAMP, min(TILT_CLAMP, t))


def weight(v, k):
    if k >= n_keep(v) and k != 0:
        return 0                      # 条数机制：超出保留条数 => 直接置零
    w = 256 + tilt_n(v) * k
    return max(0, min(511, w))


def main():
    lines = []
    for v in range(16):
        row = [weight(v, k) for k in range(16)]
        lines.append(" ".join("%03X" % x for x in row))
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
