# -*- coding: utf-8 -*-
"""
reg_ctl_check.py —— 运行时参数通道验收判据（拓展 E2 + E3）

对应测试台：src/sim/tb_reg_ctl.v（+test=0..3）

【判据】
   R1 开机自举：寄存器表被真实写过（CTRL / VIB_INC / VIB_DEPTH / GMK / PRESET）
   E3 音色切换：写 PRESET 后，该音 16 个泛音的幅度【逐个等于】preset_part.hex
                对应行（amp = (p_amp × vel) >> 8，vel = 8<<4 = 128）
   E2 颤音深度：写 VIB_DEPTH = 0 / 1000 / 2000 → 实测频偏(音分) = 0 / 26.2 / 52.0
   E2 滑音时间：写 GLIDE_M_K 的 (m=3,k=13) 与 (m=3,k=10) → 实测衰减时间常数 ≈ 8:1

用法：
   python tools/scripts/reg_ctl_check.py --simdir sim_build/latency
"""
import argparse
import math
import os
import sys

FS = 46875.0
P = 16


def load_hex(path):
    vals = []
    with open(path) as f:
        for line in f:
            for w in line.split():
                vals.append(int(w, 16))
    return vals


def load_col(path):
    return [int(l) for l in open(path) if l.strip() and l.strip().lstrip("-").isdigit()]


def dinc(ph):
    return [(ph[i + 1] - ph[i]) % (1 << 24) for i in range(len(ph) - 1)]


def cents(f, f0):
    return 1200.0 * math.log2(f / f0)


