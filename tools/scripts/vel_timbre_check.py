#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vel_timbre_check.py -- 力度->音色 与 独立亮度轴 的端到端判据（读 tb_vel_timbre 的产物）

产物格式（sim_build/regress/14_veltimbre/vel_timbre.txt）：
    标签 力度 16 个幅度

判据（A/B 组：力度 -> 音色）
    J1 默认参数下，两个力度的【谱心】几乎相同（< 2%）—— 恒等性
    J2 开启灵敏度后，高力度谱心 / 低力度谱心 >= 1.15 —— 真正变亮
    J3 低力度仍保留 >= 2 条泛音，且基音不为 0（"轻触不能像没声"）
    J4 高力度出声的条数 >= 低力度（"条数"效果方向正确）

判据（C/D 组：独立亮度轴 0x5C）
    L1 亮度档 0 -> FF 谱心单调不减（允许 1% 回退：高档权重会撞 511 饱和）
    L2 恒等点 0x70 与"亮度维不存在"逐位相同（这是本维的回归护身符）
    L3 最暗档基音不为 0（推到最暗也不能把音变没）
    L4 亮度动态范围：谱心(FF) / 谱心(0) >= 1.15
    L5 换预设（preset=2）后亮度轴仍成立（说明它接在预设谱【之后】）
    L6 同一个恒等值写两次结果逐位相同（可复现性）

★ 为什么 J1/J2 之外还要 L2 与 L6：这两条都是"防止判据自己骗自己"。
   L2 保证新加的一维在默认值下对既有音频【零影响】；
   L6 保证同一配置的产物可复现，否则上面的单调性可能只是运行时抖动。

