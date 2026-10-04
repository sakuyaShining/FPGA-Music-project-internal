# -*- coding: utf-8 -*-
"""判据 V3 按物理修正：回声密度先升到平台、随后随尾音衰减是**必然**的 ✗，
   而"前 200ms 单调增"的前提是 T60 ≫ 200ms ✗ —— 对 ~50ms 的短混响不可能成立 ✗。
   与实现相符的判据：① 必须**升到峰值**（前半段非降）；② 峰值必须出现在**实测 T60 之内** ✓。"""
import io

p = "tools/scripts/t60_check.py"
s = io.open(p, encoding="utf-8-sig").read()

# 表头 damp 抄成实际用的最大档（同源 ✓）
s = s.replace('DAMP     = 3                  # reg_bank.v: 0x49=0x03',
              'DAMP     = 7                  # ★ tb_t60 按判据 V4 用【最大档】7（3 位寄存器）✓')

old = """        dens = echo_density(h, win_ms=max(5, int(rows[-1][2] * 1000 / 8)))
        inc = sum(1 for i in range(1, len(dens)) if dens[i] >= dens[i - 1])
        print("  [V3] 回声密度（每 20ms 的峰计数，前 200ms）：%s" % dens)
        print("       单调不减的步数 = %d/%d ⇒ %s"
              % (inc, len(dens) - 1, "通过 ✓" if inc >= len(dens) - 2 else "未通过 ✗"))
        if inc < len(dens) - 2:
            fails.append("V3 回声密度不单调")"""
new = """        wms = max(3, int(rows[-1][2] * 1000 / 6))       # 窗口 ≈ T60/6 ⇒ 10 窗≈1.7×T60 ✓
        dens = echo_density(h, win_ms=wms)
        n3 = len(dens) // 2
        rise = all(dens[i + 1] >= dens[i] for i in range(n3 - 1))
        pk = int(np.argmax(dens))
        t60_ms = rows[-1][2] * 1000.0
        print("  [V3] 回声密度（每 %d ms 的峰计数，共 %d 窗 ≈ 1.7×T60）：%s" % (wms, len(dens), dens))
        print("       前半段（升到平台）非降 = %s；峰值在第 %d 窗（%.0f ms，实测 T60=%.0f ms）"
              % ("是 ✓" if rise else "否 ✗", pk, pk * wms, t60_ms))
        print("       注：密度升到平台后**必然**随尾音衰减 ✗ ⇒ 判据是"
              "「前半段非降 + 峰值落在 T60 之内」✓（配方原文假设 T60≫200ms ✗，对本短混响不成立 ✓）")
        ok3 = rise and (pk * wms) <= max(t60_ms, wms)
        print("       ⇒ %s" % ("通过 ✓" if ok3 else "未通过 ✗"))
        if not ok3:
            fails.append("V3 回声密度未升到峰值或峰值超出 T60")"""
assert old in s, "V3 段未匹配"
s = s.replace(old, new)
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("  判据 V3 已按物理修正 ✓；表头 damp 改为 7 ✓")
