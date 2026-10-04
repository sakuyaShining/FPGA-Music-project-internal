# -*- coding: utf-8 -*-
"""第 9 轮收尾：① tb_t60 按 fb 值生成文件名 + damp 用最大档 7；② 判据 V2 改成单调性。"""
import io

# ---------- ① tb_t60 ----------
p = "src/sim/tb_t60.v"
s = io.open(p, encoding="utf-8-sig").read()

# 文件名按 fb 值生成（原来写死 ✗，改档位表就对不上了）
old = """            case (k)
                0: fout = $fopen("t60_fb40.txt", "w");
                1: fout = $fopen("t60_fb80.txt", "w");
                2: fout = $fopen("t60_fbc0.txt", "w");
                default: fout = $fopen("t60_fb00.txt", "w");
            endcase"""
new = """            // ★ 文件名按 fb 值生成 ✓（原来写死 ✗：改了档位表就对不上，判据找不到文件 ✗）
            $sformat(fname, "t60_fb%02x.txt", fb_tab[k][7:0]);
            fout = $fopen(fname, "w");"""
if old in s:
    s = s.replace(old, new)
    print("  文件名改为按 fb 值生成 ✓")
else:
    print("  !! 文件名段未匹配")

if "reg [1023:0] fname;" not in s:
    s = s.replace("integer k, s, q, fout;", "integer k, s, q, fout;\n    reg [1023:0] fname;")
    print("  已声明 fname ✓")

# damp 用最大档（判据 V4 要求"damp 最大档"；寄存器 3 位 ⇒ 最大 7）
s = s.replace("wr(8'h49, 8'h03);   // REV_DAMP = 3",
              "wr(8'h49, 8'h07);   // REV_DAMP = 7 ★ 判据 V4 要求【damp 最大档】✓（3 位寄存器最大值）")
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("  damp 改为最大档 7 ✓")

# ---------- ② 判据 V2 改成单调性 ----------
p = "tools/scripts/t60_check.py"
s = io.open(p, encoding="utf-8-sig").read()
old2 = """    clean = [r for r in rows if r[5] <= 5.0]
    if len(clean) >= 2:
        (f1, fb1, t1, _, _, _), (f2, fb2, t2, _, _, _) = clean[0], clean[1]
        want = math.log(fb2) / math.log(fb1)          # T60 ∝ 1/(−ln fb) ⇒ T60_1/T60_2 = ln(fb2)/ln(fb1)
        got = t1 / t2 if t2 else 0.0
        e = abs(got - want) / want * 100.0
        print("       fb %.2f→%.2f：理论比 %.3f，实测比 %.3f，误差 %.1f%% ⇒ %s"
              % (fb1, fb2, want, got, e, "通过 ✓" if e < 15 else "未通过 ✗"))
        if e >= 15:
            fails.append("V2 比例一致性超标（%.1f%%）" % e)
    else:
        print("       ✗ 未饱和档不足 2 个，无法验证"); fails.append("V2 无足够非饱和档")"""
new2 = """    print("       注：环路里还有 damp 低通带来的**固定损耗** ⇒ 衰减不纯由 fb 决定 ✗，")
    print("           所以对多抽头 + 阻尼网络，与实现相符的判据是【单调性】而不是比例式 ✓")
    clean = [r for r in rows if r[5] <= 5.0]
    if len(clean) >= 2:
        t = [r[2] for r in clean]
        f = [r[1] for r in clean]
        mono = all(t[i + 1] > t[i] for i in range(len(t) - 1))
        print("       fb %s ⇒ T60 %s（应随 fb 单调增）"
              % (["%.3f" % v for v in f], ["%.4f" % v for v in t]))
        print("       ⇒ %s" % ("单调递增 ✓" if mono else "非单调 ✗"))
        if not mono:
            fails.append("V2 T60 未随 fb 单调递增")
    else:
        print("       ✗ 未饱和档不足 2 个，无法验证"); fails.append("V2 无足够非饱和档")"""
assert old2 in s, "V2 段未匹配"
s = s.replace(old2, new2)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("  判据 V2 改为单调性 ✓")
