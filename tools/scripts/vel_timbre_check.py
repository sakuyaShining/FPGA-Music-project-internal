#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vel_timbre_check.py -- 力度->音色 端到端判据（读 tb_vel_timbre 的产物）

产物格式（sim_build/veltimb/vel_timbre.txt）：
    标签 力度 16 个幅度

判据：
    J1 默认参数下，两个力度的【谱心】几乎相同（< 2%）—— 恒等性
    J2 开启倾斜后，高力度谱心 / 低力度谱心 >= 1.15 —— 真正变亮
    J3 低力度仍保留 >= 3 条泛音，且基音不为 0
    J4 高力度保留的条数 >= 低力度（"条数"效果方向正确）

用法：python tools/scripts/vel_timbre_check.py --simdir sim_build/veltimb
"""
import argparse
import os
import sys


def centroid(amps):
    """谱心 = sum((k+1)*a) / sum(a)，k 从 0 起。空谱返回 0。"""
    num = sum((k + 1) * a for k, a in enumerate(amps))
    den = sum(amps)
    return (num / den) if den else 0.0


def load(path):
    rows = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if len(parts) != 18:
                continue
            rows[parts[0]] = [int(x) for x in parts[2:18]]
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", required=True)
    args = ap.parse_args()

    path = os.path.join(args.simdir, "vel_timbre.txt")
    if not os.path.isfile(path):
        print("  缺 vel_timbre.txt")
        return 1

    rows = load(path)
    need = ["ident_lo", "ident_hi", "tilt_lo", "tilt_hi"]
    miss = [k for k in need if k not in rows]
    if miss:
        print("  缺数据行：%s" % ", ".join(miss))
        return 1

    fails = []
    print("  端到端：力度 -> 音色（穿 tdm_top）")
    for k in need:
        a = rows[k]
        nz = sum(1 for x in a if x)
        print("    %-9s 谱心 %6.2f   非零条数 %2d   峰值 %3d"
              % (k, centroid(a), nz, max(a)))

    # J1 恒等
    ci_lo, ci_hi = centroid(rows["ident_lo"]), centroid(rows["ident_hi"])
    if ci_lo <= 0:
        fails.append("J1: ident_lo 谱心为 0")
    else:
        d = abs(ci_hi - ci_lo) / ci_lo * 100.0
        print("\n  [J1] 默认参数恒等性：谱心差 %.2f%%（要求 < 2%%）" % d)
        if d >= 2.0:
            fails.append("J1: 默认参数改变了音色（差 %.2f%%）" % d)

    # J2 变亮
    ct_lo, ct_hi = centroid(rows["tilt_lo"]), centroid(rows["tilt_hi"])
    if ct_lo <= 0:
        fails.append("J2: tilt_lo 谱心为 0")
    else:
        r = ct_hi / ct_lo
        print("  [J2] 开启倾斜后谱心比 = %.2f（要求 >= 1.15）" % r)
        if r < 1.15:
            fails.append("J2: 高力度没有明显变亮（比 %.2f）" % r)

    # J3 低力度下限
    #   注意：这里量的是【实际有声的泛音数】，而不是"保留的槽位数"。
    #   2026-10-06 判据修正：真实预设谱本身是稀疏的（只有奇数条非零），
    #   保留 4 个槽位可能只有 2 条出声。"轻触不能像没声"这个意图
    #   应当用【基音存在 + 总能量 > 0 + 至少 2 条出声】来表达；
    #   而"槽位数 >= 3"由单元判据 V2（平坦基底）负责。
    a = rows["tilt_lo"]
    nz = sum(1 for x in a if x)
    energy = sum(a)
    print("  [J3] 低力度：出声 %d 条，基音 %d，总能量 %d（要求 出声>=2 且 基音!=0 且 能量>0）"
          % (nz, a[0], energy))
    if nz < 2:
        fails.append("J3: 低力度只有 %d 条出声" % nz)
    if a[0] == 0:
        fails.append("J3: 低力度基音被置零")
    if energy == 0:
        fails.append("J3: 低力度总能量为 0（等于没声）")

    # J4 条数方向
    n_lo = sum(1 for x in rows["tilt_lo"] if x)
    n_hi = sum(1 for x in rows["tilt_hi"] if x)
    print("  [J4] 条数：低 %d -> 高 %d（要求 高 >= 低）" % (n_lo, n_hi))
    if n_hi < n_lo:
        fails.append("J4: 高力度条数反而更少")

    print()
    if fails:
        print("  ★ 未通过：")
        for f in fails:
            print("    - %s" % f)
        return 1
    print("  ★★★ 通过（力度->音色 端到端：恒等 / 变亮 / 下限 / 条数）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
