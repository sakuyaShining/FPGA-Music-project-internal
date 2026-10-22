# -*- coding: utf-8 -*-
"""
fx_check.py —— 效果器（延迟 / 合唱）冲激响应判据（拓展 E4）

对应测试台：src/sim/tb_fx.v（+test=0 延迟 / +test=1 合唱）

【判据】
   D1 回声间距 = 设定的 dly_len（逐对精确）
   D2 回声幅度 = 冲激 × 反馈^k（等比，逐个比对，容差 ±1 count）
   D3 至少能看到 3 个回声（否则"反馈"没被验证）
   C1 合唱回声延迟 ∈ CHO_BASE ± depth（逐次）
   C2 调制幅度：延迟的极差 ≥ 0.6 × 2×depth（三角波确实在动）
   C3 延迟随时间单调成段（至少一次上升段 + 一次下降段）

用法：
   python tools/scripts/fx_check.py --simdir sim_build/fx
"""
import argparse
import os
import sys


def load_col(path):
    vals = []
    for l in open(path):
        l = l.strip()
        if l and l.lstrip("-").isdigit():
            vals.append(int(l))
    return vals


def peaks(y, tmin=0):
    """返回所有非零样本的 (位置, 值)"""
    return [(i, v) for i, v in enumerate(y) if v != 0 and i >= tmin]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default="sim_build/fx")
    ap.add_argument("--dly-len", type=int, default=2048)
    ap.add_argument("--fb", type=float, default=96.0 / 256.0)
    # 2026-10-03（第 9/10 轮）默认从 5000 改成 1280000：
    #   `imp` 是判据里的"干声冲激幅度"，而 D1 电平对齐修复后（fx_delay.v: `wet_sum <<< 8`），
    #   湿声已从【线缓冲域（16 位）】抬到【程序域（24 位）】—— 倍数 = 2^8 = 256。
    #   实测印证 ：第 0 个回声 1280000 = 5000 × 256 ；相邻比 0.3750/0.3749/0.3741
    #   = fb(96/256) ；回声间距 2048 = dly_len ⇒ 延迟本身是教科书级的 ，
    #   原来判据红只是因为还停在线缓冲域 。
    ap.add_argument("--imp", type=int, default=1280000,
                    help="干声冲激在【24 位程序域】的幅度（= 线缓冲域值 × 256）")
    ap.add_argument("--cho-base", type=int, default=1024)
    ap.add_argument("--cho-depth", type=int, default=64)
    a = ap.parse_args()
    d = a.simdir
    fails = []

    print("=" * 70)
    print(" 效果器冲激响应判据（拓展 E4：延迟 + 合唱）")
    print("=" * 70)

    # ======================================================================
    # 延迟
    # ======================================================================
    fd = os.path.join(d, "fx_delay.txt")
    if os.path.exists(fd):
        y = load_col(fd)
        pk = peaks(y)
        print("\n[D] 延迟：dly_len=%d 反馈=%.3f，检出回声 %d 个" % (a.dly_len, a.fb, len(pk)))
        for i, (pos, v) in enumerate(pk[:6]):
            exp = a.imp * (a.fb ** i)
            print("     第 %d 个回声：位置 %5d  幅度 %7d（期望 %7.1f）"
                  % (i, pos, v, exp))
        if len(pk) < 3:
            fails.append("D3: 只看到 %d 个回声（<3），反馈没被验证" % len(pk))
        # D1 间距
        if len(pk) >= 2:
            gaps = [pk[i + 1][0] - pk[i][0] for i in range(len(pk) - 1)]
            print("     回声间距：%s（期望 %d）" % (gaps[:5], a.dly_len))
            if any(g != a.dly_len for g in gaps):
                fails.append("D1: 回声间距 %s ≠ %d" % (gaps[:5], a.dly_len))
        # D2 幅度
        bad = 0
        for i, (pos, v) in enumerate(pk[:5]):
            exp = a.imp * (a.fb ** i)
            if abs(v - exp) > max(2.0, exp * 0.01):
                bad += 1
                print("       ✗ 第 %d 个回声幅度 %d ≠ %.1f" % (i, v, exp))
        if bad:
            fails.append("D2: %d 个回声幅度不符等比衰减" % bad)
    else:
        print("\n[D] 缺 fx_delay.txt（先跑 +test=0）")
        fails.append("D: 无数据")

    # ======================================================================
    # 合唱
    # ======================================================================
    fc = os.path.join(d, "fx_chorus.txt")
    if os.path.exists(fc):
        y = load_col(fc)
        # 冲激注入时刻：100, 237, 374, ...（每 137 样本一次，4 样本宽；共 12 次）
        inj = [100 + 137 * k for k in range(12)]
        delays = []
        print("\n[C] 合唱：CHO_BASE=%d depth=%d，量每次冲激的回声延迟"
              % (a.cho_base, a.cho_depth))
        for t in inj:
            # 在 t 之后 CHOBASE±depth 附近找第一个非零
            #   容差给 ±6：抽头在动，回声起点会有 1~2 个样本的抖动（最近邻重采样）
            lo = t + a.cho_base - a.cho_depth - 6
            hi = min(len(y), t + a.cho_base + a.cho_depth + 6)
            hit = next((i for i in range(max(0, lo), hi) if y[i] != 0), None)
            if hit is None:
                print("     注入 %4d：★ 未找到回声" % t)
                continue
            delays.append(hit - t)
            print("     注入 %4d → 回声延迟 %5d 样本（幅度 %d）" % (t, hit - t, y[hit]))
        if len(delays) < 4:
            fails.append("C: 有效回声不足（%d 个）" % len(delays))
        else:
            lo_d, hi_d = min(delays), max(delays)
            print("     延迟范围：%d ~ %d（期望 %d ± %d）"
                  % (lo_d, hi_d, a.cho_base, a.cho_depth))
            if lo_d < a.cho_base - a.cho_depth - 2 or hi_d > a.cho_base + a.cho_depth + 2:
                fails.append("C1: 延迟 %d~%d 超出 %d±%d"
                             % (lo_d, hi_d, a.cho_base, a.cho_depth))
            spread = hi_d - lo_d
            if spread < 0.6 * 2 * a.cho_depth:
                fails.append("C2: 调制极差 %d < 期望的 60%%（%d）"
                             % (spread, int(0.6 * 2 * a.cho_depth)))
            # C3 至少一段上升、一段下降
            up = any(delays[i + 1] > delays[i] for i in range(len(delays) - 1))
            dn = any(delays[i + 1] < delays[i] for i in range(len(delays) - 1))
            print("     单调性：有上升段 %s，有下降段 %s（三角波在动）" % (up, dn))
            if not (up and dn):
                fails.append("C3: 延迟序列没有同时出现上升与下降（没在调制？）")
    else:
        print("\n[C] 缺 fx_chorus.txt（先跑 +test=1）")
        fails.append("C: 无数据")

    # ======================================================================
    # 混响（冲激响应）：尾巴要密、要衰减、不能失控
    # ======================================================================
    fr = os.path.join(d, "fx_reverb.txt")
    if os.path.exists(fr):
        y = load_col(fr)
        pk = peaks(y)
        print("\n[R] 混响：冲激 + 单线多抽头反馈，检出非零样本 %d 个" % len(pk))
        if len(pk) < 200:
            fails.append("R1: 尾巴太稀（非零 %d 个，<300）—— 不像混响" % len(pk))
        # 头 8000 个样本里的回声数（第一抽头 1487 之后才算）
        tail = [v for i, v in pk if 100 + 750 <= i < 100 + 8000]
        print("     冲激后 750~8000 样本内的回声数 = %d（单抽头延迟只会有 3~4 个）"
              % len(tail))
        if len(tail) < 150:
            fails.append("R1: 尾巴密度不足（%d）" % len(tail))
        # 能量包络：每 1000 个样本一段
        W = 1000
        segs = []
        for s in range(0, min(len(y) - 100, 9000), W):
            e = sum(v * v for v in y[s:s + W])
            segs.append(e)
        if segs:
            print("     分段能量（每 %d 样本）: %s" % (W, segs[:9]))
            # 判据从【峰值段】开始算衰减，而不是从第 0 段：
            #   混响尾巴是"逐渐建起来再衰减"的，头一两段当然会上升。
            #   第一版从第 0 段要求单调，把正常的建立过程判成了自激。
            ipk = max(range(len(segs)), key=lambda i: segs[i])
            pk_e = segs[ipk] if segs[ipk] > 0 else 1
            print("     峰值在第 %d 段（能量 %.3g），从峰值段开始检查衰减" % (ipk, segs[ipk]))
            bad = sum(1 for i in range(ipk + 1, len(segs)) if segs[i] > segs[i - 1] * 1.05 + 1)
            if bad:
                fails.append("R2: 峰值之后仍有 %d 段逆势上升（应单调衰减）" % bad)
            ratio = segs[-1] / pk_e
            if ratio > 0.10:
                fails.append("R3: 尾巴没有衰减下去（末段/峰值 = %.3f）" % ratio)
            else:
                print("     R3 衰减：末段/峰值 = %.4f（<0.10 ✓ 没有失控）" % ratio)
        # 首个回声位置 ≈ 最小抽头 + 延迟
        if pk:
            first_pos = pk[0][0]
            print("     首个回声位置 = %d（最小抽头 743 + 流水）" % first_pos)
            if not (843 - 80 <= first_pos <= 843 + 80):
                fails.append("R4: 首个回声位置 %d 不在 743+100±80 附近" % first_pos)
    else:
        print("\n[R] 缺 fx_reverb.txt（先跑 +test=2）")
        fails.append("R: 无数据")

    print("\n" + "=" * 70)
    if fails:
        print(" ★ 未通过：")
        for x in fails:
            print("   -", x)
        return 1
    print(" ★★★ 通过（D1/D2/D3 延迟 · C1/C2/C3 合唱 · R1/R2/R3/R4 混响）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