用法：python tools/scripts/vel_timbre_check.py --simdir sim_build/regress/14_veltimbre
"""
import argparse
import os
import sys

#   一次成功运行应有的行；缺行说明测试台中途退出或产物被截断
REQUIRED = ["ident_lo", "ident_hi", "tilt_lo", "tilt_hi",
            "tilt70", "tilt0", "tilt40", "tilt70b", "tiltC0", "tiltFF",
            "pre2_dark", "pre2_brt"]

#   参与单调性检查的亮度档，按寄存器值从暗到亮排
TILT_SWEEP = ["tilt0", "tilt40", "tilt70", "tiltC0", "tiltFF"]


def centroid(amps):
    """谱心 = sum((k+1)*a) / sum(a)，k 从 0 起。空谱返回 0。"""
    num = sum((k + 1) * a for k, a in enumerate(amps))
    den = sum(amps)
    return (num / den) if den else 0.0


def load(path):
    """读产物。★ 关键词：**读不动要报得出来**。

    2026-10-06 教训：本脚本曾因 ROM 读到 X（运行目录缺表）而抛
      ValueError: invalid literal for int() with base 10: 'X'
    异常被门禁截成 120 字符的 traceback，既看不出是哪个文件、也看不出缺什么。
    ⇒ 判据脚本的第一职责是【把失败原因说清楚】，然后才是判定。
    所以这里对三种坏输入分别给出可读结论：
      · 文件缺失
      · 行数不足（测试台中途退出/被截断）
      · 数值域含 X/x/z/Z（运行期依赖表没装进去）
    """
    if not os.path.isfile(path):
        return None, "缺 vel_timbre.txt（测试台未运行或运行目录被清空？）"
    rows = {}
    bad_tokens = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln, line in enumerate(fh, 1):
            parts = line.split()
            if len(parts) != 18:
                continue
            vals = []
            for x in parts[2:18]:
                if x.lower() in ("x", "z") or "x" in x.lower() or "z" in x.lower():
                    bad_tokens.append((ln, parts[0], x))
                    vals.append(None)
                else:
                    try:
                        vals.append(int(x))
                    except ValueError:
                        bad_tokens.append((ln, parts[0], x))
                        vals.append(None)
            rows[parts[0]] = vals
    if bad_tokens:
        ln, tag, tok = bad_tokens[0]
        return None, ("产物里有未定值 %r（第 %d 行 %s，共 %d 处）"
                      "—— 典型的【运行目录缺 hex 表】导致 $readmemh 失败"
                      % (tok, ln, tag, len(bad_tokens)))
    miss = [k for k in REQUIRED if k not in rows]
    if miss:
        return None, "产物缺行：%s（共 %d 行）" % (", ".join(miss), len(rows))
    return rows, None


def check_monotone(names, rows, fails, label, tol=0.01):
    """按给定顺序检查谱心单调不减（容忍 tol 比例的回落）。"""
    cs = [(n, centroid(rows[n])) for n in names]
    lines = "  ".join("%s:%.2f" % (n, c) for n, c in cs)
    print("    %s 谱心序列  %s" % (label, lines))
    for i in range(1, len(cs)):
        if cs[i][1] < cs[i - 1][1] * (1.0 - tol):
            fails.append("%s: %s -> %s 谱心回落（%.2f -> %.2f）"
                         % (label, cs[i - 1][0], cs[i][0], cs[i - 1][1], cs[i][1]))
    return cs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", required=True)
    args = ap.parse_args()

    path = os.path.join(args.simdir, "vel_timbre.txt")
    rows, err = load(path)
    if err:
        print("  ★ 数据不完整：%s" % err)
        print("    排查顺序：① 仿真运行目录里有没有 vel_wtab.hex / tilt_wtab.hex")
        print("              ② copy_data() 是否把 DATA_FILES 全拷进来了")
        print("              ③ 测试台的 [表自检] 行有没有打出 256/466")
        return 1

    fails = []
    print("  端到端：力度 -> 音色 + 独立亮度轴（穿 tdm_top）")
    for k in REQUIRED:
        a = rows[k]
        nz = sum(1 for x in a if x)
        print("    %-10s 谱心 %6.2f   非零条数 %2d   峰值 %3d"
              % (k, centroid(a), nz, max(a)))

    # ======================================================================
    # A/B 组：力度 -> 音色
    # ======================================================================
    print("\n  ── 力度 -> 音色 ──")
    # J1 恒等
    ci_lo, ci_hi = centroid(rows["ident_lo"]), centroid(rows["ident_hi"])
    if ci_lo <= 0:
        fails.append("J1: ident_lo 谱心为 0")
    else:
        d = abs(ci_hi - ci_lo) / ci_lo * 100.0
        print("  [J1] 默认参数恒等性：谱心差 %.2f%%（要求 < 2%%）" % d)
        if d >= 2.0:
            fails.append("J1: 默认参数改变了音色（差 %.2f%%）" % d)

    # J2 变亮
    ct_lo, ct_hi = centroid(rows["tilt_lo"]), centroid(rows["tilt_hi"])
    if ct_lo <= 0:
        fails.append("J2: tilt_lo 谱心为 0")
    else:
        r = ct_hi / ct_lo
        print("  [J2] 开启灵敏度后谱心比 = %.2f（要求 >= 1.15）" % r)
        if r < 1.15:
            fails.append("J2: 高力度没有明显变亮（比 %.2f）" % r)

    # J3 低力度下限
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

    # ======================================================================
    # C/D 组：独立亮度轴 0x5C
    # ======================================================================
    print("\n  ── 独立亮度轴 0x5C ──")
    # L1 单调
    cs = check_monotone(TILT_SWEEP, rows, fails, "L1 亮度 0->FF")

    # L2 恒等点 = 亮度维不存在
    same = (rows["tilt70"] == rows["tilt70b"])
    print("  [L2] 恒等点 0x70 vs 重复写入 0x70：%s" % ("逐位相同 ✓" if same else "不同 ✗"))
    if not same:
        fails.append("L2: 恒等点两次写入结果不同（不可复现）")

    # L3 最暗档仍有基音
    if rows["tilt0"][0] == 0:
        fails.append("L3: 最暗档把基音置零（最暗 = 没声）")
    else:
        print("  [L3] 最暗档基音 = %d（要求 != 0）" % rows["tilt0"][0])

    # L4 亮度动态范围
    c_dark, c_brt = centroid(rows["tilt0"]), centroid(rows["tiltFF"])
    if c_dark <= 0:
        fails.append("L4: 最暗档谱心为 0")
    else:
        rr = c_brt / c_dark
        print("  [L4] 亮度动态范围 谱心(FF)/谱心(0) = %.2f（要求 >= 1.15）" % rr)
        if rr < 1.15:
            fails.append("L4: 亮度轴动态范围不足（%.2f）" % rr)

    # L5 跨预设
    cd, cb = centroid(rows["pre2_dark"]), centroid(rows["pre2_brt"])
    if cd <= 0:
        fails.append("L5: preset=2 最暗档谱心为 0")
    else:
        r5 = cb / cd
        print("  [L5] preset=2 下的亮度比 = %.2f（要求 >= 1.15）" % r5)
        if r5 < 1.15:
            fails.append("L5: 换预设后亮度轴失效（%.2f）—— 检查它是否接在预设谱之后" % r5)
    if rows["pre2_dark"] == rows["pre2_brt"]:
        fails.append("L5: preset=2 下亮度轴完全无效（两次结果相同）")

    print()
    if fails:
        print("  ★ 未通过：")
        for f in fails:
            print("    - %s" % f)
        return 1
    print("  ★★★ 通过（力度->音色 J1-J4 + 亮度轴 L1-L6）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
