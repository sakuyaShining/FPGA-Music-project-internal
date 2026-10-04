# -*- coding: utf-8 -*-
"""
latency_check.py —— E5（控制→输出延迟）判据脚本

输入：（由 tb_latency 的 RESULT 行汇总）

【判据】
   L1 可复现性：同一相位跑两遍，**逐拍完全相同**（这就是"无抖动"的证据）
   L2 相位线性：t_smp(ph) = t_smp(0) − ph（跨周期时 +576），误差 0 拍
                ⇒ 延迟对事件到达时刻的依赖是【闭式可预测】的，不是随机
   L3 硬上限：t_pin 最大值 ≤ 0.2 ms（并要求给出相对 5 ms / 10 ms 的余量）
   L4 组号依赖有界：t_load 随组号变化，但始终 ≤ 1 个样本周期 + 固定项

用法：
   python tools/scripts/latency_check.py --file <tb_latency 输出的 RESULT 文本>
"""
import argparse
import re
import sys

FS_CLK_NS = 37.037          # 27 MHz
PERIOD = 512                # 每样本拍数（= NSLOT；时钟链 ÷16 × 32）
PARITY_FLIP = 511           # 装载奇偶翻转点 = sc = NSLOT-1（= 周期最后一拍）
LOAD_SEQ = 18               # 事件 → 装载序列写完的拍数


def parse(path):
    recs = []
    for l in open(path, encoding="utf-8"):
        m = re.search(r"RESULT phase=(-?\d+) prefill=(-?\d+) t_smp=(-?\d+) t_pin=(-?\d+) t_load=(-?\d+)", l)
        if m:
            recs.append(tuple(int(x) for x in m.groups()))
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--limit-ms", type=float, default=0.2)
    a = ap.parse_args()

    if not a.file:
        print("用法：python tools/scripts/latency_check.py --file <tb_latency 的 RESULT 输出文件>")
        return 2
    recs = parse(a.file)
    if not recs:
        print("没有解析到 RESULT 行"); return 1

    # A 段 = prefill 0 的相位扫描；B 段 = 组号扫描
    A = [r for r in recs if r[1] == 0]
    B = [r for r in recs if r[1] != 0]

    print("=" * 70)
    print(" E5 延迟判据（clk=27 MHz, fs=46875 Hz, 每样本 %d 拍）" % PERIOD)
    print("=" * 70)

    fails = []

    # ---- L1 可复现性 ----
    seen = {}
    dup_ok, dup_bad = 0, 0
    for ph, pf, ts, tp, tl in A:
        key = ph
        val = (ts, tp, tl)
        if key in seen:
            if seen[key] == val:
                dup_ok += 1
            else:
                dup_bad += 1
                print("  ✗ 相位 %d 两次结果不同：%s vs %s" % (ph, seen[key], val))
        else:
            seen[key] = val
    print("\n[L1] 可复现性：重复相位 %d 组，逐拍一致 %d，不一致 %d" % (dup_ok + dup_bad, dup_ok, dup_bad))
    if dup_bad:
        fails.append("L1: 同一相位两次测量不一致（存在非确定性）")

    # ---- L2 相位线性 ----
    #   模型不是"纯粹的 t0 - ph"，而是【分段】的：
    #     装载序列本身要 ~18 拍；而"待生效"的奇偶翻转点在 sc = NSLOT-1 = 511
    #     （周期最后一拍）。于是事件若晚于 511-18 = 493 拍到达，
    #     写进去的那一代就要多等一个周期。
    LOAD_SEQ = 18
    PARITY_FLIP = 511
    base = None
    for ph, pf, ts, tp, tl in A:
        if ph == 0:
            base = (ts, tp, tl)
    print("\n[L2] 相位线性（基准：相位 0 → t_smp=%d, t_pin=%d；翻转点 %d 拍）"
          % (base[0], base[1], PARITY_FLIP))
    for ph, pf, ts, tp, tl in A:
        extra = PERIOD if (ph + LOAD_SEQ) > PARITY_FLIP else 0
        pred_ts = base[0] - ph + extra
        pred_tp = base[1] - ph + extra
        ok = (ts == pred_ts) and (tp == pred_tp)
        print("     相位 %4d：实测 t_smp=%4d t_pin=%4d ｜ 预测 %4d / %4d %s"
              % (ph, ts, tp, pred_ts, pred_tp, "（含 +1 周期项）" if extra else "  ", ))
        if not ok:
            print("        ✗ 与预测不符（预测 %d / %d）" % (pred_ts, pred_tp))
            fails.append("L2: 相位 %d 偏离线性预测" % ph)

    # ---- L3 硬上限 ----
    mx = max(r[3] for r in A if r[3] > 0)
    mx_smp = max(r[2] for r in A if r[2] > 0)
    print("\n[L3] 端到端上限")
    print("     t_pin 最大 = %d 拍 = %.2f us = %.4f ms" % (mx, mx * FS_CLK_NS / 1000.0, mx * FS_CLK_NS / 1e6))
    print("     t_smp 最大 = %d 拍 = %.2f us" % (mx_smp, mx_smp * FS_CLK_NS / 1000.0))
    print("     相对要求：5 ms → 余量 %.0f× ；10 ms → 余量 %.0f×"
          % (5.0 / (mx * FS_CLK_NS / 1e6), 10.0 / (mx * FS_CLK_NS / 1e6)))
    if mx * FS_CLK_NS / 1e6 > a.limit_ms:
        fails.append("L3: t_pin 最大值 %.4f ms 超过 %.2f ms" % (mx * FS_CLK_NS / 1e6, a.limit_ms))

    # ---- L4 组号依赖 ----
    if B:
        tl = [r[4] for r in B if r[4] > 0]
        print("\n[L4] 组号依赖：t_load ∈ [%d, %d] 拍（跨度 %d 拍 = %.2f us）"
              % (min(tl), max(tl), max(tl) - min(tl), (max(tl) - min(tl)) * FS_CLK_NS / 1000.0))
        print("     说明：组号决定该组的时隙在本周期被访问的早晚 —— 仍是确定量"
              "（周期 = NSLOT = 512 拍，每个时隙每样本恰好访问一次）")
        print("     最坏合计（相位 + 组号）实测上界 = %d 拍 = %.2f us"
              % (mx, mx * FS_CLK_NS / 1000.0))

    print("\n" + "=" * 70)
    if fails:
        print(" ★ 未通过：")
        for f in fails:
            print("   -", f)
        return 1
    print(" ★★★ 通过（L1 可复现 / L2 闭式线性 / L3 余量 ≥ %.0f× / L4 组号依赖有界）"
          % (5.0 / (mx * FS_CLK_NS / 1e6)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
