# -*- coding: utf-8 -*-
"""第 8 轮：把 tb_t60 的冲激幅度改成 tb_fx 的已知能工作值（2560000），
并把上一轮"满幅冲激"的 dump 另存，避免被覆盖。"""
import io
import os
import shutil

p = "src/sim/tb_t60.v"
s = io.open(p, encoding="utf-8-sig").read()

old = "din <= (s == 200) ? 24'sd4194303 : 24'sd0;"
new = "din <= (s == 200) ? 24'sd2560000 : 24'sd0;"
if old in s:
    s = s.replace(old, new)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("  冲激幅度 4194303 → 2560000（抄 tb_fx 的已知能工作值 ✓）")
elif new in s:
    print("  冲激幅度已经是 2560000 ✓")
else:
    print("  !! 未匹配，请手工检查")

# 把"满幅冲激"那批 dump 另存，保留为 V5（饱和/溢出）证据
d = "sim_build/t60"
for fb in ("40", "80", "c0", "e0"):
    src = os.path.join(d, "t60_fb%s.txt" % fb)
    dst = os.path.join(d, "sat_fb%s.txt" % fb)
    if os.path.isfile(src) and not os.path.isfile(dst):
        shutil.copy(src, dst)
        print("  另存饱和证据 %s → %s" % (os.path.basename(src), os.path.basename(dst)))
