# -*- coding: utf-8 -*-
"""
seq_check.py —— 片上曲目定序器（E7）＋ LED 指引（E6）判据

对应测试台：src/sim/tb_seq.v（+test=0 慢档 / +test=1 快档）

【判据】
   S1 音符序列 == 曲谱（音高逐个）
   S2 每个音符【开】的时间戳 == 由 tempo_inc 独立推算的拍点时间戳（±1 个样本）
   S3 每个新音之前恰好有一个 note-off（同一拍上拆分，间隔 1 个样本）
   S4 拍点脉冲个数 == 推算的拍数；每个脉冲起点 == 推算拍点（±1）
   S5 逐步的 cur_note == 曲谱该步音高（休止符为 0）—— 这就是"LED 指引"的数据源
   S6 快档/慢档的总时长比 ≈ 10（证明 tempo_inc 真的在控制速度）

用法：python tools/scripts/seq_check.py --simdir sim_build/seq
"""
import argparse
import os
import sys

# 曲谱（与 song_seq.v 的 case 表逐字对应）
SCORE_NOTE = [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60, 0]
SCORE_BEATS = [1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 2, 2]
NSTEP = len(SCORE_NOTE)
TWO24 = 1 << 24
BP_LEN = 2109          # beat_pulse 展宽（样本）


def load_rows(path, ncol):
    rows = []
    for l in open(path):
        l = l.strip()
        if not l:
            continue
        p = l.split()
        if len(p) >= ncol and all(x.lstrip("-").isdigit() for x in p[:ncol]):
            rows.append([int(x) for x in p[:ncol]])
    return rows


def model_beats(tempo_inc, nsamp):
    """独立推算拍点（与 RTL 的 24 位累加器进位逐位一致）"""
    acc, out = 0, []
    for n in range(nsamp):
        s = acc + tempo_inc
        if s >= TWO24:
            out.append(n)
            acc = s - TWO24
        else:
            acc = s
    return out


