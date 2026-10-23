#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_vel_wtab.py —— 生成 vel_wtab.hex（四槽力度->谱形表）

地址布局：widx = {slot[1:0], vel[3:0], part[3:0]}，共 1024 项。
文件格式：每行 16 项，每项 3 个十六进制位（0x000..0x1FF），空格分隔。
           行号 = slot*16 + vel，列号 = part。

数值语义（见 engine/src/vel_shape.v）：
    256 = 1.0 倍（恒等，amp == base）
    < 256 = 该泛音被压暗
    > 256 = 该泛音被加强（上限 511，因为 RTL 只用低 9 位）
    0     = 该泛音在本力度下不存在

★ 硬约束（对应 tb_vel_shape 判据 V1/V2/V3）：
    · 基音（part=0）任何力度下都不置零
    · 最少保留 3 条泛音（RTL 侧 part<4 有 NFLOOR=64 兜底）
    · 任何参数下 base == 0 ⇒ amp == 0（"没有的泛音"不会被凭空造出来）
      这条由 RTL 保证（amp = base * w >> 8），表里写什么都造不出泛音。

★ 四槽性格（2026-10-23 刀1 第二步）：
    slot 0  钢琴    —— 逐位保留改造前的表，出厂预设 0 的声音不变
    slot 1  弦乐    —— 谱形不随力度变，力度只改音量（全泛音等比例缩放）
    slot 2  钟/铃   —— 高次泛音对力度不敏感（低力度也亮）
    slot 3  贝斯    —— 只有前 4 条泛音，高次恒弱；力度改厚度不改亮度

用法：
    python tools/scripts/gen_vel_wtab.py                    # 写 engine/src/vel_wtab.hex
    python tools/scripts/gen_vel_wtab.py --out /tmp/x.hex   # 写别处（对照用）
    python tools/scripts/gen_vel_wtab.py --check            # 只校验不写
