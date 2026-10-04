# -*- coding: utf-8 -*-
"""一次性修复：引导 FSM 的 case 标签从 5 位改成 6 位。
（b_idx 已加宽到 6 位，但 5'd32..5'd44 会溢出回绕 ⇒ 引导提前终止 ⇒ 谱 RAM 只写了前几个 ✗）"""
import io
import re

p = "src/rtl/tdm_top.v"
s = io.open(p, encoding="utf-8-sig").read()

# 只改 case 里的标签：'5'dNN: begin b_addr'
before = len(re.findall(r"5'd(\d+): begin b_addr", s))
s = re.sub(r"5'd(\d+): begin b_addr", lambda m: "6'd%s: begin b_addr" % m.group(1), s)
after = len(re.findall(r"6'd(\d+): begin b_addr", s))
io.open(p, "w", encoding="utf-8", newline="").write(s)
print("  改了 %d 条 case 标签（现在 6 位标签共 %d 条）" % (before, after))
for line in s.split("\n"):
    if "b_addr" in line and ("6'd2" in line or "6'd4" in line or "6'd3" in line):
        print("   ", line.strip()[:90])
