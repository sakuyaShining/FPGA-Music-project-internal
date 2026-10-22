#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_tilt_wtab.py -- 生成【独立亮度轴】0x5C TILT 的权重表 tilt_wtab.hex

它和 vel_wtab.hex 是两件事，别混：

    vel_wtab.hex   力度 -> 谱形。  索引 = vel*16+part。**演奏中按下多重**决定。
    tilt_wtab.hex  亮度轴 -> 谱形。索引 = tilt 档。    **手在泛音排上滑到哪**决定。

为什么要有独立的表（而不是复用 vel_wtab）：
    规格里"亮度"是第 4 个独立表情维（32 号 D-13）。用户选的形状是
    「倾斜轴为主」：**基音退、高次进**，听起来是"变亮"，而不是"变响"。
    —— 逐条等比缩放会变成音量变化，那是被明确否决的做法（32 号 D-13 否决项）。

表结构：16 档（tilt 0..255 量化到 16 档，每档 16 个十六进制步进）
    每项 9 位，256 = 1.0 倍（恒等）
    w(t, k) = 256 + ((t - 7) * k * 896) // 105     k = 0..15（0 = 基音）
    896 = 256 * 3.5，105 = 7 * 15 → 使 t=15, k=15 时 w 正好 511（到顶不溢出）

三条性质（判据 T 系列要验的就是它们）：
    · w(7, k) == 256  ∀k   ⇒ 中点即【恒等】。写入 0x5C=0x70 不改变音色。
    · t=0 时基音被压到 0.5 倍 → 不是静音（"最暗"仍有音高，判据 T3）
    · 基音恒不为 0 ⇒ 亮度推到哪一档都不会把音"变没"
"""
import sys

NZERO = 7            # 中点档 = 恒等（对应寄存器值 0x70 = 112）
K_NUM = 896          # 斜率分子
K_DEN = 105          # 斜率分母（= 7 × 15）


def weight(t, k):
    w = 256 + ((t - NZERO) * k * K_NUM) // K_DEN
    return max(0, min(511, w))


def main():
    lines = []
    for t in range(16):
        row = [weight(t, k) for k in range(16)]
        lines.append(" ".join("%03X" % x for x in row))
    sys.stdout.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