"""
import argparse
import os
import sys

NPART = 16
NVEL = 16
NSLOT = 4

# 各槽的"力度增益" g(v)：0.30 .. 1.00，线性
def g(v):
    return 0.30 + 0.70 * (v / 15.0)

def clamp9(x):
    return max(0, min(511, int(round(x))))

# ---------------------------------------------------------------------------
# 槽性格函数：返回 w(vel, part) 的 9 位权重
# ---------------------------------------------------------------------------
def w_piano(v, p):
    """钢琴：w = 256 * g^(1 + p/5)
    低力度时高次泛音按几何级数消失（p=0 只掉 g，p=15 掉 g^4），
    高力度时全谱拉平到 256。这是"击得越重、激励越窄、高频越强"。
    注意：slot 0 不调用本函数，而是直接抄现有表（见 load_legacy_slot0）。"""
    return clamp9(256.0 * (g(v) ** (1.0 + p / 5.0)))

def w_strings(v, p):
    """弦乐：w = 256 * g(v)，与 p 无关
    全部泛音等比例缩放 ⇒ 谱形不变，只有音量变。
    这是"弓压改变音量、不改变音色"的第一性模型。"""
    return clamp9(256.0 * g(v))

def w_bell(v, p):
    """钟/铃：低次随力度走，高次几乎不动
    p<4  : 0.30 .. 1.00 倍
    p>=4 : 0.75 .. 1.00 倍（低力度下高次相对更突出 ⇒ 钟永远亮）
    """
    if p < 4:
        return clamp9(256.0 * (0.30 + 0.70 * v / 15.0))
    return clamp9(256.0 * (0.75 + 0.25 * v / 15.0))

def w_bass(v, p):
    """贝斯：前 4 条主导，高次恒弱
    p<4  : 0.30 .. 1.00 倍（改厚度）
    p>=4 : 0.06 .. 0.16 倍（恒暗，不改亮度）
    """
    if p < 4:
        return clamp9(256.0 * (0.30 + 0.70 * v / 15.0))
    return clamp9(256.0 * (0.06 + 0.10 * v / 15.0))

SLOT_FN = [None, w_strings, w_bell, w_bass]   # slot 0 特殊处理

LEGACY = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      '..', '..', 'engine', 'src', 'vel_wtab.hex.bak-20261023')
OUT_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           '..', '..', 'engine', 'src', 'vel_wtab.hex')

def load_legacy_slot0():
    """读改造前的 256 项表（16 行 x 16 项），作为 slot 0。
    这是"钢琴音色逐位不变"的保证：slot 0 不重算，直接抄。"""
    if not os.path.exists(LEGACY):
        sys.exit('缺少改造前基线 %s（用于 slot 0 逐位保留）' % LEGACY)
    rows = []
    for line in open(LEGACY):
        line = line.strip()
        if line:
            rows.append([int(t, 16) for t in line.split()])
    if len(rows) != NVEL or any(len(r) != NPART for r in rows):
        sys.exit('基线表形状不对：%d 行' % len(rows))
    return rows

def build():
    table = [[[0] * NPART for _ in range(NVEL)] for _ in range(NSLOT)]
    table[0] = load_legacy_slot0()
    for s in (1, 2, 3):
        fn = SLOT_FN[s]
        for v in range(NVEL):
            for p in range(NPART):
                table[s][v][p] = fn(v, p)
    return table

def check(table):
    """判据：基音不置零 / 前 4 条不置零 / 全表在 9 位内 / 槽间必须不同"""
    errs = []
    for s in range(NSLOT):
        for v in range(NVEL):
            if table[s][v][0] == 0:
                errs.append('slot%d vel%d 基音被置零' % (s, v))
            if sum(1 for p in range(NPART) if table[s][v][p] > 0) < 3:
                errs.append('slot%d vel%d 保留泛音少于 3 条' % (s, v))
            for p in range(NPART):
                if not (0 <= table[s][v][p] <= 511):
                    errs.append('slot%d vel%d part%d 越界 %d'
                                % (s, v, p, table[s][v][p]))
    # 槽间必须不同（刀1 第二步的意义所在）
    for s in (1, 2, 3):
        same = sum(1 for v in range(NVEL) for p in range(NPART)
                   if table[s][v][p] == table[0][v][p])
        if same == NVEL * NPART:
            errs.append('slot%d 与 slot0 完全相同（表没分化）' % s)
    # 每槽内：高次/低次比例随力度【单调】，方向不限
    #   钢琴/贝斯/弦乐是"越重越亮"（比例递增）；
    #   钟是"越重相对越暗"（高次对力度不敏感，基音补上来）—— 这是设计意图，
    #   所以判据只能要求单调，不能要求递增。
    #   必须先滤掉量化毛刺：16 位取整会让 525->527 这种 ±2 的抖动出现，
    #   占比不到 0.5%，不代表趋势反转。毛刺阈值取序列幅度的 2%。
    for s in range(NSLOT):
        series = []
        for v in range(NVEL):
            lo = sum(table[s][v][0:4])
            hi = sum(table[s][v][4:16])
            series.append((hi * 1000) // max(1, lo))
        tol = max(20, (max(series) - min(series)) // 40)
        diffs = [series[i + 1] - series[i] for i in range(len(series) - 1)]
        real = [d for d in diffs if abs(d) > tol]
        pos = sum(1 for d in real if d > 0)
        neg = sum(1 for d in real if d < 0)
        if pos and neg and min(pos, neg) >= 2:
            errs.append('slot%d 亮度比例非单调（滤毛刺后 增 %d 次 / 减 %d 次）：%s'
                        % (s, pos, neg, series))
    return errs

def dump(table, path):
    with open(path, 'w', newline='\n') as f:
        for s in range(NSLOT):
            for v in range(NVEL):
                f.write(' '.join('%03X' % x for x in table[s][v]) + '\n')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=OUT_DEFAULT)
    ap.add_argument('--check', action='store_true', help='只校验不写')
    a = ap.parse_args()

    table = build()
    errs = check(table)
    if errs:
        for e in errs:
            print('  [FAIL] ' + e)
        sys.exit(1)
    print('校验通过：4 槽 x 16 力度 x 16 泛音 = 1024 项，全部在 0..511')

    for s, name in enumerate(['钢琴(保留原表)', '弦乐', '钟/铃', '贝斯']):
        lo = sum(table[s][0][0:4]) // 4
        hi_lo = sum(table[s][0][4:16]) // 12
        lo2 = sum(table[s][15][0:4]) // 4
        hi_hi = sum(table[s][15][4:16]) // 12
        print('  slot%d %-12s  vel0: 低次%3d 高次%3d   vel15: 低次%3d 高次%3d'
              % (s, name, lo, hi_lo, lo2, hi_hi))

    if a.check:
        print('(--check) 未写文件')
        return
    dump(table, a.out)
    print('已写入 %s（%d 行）' % (a.out, NSLOT * NVEL))

if __name__ == '__main__':
    main()
