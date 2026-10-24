#!/usr/bin/env python3
"""check_audio_rate.py —— 采样率定稿的静态守门人

为什么需要这个工具
==================
`audio_clk_en` 的采样率由两个参数相乘决定：

    采样率 = 27 MHz ÷ DIV_BCK ÷ BCK_PER_LRCK

而 `tdm_engine` 的时隙数 `NSLOT` 必须【恰好等于】每样本的时钟拍数
`DIV_BCK × BCK_PER_LRCK`。两者一旦不等，引擎按 NSLOT 拍跑一圈、
I2S 却按另一个拍数收帧 —— 这就是 2026-09-30 那个"整体低一个八度"
bug 的同族问题：**参数漂移不会报错，只会让音高/帧率悄悄错掉。**

2026-10-25 定稿：
    · 产品配置（tdm_top / tdm_top_owned / tdm_top_rh）= 16 × 32 = 512 拍
      → 27e6 / 512 = **52734.375 Hz**
    · 旧配置（osc_additive_top）= 18 × 32 = 576 拍 → 46875 Hz（保留，不能悄悄坏）
    · 48 kHz 需要 PLL 或换晶振，本项目设计纪律"不用 PLL"，故不采用。

本工具查三件事
==============
  1. 每个 `audio_clk_en #(...)` 例化的 DIV_BCK / BCK_PER_LRCK 能否解析
  2. 产品顶层必须是 16/32（= 52734.375 Hz），旧顶层必须是 18/32
  3. 声明了 `NSLOT` 的顶层必须满足 NSLOT == DIV_BCK × BCK_PER_LRCK

动态判据在 `sim/tb_audio_clk_en.v`（12 项，含对齐契约）；本工具守的是
"产品里到底传了什么参数"—— 仿真查不到这一层，因为仿真自己传参。

用法
====
    python tools/check_audio_rate.py
    python tools/check_audio_rate.py --strict    # 有问题返回非零
"""
import argparse
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
SRC = R / 'engine/src'
CLK_HZ = 27_000_000.0

# 定稿值：产品顶层必须命中这些 (DIV_BCK, BCK_PER_LRCK)
EXPECT = {
    'tdm_top.v':         (16, 32),
    'tdm_top_owned.v':   (16, 32),
    'tdm_top_rh.v':      (16, 32),
    'osc_additive_top.v': (18, 32),   # 旧链路，保留原速率
}

INST = re.compile(
    r"audio_clk_en\s*#\s*\(\s*\.DIV_BCK\s*\(\s*(\d+)\s*\)\s*,"
    r"\s*\.BCK_PER_LRCK\s*\(\s*(\d+)\s*\)\s*\)")
NSLOT = re.compile(r"localparam\s+(?:integer\s+)?NSLOT\s*=\s*(\d+)\s*;")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()

    files = sorted(SRC.glob('*.v'))
    if not files:
        print(f'找不到源码：{SRC}')
        return 2

    bad = []
    rows = []

    for f in files:
        text = f.read_text(encoding='utf-8', errors='replace')
        ms = INST.findall(text)
        if not ms:
            continue
        if len(ms) > 1:
            print(f'[WARN] {f.name} 有 {len(ms)} 处 audio_clk_en 例化，只按第一处判定')
        divb, bpl = int(ms[0][0]), int(ms[0][1])
        period = divb * bpl
        rate = CLK_HZ / period

        nsl = NSLOT.search(text)
        nslot = int(nsl.group(1)) if nsl else None

        exp = EXPECT.get(f.name)
        mark = ''
        if exp is not None:
            if (divb, bpl) != exp:
                mark = 'EXPECT-MISMATCH'
                bad.append(f'{f.name}: 参数 {divb}/{bpl}，定稿是 {exp[0]}/{exp[1]}')
        if nslot is not None and nslot != period:
            mark = (mark + '+NSLOT-MISMATCH') if mark else 'NSLOT-MISMATCH'
            bad.append(f'{f.name}: NSLOT={nslot} 但每样本 {period} 拍 '
                       f'（差 {nslot - period:+d} 拍 ⇒ 引擎与 I2S 帧不同步）')

        rows.append((f.name, divb, bpl, period, rate, nslot, mark))

    print('audio_clk_en 例化清单（27 MHz ÷ DIV_BCK ÷ BCK_PER_LRCK）')
    print('-' * 84)
    print(f'{"文件":<22}{"DIV":>5}{"BPL":>6}{"拍/样本":>9}{"采样率 Hz":>14}{"NSLOT":>7}  判定')
    print('-' * 84)
    for name, divb, bpl, period, rate, nslot, mark in rows:
        ns = str(nslot) if nslot is not None else '-'
        print(f'{name:<22}{divb:>5}{bpl:>6}{period:>9}{rate:>14.3f}{ns:>7}  '
              f'{mark if mark else "OK"}')
    print('-' * 84)

    prod = [r for r in rows if r[0] in EXPECT and r[0] != 'osc_additive_top.v']
    if prod:
        rates = {round(r[4], 3) for r in prod}
        print(f'\n产品采样率：{", ".join(f"{x:.3f}" for x in sorted(rates))} Hz'
              f'（{len(prod)} 个顶层）')
        if len(rates) > 1:
            bad.append('产品顶层之间采样率不一致：' + ', '.join(f'{x:.3f}' for x in rates))
            print('  [FAIL] 三个产品顶层必须同速率，否则同一份 bitstream 换顶层就变调')
        else:
            print('  [OK]   三个产品顶层同速率（换顶层不会变调）')

    miss = [n for n in EXPECT if not any(r[0] == n for r in rows)]
    if miss:
        print(f'\n[WARN] 定稿表里的文件没找到 audio_clk_en 例化：{", ".join(miss)}'
              f'（文件被改名/删除？请同步更新本工具的 EXPECT）')

    print()
    if bad:
        print('发现 %d 个问题：' % len(bad))
        for b in bad:
            print('  · ' + b)
        print('\n结论: FAIL' if args.strict else '\n结论: 有问题，见上')
        return 1 if args.strict else 0
    print('结论: PASS —— 产品 52734.375 Hz，旧链路 46875 Hz，NSLOT 与拍数全部对齐')
    return 0


if __name__ == '__main__':
    sys.exit(main())