def check_one(tag, seqfile, ledfile, tempo_inc, nsamp, fails):
    ev = load_rows(seqfile, 4)          # ns on note vel
    led = load_rows(ledfile, 4)         # ns beat cur_note step
    print("\n[%s] tempo_inc=%d，事件 %d 条，样本 %d" % (tag, tempo_inc, len(ev), len(led)))

    # ---- 期望事件 ----
    beats = model_beats(tempo_inc, nsamp)
    # 步进发生在【拍点那一刻】：RTL 是 `beat_cnt+1 >= step_beats` 就换步，
    #   所以第 0 步只持续到【第一个拍点】（不是等第二个拍点）。
    #   第一版模型把换步放在第二个拍点，于是时间戳正好差一拍 —— 典型的
    #   "模型对了 90% 却全错"。
    exp_ev = []                           # (tick, on, note)
    exp_ev.append((0, 1, SCORE_NOTE[0]))  # hold 释放后第一个样本就发第一个音
    st, cnt, prev_note = 0, 0, SCORE_NOTE[0]
    step_at_beat = []
    for bs in beats:
        cnt += 1
        if cnt >= SCORE_BEATS[st]:
            cnt = 0
            st = (st + 1) % NSTEP
            new_note = SCORE_NOTE[st]
            if prev_note != 0:
                exp_ev.append((bs + 1, 0, prev_note))
            if new_note != 0:
                exp_ev.append((bs + 2, 1, new_note))
            prev_note = new_note
        step_at_beat.append(st)
    step_of_beat = step_at_beat

    # ---- S1/S2/S3：逐条比对（自校准：以第一条事件对齐，消掉启动相位歧义）----
    got = [(r[0], r[1], r[2]) for r in ev]
    n = min(len(got), len(exp_ev))
    print("     期望事件 %d 条，实测 %d 条（比对前 %d 条）" % (len(exp_ev), len(got), n))
    bad_t, bad_n = 0, 0
    if n == 0:
        fails.append("%s S1: 一条事件都没记到" % tag)
    else:
        dt = got[0][0] - exp_ev[0][0]
        print("     对齐偏移 = %d 个样本（第一条事件）" % dt)
        for i in range(n):
            gt, go, gn = got[i]
            et, eo, en = exp_ev[i]
            if abs((gt - dt) - et) > 1:
                bad_t += 1
                if bad_t <= 3:
                    print("       ✗ 第 %d 条时间戳 实测 %d（对齐后 %d）≠ 推算 %d"
                          % (i, gt, gt - dt, et))
            if go != eo or gn != en:
                bad_n += 1
                if bad_n <= 3:
                    print("       ✗ 第 %d 条 实测(%d,%d) ≠ 推算(%d,%d)" % (i, go, gn, eo, en))
        if bad_n:
            fails.append("%s S1/S3: %d 条事件内容不符" % (tag, bad_n))
        if bad_t:
            fails.append("%s S2: %d 条时间戳不符" % (tag, bad_t))
        if abs(len(got) - len(exp_ev)) > 2:
            fails.append("%s: 事件条数 %d 与推算 %d 差太多" % (tag, len(got), len(exp_ev)))

    # ---- S4：拍点脉冲（同样自校准对齐）----
    pulses, inb = [], False
    for r in led:
        if r[1] and not inb:
            pulses.append(r[0])
            inb = True
        elif not r[1]:
            inb = False
    print("     拍点脉冲 %d 个（推算拍点 %d 个），宽度应≈%d 样本" % (len(pulses), len(beats), BP_LEN))
    nb = min(len(pulses), len(beats))
    if nb == 0:
        fails.append("%s S4: 一个拍点脉冲都没有" % tag)
    else:
        db = pulses[0] - beats[0]
        off = sum(1 for i in range(nb) if abs((pulses[i] - db) - beats[i]) > 1)
        if off:
            fails.append("%s S4: %d 个脉冲起点与推算拍点不符" % (tag, off))
        else:
            print("     对齐偏移 = %d 个样本 → 全部 %d 个拍点位置与推算一致 ✓" % (db, nb))
    if abs(len(pulses) - len(beats)) > 1:
        fails.append("%s S4: 脉冲数 %d ≠ 拍数 %d" % (tag, len(pulses), len(beats)))

    # ---- S5：LED 指引 = 当前步音高（用实测脉冲做区间，不再依赖推算对齐）----
    bad5 = 0
    for j in range(min(len(pulses) - 1, len(step_of_beat) - 1)):
        want = SCORE_NOTE[step_of_beat[j]]
        seg = [r for r in led if pulses[j] + 100 <= r[0] < pulses[j + 1]]
        if not seg:
            continue
        if seg[0][2] != want:
            bad5 += 1
            if bad5 <= 3:
                print("       ✗ 第 %d 拍 LED 指引 %d ≠ 曲谱 %d" % (j, seg[0][2], want))
    if bad5:
        fails.append("%s S5: %d 拍 LED 指引与曲谱不符" % (tag, bad5))
    else:
        print("     S5 LED 指引：每一拍的 cur_note 都与曲谱一致 ✓")

    return beats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default="sim_build/seq")
    ap.add_argument("--nsamp", type=int, default=60000)
    a = ap.parse_args()
    d = a.simdir
    fails = []

    print("=" * 70)
    print(" 曲目定序器（E7）＋ LED 指引（E6）判据")
    print("=" * 70)

    ok = True
    for tag, inc in (("慢档", 1272), ("快档", 12720)):
        sf = os.path.join(d, "seq_slow.txt" if inc == 1272 else "seq_fast.txt")
        lf = os.path.join(d, "led_slow.txt" if inc == 1272 else "led_fast.txt")
        if not (os.path.exists(sf) and os.path.exists(lf)):
            print("\n[%s] 缺数据（先跑 +test=%d）" % (tag, 0 if inc == 1272 else 1))
            fails.append("%s: 无数据" % tag)
            ok = False
            continue
        check_one(tag, sf, lf, inc, a.nsamp, fails)

    # ---- S6：两档速度比（用【拍间隔中位数】而不是拍数：拍数受边界取整影响，
    #         实测 4 拍 vs 45 拍会给出 11.25 的假比值）----
    lf_s = os.path.join(d, "led_slow.txt")
    lf_f = os.path.join(d, "led_fast.txt")
    if os.path.exists(lf_s) and os.path.exists(lf_f):
        def pulses_of(p):
            rows = load_rows(p, 4)
            c, inb = [], False
            for r in rows:
                if r[1] and not inb:
                    c.append(r[0])
                    inb = True
                elif not r[1]:
                    inb = False
            return c

        def med_iv(ps):
            iv = sorted(ps[i + 1] - ps[i] for i in range(len(ps) - 1))
            return iv[len(iv) // 2] if iv else 0

        ps, pf = pulses_of(lf_s), pulses_of(lf_f)
        ivs, ivf = med_iv(ps), med_iv(pf)
        ratio = (ivs / ivf) if ivf else 0
        print("\n[S6] 拍间隔中位数：慢档 %d 样本、快档 %d 样本（比值 %.2f，设定 10）"
              % (ivs, ivf, ratio))
        if abs(ratio - 10.0) > 0.3:
            fails.append("S6: 拍间隔比 %.2f ≠ 10" % ratio)

    print("\n" + "=" * 70)
    if fails:
        print(" ★ 未通过：")
        for x in fails:
            print("   -", x)
        return 1
    print(" ★★★ 通过（S1 音符序列 / S2 时间戳 / S3 开关配对 / S4 拍点 / S5 LED 指引 / S6 速度控制）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
