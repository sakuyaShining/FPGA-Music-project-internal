# -*- coding: utf-8 -*-
"""一次性：给 cst 里 16 条 pad 的 IO_PORT 加/去 OPEN_DRAIN=ON。
用法：python tools/scripts/_diag_open_drain.py [--off]"""
import io
import re
import sys

p = "src/constr/tdm_top.cst"
s = io.open(p, encoding="utf-8-sig").read()
off = "--off" in sys.argv

if off:
    s2 = s.replace("IO_TYPE=LVCMOS33 OPEN_DRAIN=ON;", "IO_TYPE=LVCMOS33;")
else:
    s2 = re.sub(r'(IO_PORT "pad\[\d+"\]\s+IO_TYPE=LVCMOS33)(;)',
                r"\1 OPEN_DRAIN=ON\2", s)

n = len(re.findall(r'IO_PORT "pad\[', s2))
print("  pad 的 IO_PORT 条数 = %d，%s OPEN_DRAIN" % (n, "去掉" if off else "加上"))
io.open(p, "w", encoding="utf-8", newline="").write(s2)

for line in s2.split("\n"):
    if 'IO_PORT "pad[0]"' in line or 'IO_PORT "pad[15]"' in line:
        print("   ", line.strip())
