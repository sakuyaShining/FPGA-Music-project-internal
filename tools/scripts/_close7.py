# -*- coding: utf-8 -*-
"""第 10 轮收尾：① 删掉挂账清单里被取代的旧 ⑥（第 8 轮版）；② 任务板 ⑦ 销账。"""
import io

# ---------- ① 删旧的 ⑥ 段（从 '### 🔴 **⑥ 混响 T60 取证：V2/V3/V4 通过' 到下一个 '### '）----------
p = "refs/素材库/未验证与挂账清单.md"
lines = io.open(p, encoding="utf-8-sig").read().split("\n")
out, skipping = [], False
for ln in lines:
    if ln.startswith("### 🔴 **⑥ 混响 T60 取证："):
        skipping = True
        print("  删除旧 ⑥ 段起始行", ln[:40])
        continue
    if skipping:
        if ln.startswith("### "):
            skipping = False
        else:
            continue
    out.append(ln)
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))

# ---------- ② 任务板 ⑦ → 销账 ----------
p = "refs/素材库/双代理任务板.md"
s = io.open(p, encoding="utf-8-sig").read()
old = "| 🔄 **⑦ 混响两缺陷：D1/D2 已修 ✓，但 FX 判据待更新 ⇒ 未销账（第 9 轮）** | 🔄 **未销账** |"
new = ("| ✅ **⑦ 混响两缺陷（D1 湿声电平差 42 dB / D2 默认档饱和）已修并销账（第 9–10 轮）** "
       "| ✅ 2026-10-03 |")
if old in s:
    s = s.replace(old, new)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("  任务板 ⑦ 已标记销账 ✓")
else:
    print("  !! 任务板 ⑦ 未匹配，请手工检查")
