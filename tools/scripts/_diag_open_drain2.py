# -*- coding: utf-8 -*-
"""逐行给 pad 的 IO_PORT 加/去 OPEN_DRAIN=ON（C0 实验）。
用法：python tools/scripts/_diag_open_drain2.py [--off]"""
import io
import sys

p = "src/constr/tdm_top.cst"
s = io.open(p, encoding="utf-8-sig").read()
off = "--off" in sys.argv

out, n = [], 0
for line in s.split("\n"):
    if line.startswith('IO_PORT "pad['):
        t = line.rstrip()
        if off:
            t = t.replace(" OPEN_DRAIN=ON", "")
        elif "OPEN_DRAIN" not in t:
            t = t[:-1] + " OPEN_DRAIN=ON;" if t.endswith(";") else t
        n += 1
        line = t
    out.append(line)

io.open(p, "w", encoding="utf-8", newline="").write("\n".join(out))
print("  处理 pad 行数 = %d（off=%s）" % (n, off))
for line in out:
    if 'IO_PORT "pad[0]"' in line or 'IO_PORT "pad[15]"' in line:
        print("   ", line.strip())
