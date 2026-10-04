# -*- coding: utf-8 -*-
"""
perf_check.py —— 演奏交互层（M1/M9）判据

对应测试台：src/sim/tb_perf.v（+test=0..4）

【为什么核心是"交叉测试"】
  M1 原文「≥2 个独立可控演奏维度」，判据是"现场演示可分别操控"。
  只证明"两个都能变"是不够的 —— 必须证明【动一个，另一个不动】：
     P1 只动维度1（选音）→ 音高变、力度恒定
     P2 只动维度2（力度）→ 力度变、音高恒定
  这两条同时成立才叫"独立可控"。

  P3 锁存：触发后再动维度，正在响的音不许变（真实乐器语义）
  P4 拨弦/力度感应：挥手越快 → 力度越大（单调）
  P5 集成：动作 → 真引擎起振的延迟（补 E5 里"不含控制侧"那一段）
  P6 松手收声：每次 note-on 都有配对的 note-off

用法：python tools/scripts/perf_check.py --simdir sim_build/perf
"""
import argparse
import os
import sys


def load_hex(p):
    v = []
    for l in open(p):
        for w in l.split():
            v.append(int(w, 16))
    return v


def load_ev(p):
    """动作事件：ns on note vel"""
    out = []
    for l in open(p):
        l = l.strip()
        if not l:
            continue
        f = l.split()
        if len(f) >= 4 and all(x.lstrip("-").isdigit() for x in f[:4]):
            out.append((int(f[0]), int(f[1]), int(f[2]), int(f[3])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default="sim_build/perf")
    a = ap.parse_args()
    d = a.simdir
    fails = []

    print("=" * 70)
    print(" 演奏交互层判据（M1 独立可控维度 + M9 自研交互形态）")
    print("=" * 70)

    # ======================================================================
    # P1 只动选音维度
    # ======================================================================
    p = os.path.join(d, "perf_a.txt")
    if os.path.exists(p):
        ev = load_ev(p)
        ons = [e for e in ev if e[1] == 1]
        notes = [e[2] for e in ons]
        vels = set(e[3] for e in ons)
        print("\n[P1] 只动维度1（选音）：固定力度，扫音高")
        print("     触发的音高序列 = %s" % notes)
        print("     力度取值集合   = %s（必须只有一个值）" % sorted(vels))
        if len(notes) < 5:
            fails.append("P1: note-on 太少（%d）" % len(notes))
        else:
            if any(notes[i + 1] <= notes[i] for i in range(len(notes) - 1)):
                fails.append("P1: 音高不是严格递增 %s" % notes)
            if len(vels) != 1:
                fails.append("P1: 力度随选音维度变化了 %s（不独立）" % sorted(vels))
    else:
        print("\n[P1] 缺 perf_a.txt"); fails.append("P1: 无数据")

    # ======================================================================
    # P2 只动力度维度
    # ======================================================================
    p = os.path.join(d, "perf_b.txt")
    if os.path.exists(p):
        ev = load_ev(p)
        ons = [e for e in ev if e[1] == 1]
        vels = [e[3] for e in ons]
        notes = set(e[2] for e in ons)
        print("\n[P2] 只动维度2（力度）：固定音高，扫力度")
        print("     触发的力度序列 = %s" % vels)
        print("     音高取值集合   = %s（必须只有一个值）" % sorted(notes))
        if len(vels) < 8:
            fails.append("P2: note-on 太少（%d）" % len(vels))
        else:
            if any(vels[i + 1] <= vels[i] for i in range(len(vels) - 1)):
                fails.append("P2: 力度不是严格递增 %s" % vels)
            if len(notes) != 1:
                fails.append("P2: 音高随力度维度变化了 %s（不独立）" % sorted(notes))
    else:
        print("\n[P2] 缺 perf_b.txt"); fails.append("P2: 无数据")

    # ======================================================================
    # P3 锁存 + P6 收声配对
    # ======================================================================
    p = os.path.join(d, "perf_latch.txt")
    if os.path.exists(p):
        ev = load_ev(p)
        ons = [e for e in ev if e[1] == 1]
        offs = [e for e in ev if e[1] == 0]
        pairs = sorted(set((e[2], e[3]) for e in ons))
        print("\n[P3] 锁存：按住期间把两个维度都改掉，正在响的音不许变")
        print("     出现过的 (音高,力度) 组合 = %s" % pairs)
        print("     事件总数 on/off = %d/%d" % (len(ons), len(offs)))
        if len(pairs) != 2:
            fails.append("P3: 期望恰好两种组合（按下用旧值、重按用新值），实测 %d 种" % len(pairs))
        else:
            first = sorted(pairs)[0]
            # 第一次按下必须是"触发当时"的维度值（音高 63 / 力度 15）
            exp_first = None
            for e in ons:
                exp_first = (e[2], e[3]); break
            if exp_first != (63, 15):
                fails.append("P3: 首次触发锁存的是 %s，应为 (63,15)" % (exp_first,))
            else:
                print("     首次触发锁存 = %s ✓（按住期间扫维度没有改到它）" % (exp_first,))
        # P6：每个 on 都要有配对 off
        if len(ons) != len(offs):
            fails.append("P6: on/off 数量不配对 %d/%d" % (len(ons), len(offs)))
        else:
            print("     P6 收声配对：%d 对 ✓" % len(ons))
    else:
        print("\n[P3] 缺 perf_latch.txt"); fails.append("P3: 无数据")

    # ======================================================================
    # P4 变化率 → 力度（拨弦/力度感应）
    # ======================================================================
    p = os.path.join(d, "perf_rate.txt")
    if os.path.exists(p):
        ev = load_ev(p)
        ons = [e for e in ev if e[1] == 1]
        vels = [e[3] for e in ons]
        print("\n[P4] 变化率触发（挥手=拨弦）：三档挥速 → 力度")
        print("     触发的力度序列 = %s（期望 4 / 10 / 15）" % vels)
        if vels != [4, 10, 15]:
            if any(vels[i + 1] < vels[i] for i in range(len(vels) - 1)):
                fails.append("P4: 力度随挥速不单调 %s" % vels)
            else:
                fails.append("P4: 力度序列 %s 与期望 [4,10,15] 不符" % vels)
        else:
            print("     三档挥速 → 力度单调递增且数值精确 ✓")
    else:
        print("\n[P4] 缺 perf_rate.txt"); fails.append("P4: 无数据")

    # ======================================================================
    # P5 集成：动作 → 真引擎起振的延迟 + 音高真的到了引擎
    # ======================================================================
    p = os.path.join(d, "perf_int.txt")
    if os.path.exists(p):
        rows = []
        for l in open(p):
            f = l.split()
            if len(f) >= 6 and all(x.lstrip("-").isdigit() for x in f[:6]):
                rows.append([int(x) for x in f[:6]])
        # 第一个"正在响"的样本
        t_on = next((r[0] for r in rows if r[2] == 1), None)
        t_eng = next((r[0] for r in rows if r[4] != 0), None)
        note = next((r[1] for r in rows if r[2] == 1), None)
        print("\n[P5] 集成：传感器 → 交互核心 → ev_* → 真引擎")
        print("     动作开始于样本 %s，引擎组 0 起振于样本 %s，音高 %s"
              % (t_on, t_eng, note))
        if t_on is None or t_eng is None:
            fails.append("P5: 没测到动作或引擎起振")
        else:
            lat = t_eng - t_on
            print("     控制侧延迟 = %d 个样本 = %.2f us（引擎侧延迟见 E5 文档）"
                  % (lat, lat * 1.0e6 / 52734.375))
            if lat < 0 or lat > 3:
                fails.append("P5: 控制侧延迟 %d 个样本超出预期（应 ≤3）" % lat)
            # 音高是否真的写进引擎
            ni = load_hex(os.path.join(d, "note_inc.hex"))
            inc0 = next((r[4] for r in rows if r[4] != 0), None)
            if note is not None and inc0 is not None and 0 <= note < len(ni):
                if inc0 == ni[note]:
                    print("     引擎 group0 的相位增量 = note_inc[%d] = %d ✓（逐位相符）"
                          % (note, inc0))
                else:
                    fails.append("P5: 引擎 inc=%d ≠ note_inc[%d]=%d" % (inc0, note, ni[note]))
    else:
        print("\n[P5] 缺 perf_int.txt"); fails.append("P5: 无数据")

    print("\n" + "=" * 70)
    if fails:
        print(" ★ 未通过：")
        for x in fails:
            print("   -", x)
        return 1
    print(" ★★★ 通过（P1 选音独立 / P2 力度独立 / P3 锁存 / P4 力度感应 / P5 集成+延迟 / P6 收声）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