def decay_mirror(m, k, cut, n):
    """严格照抄 pitch_mod.v 的整数递推（返回 |gq| 的衰减序列，初值 1.0 归一化用）"""
    out = []
    mag = 1 << 17          # 用大初值观察比例关系即可
    for _ in range(n):
        out.append(mag)
        step = (mag * m) >> k
        if step == 0:
            step = 1
        mag = 0 if mag <= cut else mag - step
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--simdir", default="sim_build/latency")
    a = ap.parse_args()
    d = a.simdir
    fails = []

    print("=" * 70)
    print(" 运行时参数通道验收（拓展 E2 + E3）")
    print("=" * 70)

    # ======================================================================
    # E3：音色切换（幅度逐个核对预设表）
    # ======================================================================
    fpreset = os.path.join(d, "rc_preset.txt")
    if not os.path.exists(fpreset):
        print("\n[E3] 缺 rc_preset.txt（先跑 +test=0）")
        fails.append("E3: 无数据")
    else:
        note_inc = load_hex(os.path.join(d, "note_inc.hex"))
        part = load_hex(os.path.join(d, "preset_part.hex"))
        rows = [[int(x) for x in l.split()] for l in open(fpreset) if l.strip()]
        print("\n[E3] 音色切换：写 PRESET 寄存器 → 该音 16 个泛音幅度")
        print("     vel = 8<<4 = 128 → 期望 amp = (p_amp × 128) >> 8 = p_amp >> 1")
        for p in range(min(4, len(rows))):
            ok = 0
            for k in range(P):
                word = part[p * P + k]
                p_amp = (word >> 24) & 0xFF
                exp = (p_amp * 128) >> 8
                if rows[p][k] == exp:
                    ok += 1
            print("     预设 %0d：16 个泛音幅度匹配 %2d / 16" % (p, ok))
            if ok != P:
                fails.append("E3: 预设 %0d 只匹配 %0d/16" % (p, ok))
        # 四个预设必须彼此不同（否则"切换"没有意义）
        if len(rows) >= 2 and rows[0] == rows[1]:
            fails.append("E3: 预设 0 与 1 的幅度完全相同")

    # ======================================================================
    # E2a：颤音深度（写寄存器 → 实测频偏）
    # ======================================================================
    fvib = os.path.join(d, "rc_vib.txt")
    if not os.path.exists(fvib):
        print("\n[E2a] 缺 rc_vib.txt（先跑 +test=1）")
        fails.append("E2a: 无数据")
    else:
        note_inc = load_hex(os.path.join(d, "note_inc.hex"))
        INC = note_inc[69]
        ph = load_col(fvib)
        seglen = len(ph) // 3
        print("\n[E2a] 颤音深度：写 VIB_DEPTH = 0 / 1000 / 2000")
        depths = [0, 1000, 2000]
        for s in range(3):
            seg = ph[s * seglen:(s + 1) * seglen]
            dg = dinc(seg)
            # 跳过换档瞬间
            dg = dg[200:]
            cs = [cents(x, INC) for x in dg]
            peak = (max(cs) - min(cs)) / 2.0
            mean = sum(cs) / len(cs)
            exp = cents(1 + depths[s] / 65536.0, 1.0)
            print("     段 %0d：VIB_DEPTH=%4d → 实测峰偏 %6.2f 音分（期望 %6.2f），"
                  "均值 %+6.2f" % (s, depths[s], peak, exp, mean))
            if abs(peak - exp) > max(1.5, exp * 0.06):
                fails.append("E2a: 段 %0d 峰偏 %.2f ≠ %.2f" % (s, peak, exp))
            # 中心判据：颤音必须【越过零点】（用均值会被半个周期带偏，
            # 第一版就吃了这个亏：2600 样本 @50 Hz = 2.8 个周期）
            if depths[s] > 0 and not (min(cs) < 0.0 < max(cs)):
                fails.append("E2a: 段 %0d 频偏没有越过零点（%+.2f .. %+.2f）"
                             % (s, min(cs), max(cs)))

    # ======================================================================
    # E2b：滑音时间常数（两组 (m,k) 应相差 8 倍）
    # ======================================================================
    def glide_check(path, step):
        """线性速率滑音。用测试台 dump 出来的【RTL 自己的 gq】做判据：
             L-a 递推必须是"每样本减 step，到 0 停"（逐样本）
             L-b 相位增量必须是 INC_NEW + ((INC_NEW × gq) >> 16)（逐样本，滞后 0~2）
             L-c 时长 = |gq0| / step
           ★ 不用"表里算出的 gq0"：它因倒数表 20 位舍入会差 1~2 个计数，
             那是精度问题，不是设计问题。"""
        note_inc = load_hex(os.path.join(d, "note_inc.hex"))
        INC_NEW = note_inc[72]
        rows = [l.split() for l in open(path) if l.strip()]
        s0 = [int(x[0]) for x in rows]
        gq = [int(x[2]) for x in rows]
        # 滑音初值是在【装载被消费】那一拍才写进去的，dump 前几拍 gq 还是 0 —— 跳过
        off = next((i for i, g in enumerate(gq) if g != 0), None)
        if off is None:
            return None, None, None, None, None
        gq = gq[off:]
        s0 = s0[off:]
        dg = dinc(s0)
        gq0 = gq[0]
        # L-a：递推逐样本成立
        bad_a = 0
        # 从 i=1 开始：第 0 对里含【装载写入】那一步（0 → gq0 的跳变不是衰减）
        for i in range(1, len(gq) - 1):
            g, nxt = gq[i], gq[i + 1]
            if g > 0:
                exp = (g - step) if g > step else 0
            elif g < 0:
                exp = (g + step) if g < -step else 0
            else:
                exp = 0
            if nxt != exp:
                bad_a += 1
        # L-b：相位增量 = INC_NEW + ((INC_NEW × gq) >> 16)（滞后搜索）
        exp_inc = [INC_NEW + ((INC_NEW * g) >> 16) for g in gq]
        best = None
        for lag in range(0, 3):
            n = min(len(exp_inc) - lag, len(dg))
            if n < 50:
                break
            diff = sum(1 for j in range(n) if dg[j] != exp_inc[lag + j])
            if best is None or diff < best[1]:
                best = (lag, diff, n)
        # L-c：时长
        dur = None
        for j, x in enumerate(dg):
            if abs(x - INC_NEW) <= 1:
                dur = j
                break
        return gq0, bad_a, best, dur, abs(gq0) / float(step)

    print("\n[E2b] 滑音速率：写 GLIDE_STEP 后量时长与轨迹")
    durs = {}
    for tag, step in (("20", 20), ("160", 160)):
        f = os.path.join(d, "rc_glide%s.txt" % tag)
        if not os.path.exists(f):
            print("     缺 rc_glide%s.txt（先跑 +test=%s）" % (tag, "2" if tag == "20" else "3"))
            fails.append("E2b: 缺 rc_glide%s.txt" % tag)
            continue
        gq0, bad_a, best, dur, exp_dur = glide_check(f, step)
        if gq0 is None:
            print("     组 GLIDE_STEP=%s：★ 未检出滑音（gq 全 0）" % tag)
            fails.append("E2b: step=%s 未检出滑音" % tag)
            continue
        print("     GLIDE_STEP=%3d：RTL 的 gq0 = %d（%.0f 音分）"
              % (step, gq0, cents(1 + gq0 / 65536.0, 1.0)))
        print("            L-a 线性递推（每样本减 %d，到 0 停）：不符 %d 个样本"
              % (step, bad_a))
        if bad_a != 0:
            fails.append("E2b: step=%d 线性递推不符 %d 个样本" % (step, bad_a))
        print("            L-b 相位增量 = INC_NEW + (INC_NEW×gq)>>16：滞后 %d，不符 %d / %d"
              % (best[0], best[1], best[2]))
        if best[1] != 0:
            fails.append("E2b: step=%d 相位增量与 gq 不符 %d/%d" % (step, best[1], best[2]))
        print("            L-c 时长：实测 %s 样本，理论 |gq0|/step = %.0f 样本"
              % (dur, exp_dur))
        if dur and abs(dur - exp_dur) > max(3, exp_dur * 0.02):
            fails.append("E2b: step=%d 实测时长 %s ≠ 理论 %.0f" % (step, dur, exp_dur))
        durs[step] = dur
    if 20 in durs and 160 in durs and durs[20] and durs[160]:
        ratio = durs[20] / float(durs[160])
        print("     时长比 (step20)/(step160) 实测 = %.2f（理论 8.0）" % ratio)
        if abs(ratio - 8.0) > 0.3:
            fails.append("E2b: 时长比 %.2f ≠ 8" % ratio)

    # ======================================================================
    # E4 旁路等价性：FX 全关时音频必须与引擎输出逐位相同
    # ======================================================================
    fb = os.path.join(d, "rc_bypass.txt")
    if os.path.exists(fb):
        rows = [l.split() for l in open(fb) if l.strip()]
        bad = sum(1 for r in rows if r[0] != r[1])
        nz = sum(1 for r in rows if int(r[0]) != 0)
        print("\n[E4-bypass] FX 全关时：顶层音频 vs 引擎输出")
        print("     比对 %d 个样本（其中非零 %d 个），不一致 %d 个" % (len(rows), nz, bad))
        if bad != 0:
            fails.append("E4: 旁路时音频与引擎输出不一致 %d 个样本" % bad)
        if nz == 0:
            fails.append("E4: 旁路测试没有非零样本（测试无效）")
    else:
        print("\n[E4-bypass] 缺 rc_bypass.txt（先跑 +test=4）")
        fails.append("E4: 无旁路数据")

    # ======================================================================
    # E7 集成：定序器经寄存器真的驱动了引擎
    # ======================================================================
    fs_ = os.path.join(d, "rc_seq.txt")
    if os.path.exists(fs_):
        rows = [l.split() for l in open(fs_) if l.strip()]
        act = [int(r[0]) for r in rows]
        # LED 共阳极取反 → 判据里取反回来
        gd = [(~int(r[1])) & 0x3F for r in rows]
        nz = [int(r[2]) for r in rows]
        print("\n[E7-集成] 定序器驱动引擎（%d 个样本）" % len(rows))
        onsets = sum(1 for i in range(1, len(act)) if act[i] and not act[i - 1])
        offs = sum(1 for i in range(1, len(act)) if act[i - 1] and not act[i])
        nz_on = sum(1 for i in range(len(act)) if act[i] and nz[i])
        nz_tot = sum(1 for i in range(len(act)) if act[i])
        print("     引擎在奏：出现 %d 次起音 / %d 次收音；有声音的样本 %d/%d"
              % (onsets, offs, nz_on, max(1, nz_tot)))
        if onsets < 5:
            fails.append("E7: 只出现 %d 次起音（应有 8 次左右）" % onsets)
        if offs < 5:
            fails.append("E7: 只出现 %d 次收音（note-off 没生效，曲目会糊）" % offs)
        if nz_tot and nz_on < nz_tot * 0.9:
            fails.append("E7: 在奏期间只有 %d/%d 个样本有声音" % (nz_on, nz_tot))
        # ----------------------------------------------------------------
        # LED 指引序列（2026-10-06 重写判据）
        #
        #   ★ 原判据是错的，且**永远不可能通过**。原写法：
        #       seq = led 的低 5 位（连续去重）
        #       exp = 曲谱 MIDI 音高 & 0x1F（连续去重）
        #       要求 min(len(seq), len(exp)) >= 5 且逐项相等
        #     三个错处：
        #     ① 口径错：led_ind.v 的输出是 **一热的 5 档音高台阶**
        #        （band_of: <=51→0, 52..66→1, 67..81→2, 82..96→3, >=97→4），
        #        不是 MIDI 音高的低 5 位。拿 60&0x1F=28 去比永远对不上。
        #     ② 门槛错：曲谱音高只有 MIDI 60..69 ⇒ 只落在 band 1 与 2 ⇒
        #        期望序列最长为 [1,2,1]（3 项），**不可能 >= 5**。
        #        所以这条判据是"写在纸上就注定红"的。
        #     ③ 结论错：实测 LED 是 1→2→1（band），而 4/12000 个样本出现
        #        band 0 是内核复位时 cur_note=0 的正常瞬态。
        #   ⇒ 改为按 led_ind.v 的规格判三件事（实测值见下）：
        #        ① ladder 恒为一热（规格：5'b00001 << band）
        #        ② band 序列与曲谱推算的期望序列一致（允许开头的复位零瞬态）
        #        ③ 拍点位（led[5]）确有拉长的脉冲
        #   注意：band 只有 5 档，曲谱跨度小 ⇒ 序列短是**正常的**，
        #     判据不能拿"项数"当丰富度指标（这正是原判据的根因）。
        # ----------------------------------------------------------------
        onehot_bad = sum(1 for v in gd if bin(v & 0x1F).count("1") != 1)
        bands = [(v & 0x1F).bit_length() - 1 for v in gd]
        #   连续去重，并丢掉 band 0（复位瞬态：cur_note=0 时 band_of(0)=0）
        bseq, last = [], None
        for b in bands:
            if b != last and b != 0:
                bseq.append(b)
            last = b
        beat_hi = sum(1 for v in gd if (v >> 5) & 1)

        SCORE = [60, 60, 67, 67, 69, 69, 67, 65, 65, 64, 64, 62, 62, 60]

        def band_of(n):
            return 0 if n <= 51 else 1 if n <= 66 else 2 if n <= 81 else 3 if n <= 96 else 4

        exp_b, last = [], None
        for x in SCORE:
            b = band_of(x)
            if b != last:
                exp_b.append(b)
            last = b

        print("     LED 音高台阶(band) 去重序列 = %s" % bseq[:12])
        print("     曲谱推算的期望 band 序列   = %s" % exp_b)
        print("     非一热样本 %d/%d   拍点位为高的样本 %d" % (onehot_bad, len(gd), beat_hi))

        if onehot_bad:
            fails.append("E7: LED 音高台阶不是一热编码（%d/%d 个样本）" % (onehot_bad, len(gd)))
        #   ② 期望序列必须是实测序列的**子序列**（按序出现）。
        #      这样既容忍开头的复位瞬态与中间未变档，也不放过"完全对不上"。
        it = iter(bseq)
        if not all(any(x == e for x in it) for e in exp_b):
            fails.append("E7: LED 音高台阶序列与曲谱不符（实测 %s，期望按序出现 %s）"
                         % (bseq[:12], exp_b))
        else:
            print("     ✓ 曲谱 band 序列按序出现在 LED 上")
        #   ③ 拍点：80 ms 拉长（27 MHz × 80 ms ≈ 2.16e6 拍，远长于一次采集）
        if beat_hi == 0:
            fails.append("E7: LED 拍点位从未点亮")
        #   注：band 只有 5 档且本曲跨度 60..69 ⇒ 去重后只有 1→2→1，
        #     所以**不得**再用"序列项数"当判据（原判据就是死在这里）。
        if max(act) == 0 or max(nz) == 0:
            fails.append("E7: 定序器没有驱动出任何声音（在奏标志始终 0 / 音频全 0）")
    else:
        print("\n[E7-集成] 缺 rc_seq.txt（先跑 +test=5）")
        fails.append("E7: 无集成数据")

    print("\n" + "=" * 70)
    if fails:
        print(" ★ 未通过：")
        for x in fails:
            print("   -", x)
        return 1
    print(" ★★★ 通过（E2 颤音深度 / E2 滑音时间 / E3 音色切换）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
