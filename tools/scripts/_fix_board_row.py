# -*- coding: utf-8 -*-
"""把任务板里被合并的一行拆回两行（第 7 轮认领时的编辑事故）。
第 92 行同时含：⑤ 认领行 + C0 彻底解决行的正文。"""
import io

p = "refs/素材库/双代理任务板.md"
lines = io.open(p, encoding="utf-8-sig").read().split("\n")
out = []
fixed = 0
for ln in lines:
    if "⑤ 电极遥测寄存器（认领开工" in ln and "真根因" in ln:
        a, b = ln.split(" | **真根因**", 1)
        row_c0 = "| ✅✅ **C0 彻底解决：三态使能必须写成寄存器（第 6 轮）** | ✅ 2026-10-03 | **真根因**" + b
        out.append(a.rstrip() + " |")
        out.append(row_c0)
        fixed += 1
    else:
        out.append(ln)
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
print("  拆分并修复的行数 = %d" % fixed)
