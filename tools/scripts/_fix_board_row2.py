# -*- coding: utf-8 -*-
"""拆开任务板里被合并的行：⑤ 完成行 与 ⑦ 认领行（第 9 轮编辑事故）"""
import io

p = "refs/素材库/双代理任务板.md"
lines = io.open(p, encoding="utf-8-sig").read().split("\n")
out, fixed = [], 0
for ln in lines:
    if "⑦ 处置 V5 缺陷" in ln and "⑤ 电极遥测寄存器完成" in ln:
        # 该行形如： | 🔄 **⑦ ...** | 🔄 | <⑦正文> <⑤正文> |
        head, rest = ln.split("⑤ 电极遥测寄存器完成（第 7 轮）** | ✅ 2026-10-03 |", 1)
        row5 = "| ✅ **⑤ 电极遥测寄存器完成（第 7 轮）** | ✅ 2026-10-03 |" + rest
        out.append(head.rstrip() + " |")
        out.append(row5)
        fixed += 1
    else:
        out.append(ln)
io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
print("  修复行数 = %d" % fixed)
