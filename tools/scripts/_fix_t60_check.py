# -*- coding: utf-8 -*-
"""把 t60_check.py 的判据改成【与实现相符】的版本（第 8 轮实测修正）：

实测发现两件事，都必须写进判据：
 ① RTL 的混响是 **8 抽头网络**（fx_delay.v: RT0..RT7 = 743/806/870/939/1008/1068/1140/1229），
    而 21 号 §6 的理论式 `6.91·Ts/(1−fb)` 假设的是**单抽头环路** ✗
    ⇒ 该式对本实现**不适用** ✓（我用 dly_len 当 Ts 是抄错了尺子 ✗，
      审计第 4 条"尺子与被测物同源"正是防这个 ✓）。
    真正与实现相符的判据是**比例一致性**：T60 ∝ 1/(−ln fb) ✓
    （实测 fb 0.25→0.50 时 T60 恰好 ×2.07 ✓✓）。
 ② **默认 RV_FB=0xC0（0.75）会让混响满饱和** ✗✗（实测 64357/70000 个样本被钳在 ±32767），
    0xE0 更糟（67646）✓ ⇒ 判据必须**直接检查饱和样本数** ✓
    （这正是 21 号 §6 第 7 步"溢出测试 V5"要防的 ✓，而闸口原来的回声计数判据看不见它 ✗）。
"""
import io

p = "tools/scripts/t60_check.py"
s = io.open(p, encoding="utf-8-sig").read()

# ① 把"逐档 vs 单抽头理论"的判定，换成【比例一致性 + 饱和检查】
old = """        err = abs(t60 - t60_exact) / t60_exact * 100.0
        rows.append((fbq, fb, t60, t60_exact, t60_approx, err))
        print("  fb=0x%02X(%.3f): T60 实测 %.4f s | 精确理论 %.4f s | 近似理论 %.4f s | 误差 %.1f%% %s"
              % (fbq, fb, t60, t60_exact, t60_approx, err, "OK" if err < 10 else "XX"))"""
new = """        sat = int((np.abs(h) >= 32767).sum())
        satp = 100.0 * sat / len(h)
        rows.append((fbq, fb, t60, t60_exact, t60_approx, satp))
        print("  fb=0x%02X(%.3f): T60 实测 %.4f s | 单抽头式参考 %.4f s | **饱和样本 %d (%.1f%%)** %s"
              % (fbq, fb, t60, t60_exact, sat, satp,
                 "<-- 削顶 ✗" if satp > 5.0 else "OK"))"""
assert old in s, "① 未匹配"
s = s.replace(old, new)

# ② V2 判定：改成"比例一致性"（非饱和档）+ 饱和档必须被标出
old2 = """    print("-" * 74)
    print("  [V2] 逐档 T60 vs 理论（判定用精确式，容差 10%）：")
    ok2 = all(r[5] < 10.0 for r in rows) and len(rows) >= 3
    print("       ⇒ %s（%d 档，最大误差 %.1f%%）"
          % ("通过 ✓" if ok2 else "未通过 ✗", len(rows),
             max([r[5] for r in rows]) if rows else -1))
    if not ok2:
        fails.append("V2 T60 误差超标")"""
new2 = """    print("-" * 74)
    print("  [V2] T60 与 fb 的**比例一致性**（与实现相符的判据 ✓）：")
    print("       依据：T60 ∝ 1/(−ln fb)。取两个**未饱和**档验证比值：")
    clean = [r for r in rows if r[5] <= 5.0]
    if len(clean) >= 2:
        (f1, fb1, t1, _, _, _), (f2, fb2, t2, _, _, _) = clean[0], clean[1]
        want = math.log(fb1) / math.log(fb2)          # T60_1/T60_2 的理论比
        got = t1 / t2 if t2 else 0.0
        e = abs(got - want) / want * 100.0
        print("       fb %.2f→%.2f：理论比 %.3f，实测比 %.3f，误差 %.1f%% ⇒ %s"
              % (fb1, fb2, want, got, e, "通过 ✓" if e < 15 else "未通过 ✗"))
        if e >= 15:
            fails.append("V2 比例一致性超标（%.1f%%）" % e)
    else:
        print("       ✗ 未饱和档不足 2 个，无法验证"); fails.append("V2 无足够非饱和档")

    print("  [V5] 溢出/饱和检查（21 号 §6 第 7 步）：")
    bad_sat = [r for r in rows if r[5] > 5.0]
    if bad_sat:
        for r in bad_sat:
            print("       ✗ RV_FB=0x%02X（fb=%.3f）饱和 %.1f%% ⇒ **该档不可用**"
                  % (r[0], r[1], r[5]))
        fails.append("V5 %d 档混响饱和削顶" % len(bad_sat))
    else:
        print("       ⇒ 全部档位无饱和 ✓")"""
assert old2 in s, "② 未匹配"
s = s.replace(old2, new2)

# ③ V3 的窗口跟着实测 T60 缩放（原来固定前 200ms，对短 T60 会误判 ✗）
s = s.replace("        dens = echo_density(h)",
              "        dens = echo_density(h, win_ms=max(5, int(rows[-1][2] * 1000 / 8)))")

io.open(p, "w", encoding="utf-8", newline="").write(s)
print("  t60_check.py 判据已按实测修正 ✓（比例一致性 + 饱和检查 + V3 窗口自适应）")
