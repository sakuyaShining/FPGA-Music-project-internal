# -*- coding: utf-8 -*-
"""一次性：给 cst 里 16 条 pad 的 IO_PORT 加回 PULL_MODE=DOWN（RC 放电必需）。
用法：python tools/scripts/_diag_pull_mode.py [--off]"""
import io
import re
import sys

p = "src/constr/tdm_top.cst"
s = io.open(p, encoding="utf-8-sig").read()
off = "--off" in sys.argv

if off:
    s2 = re.sub(r'(IO_PORT "pad\[\d+"\]\s+IO_TYPE=LVCMOS33)\s+PULL_MODE=DOWN(;)', r"\1\2", s)
else:
    s2 = re.sub(r'(IO_PORT "pad\[\d+"\]\s+IO_TYPE=LVCMOS33)(;)', r"\1 PULL_MODE=DOWN\2", s)

# 去掉可能残留的 OPEN_DRAIN（本试验不掺它）
s2 = s2.replace("IO_TYPE=LVCMOS33 OPEN_DRAIN=ON;", "IO_TYPE=LVCMOS33;")

n = len(re.findall(r'IO_PORT "pad\[\d+"\]', s2))
k = len(re.findall(r'IO_PORT "pad\[\d+"\]\s+IO_TYPE=LVCMOS33 PULL_MODE=DOWN;', s2))
print("  pad 条数 = %d，其中带 PULL_MODE=DOWN 的 = %d" % (n, k))
io.open(p, "w", encoding="utf-8", newline="").write(s2)
for line in s2.split("\n"):
    if 'IO_PORT "pad[0]"' in line or 'IO_PORT "pad[15]"' in line:
        print("   ", line.strip())
