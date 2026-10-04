# -*- coding: utf-8 -*-
"""一次性诊断脚本：把 pad 从 inout 改成 input，验证"三态缓冲区是否导致布不通"。
用完即删（或反向运行 --revert 恢复）。"""
import io
import sys

REVERT = "--revert" in sys.argv

EDITS = [
    ("src/rtl/tdm_top.v", "inout  wire [15:0] pad", "input  wire [15:0] pad"),
    ("src/rtl/tdm_ship.v", "inout  wire [15:0] pad", "input  wire [15:0] pad"),
    ("src/rtl/pad_scan.v",
     "inout  wire [NCH-1:0]      pad,          // 电极：充/放/读 同一根线",
     "input  wire [NCH-1:0]      pad,          // [诊断] 纯输入"),
    ("src/rtl/pad_scan.v",
     "    assign pad = (st == S_CHG) ? {NCH{1'b1}} : {NCH{1'bz}};",
     "    // [诊断] input 模式下不能驱动电极"),
]

for path, old, new in EDITS:
    if REVERT:
        old, new = new, old
    s = io.open(path, encoding="utf-8-sig").read()
    if old in s:
        s = s.replace(old, new)
        io.open(path, "w", encoding="utf-8", newline="").write(s)
        print("  %s %s" % ("还原" if REVERT else "改", path))
    else:
        print("  !! %s 未匹配：%s" % (path, old[:40]))
