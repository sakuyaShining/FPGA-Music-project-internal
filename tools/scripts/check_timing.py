#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_timing.py —— 时序判据（把"心腹大患"做成自动门）

从 PnR 的 timing_paths 读出 SETUP slack，与阈值比较：
  · slack 低于阈值            -> 判红（退出码 1）
  · 时序文件过旧（可选）      -> 判红（退出码 1）
  · 找不到或读不出            -> 报错（退出码 2）
  · 正常                      -> 通过（退出码 0）

用法：
  python tools/scripts/check_timing.py                    # 默认阈值 +5.0 ns
  python tools/scripts/check_timing.py --min 10           # 换阈值
  python tools/scripts/check_timing.py --require-fresh    # 验收流程用：文件必须够新
"""

import argparse
import glob
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def find_timing(explicit=None):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    pat = os.path.join("src", "gowin", "tdm_synth", "impl", "pnr", "*.timing_paths")
    cands = glob.glob(pat)
    if not cands:
        return None
    return max(cands, key=os.path.getmtime)


def read_setup_slack(path):
    """timing_paths 的格式：第一行 =====，第二行 SETUP，第三行就是 slack。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    for i, ln in enumerate(lines):
        if ln.strip().upper() == "SETUP" and i + 1 < len(lines):
            try:
                return float(lines[i + 1].strip())
            except ValueError:
                continue
    return None


def main():
    ap = argparse.ArgumentParser(description="PnR 时序判据")
    ap.add_argument("--min", type=float, default=5.0, dest="mn",
                    help="slack 下限，单位 ns（默认 5.0）")
    ap.add_argument("--require-fresh", action="store_true",
                    help="时序文件必须足够新，否则判红")
    ap.add_argument("--max-age-min", type=float, default=90.0,
                    help="配合 --require-fresh：允许的最大文件年龄（分钟）")
    ap.add_argument("--file", default=None, help="指定 timing_paths（默认自动找最新）")
    args = ap.parse_args()

    path = find_timing(args.file)
    if not path:
        print("  未找到 timing_paths（先跑一次综合与布局布线）")
        return 2

    slack = read_setup_slack(path)
    if slack is None:
        print("  无法从 %s 解析 SETUP slack" % path)
        return 2

    age_min = (time.time() - os.path.getmtime(path)) / 60.0
    print("  时序文件：%s" % path)
    print("  文件年龄：%.1f 分钟" % age_min)
    print("  SETUP slack = %+.3f ns   阈值 = %+.1f ns" % (slack, args.mn))

    if args.require_fresh and age_min > args.max_age_min:
        print("  判红：时序文件过旧（%.1f > %.1f 分钟），不能作为本次验收依据" % (age_min, args.max_age_min))
        return 1

    if slack < args.mn:
        print("  判红：slack 低于阈值（差 %.3f ns）" % (args.mn - slack))
        return 1

    print("  通过：余量 %.3f ns" % (slack - args.mn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
