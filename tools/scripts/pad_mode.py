# -*- coding: utf-8 -*-
"""
pad_mode.py —— 一键切换 16 路电极的端口模式（C0 实验用，可复现）

背景（见 refs/素材库/步骤16_上板风险审计.md §2c）：
  · pad = inout 三态   ⇒ Gowin 报 PR0004 "86 unrouted nets" ⇒ 出不了码流 ✗
  · pad = input 纯输入 ⇒ 正常出码流 ✓，但硬件上电极无法充放电 ✗
本脚本让这两种状态可以**一键来回切**，并为"三态能不能救活"的后续实验服务。

用法：
  python tools/scripts/pad_mode.py --inout     # 三态（充/放/读同一根线）
  python tools/scripts/pad_mode.py --input     # 纯输入（临时可出码流状态）
  python tools/scripts/pad_mode.py --show      # 只打印当前状态
"""
import io
import re
import sys

FILES = {
    "src/rtl/tdm_top.v":   ('    inout  wire [15:0] pad', '    input  wire [15:0] pad'),
    "src/rtl/tdm_ship.v":  ('    inout  wire [15:0] pad', '    input  wire [15:0] pad'),
}
PAD_SCAN = "src/rtl/pad_scan.v"
PS_INOUT = '    inout  wire [NCH-1:0]      pad,'
PS_INPUT = '    input  wire [NCH-1:0]      pad,'
# ★★ C0 的真正修法（2026-10-03 实测）：三态必须用【寄存器使能】！！
#    组合推断的三态 ⇒ Gowin 报 PR0004 "86 unrouted nets" ⇒ 出不了码流 ✗
#    把使能做成一拍寄存器 ⇒ 完整 PnR 成功、出 .fs ✓✓（见 步骤16 §2c 的完整排除链）
DRV_REG = """    // ★★ C0 关键修法：三态的【使能必须是寄存器】！
    //    Gowin 的 IOBUF 内置输出使能寄存器；用组合逻辑推断三态时，
    //    布局布线会报 PR0004 "86 unrouted nets" ⇒ 出不了码流 ✗✗
    //    （已排除：组合三态 ✗、+OPEN_DRAIN ✗、+寄存器表瘦身 ✗ ⇒ 只有寄存器使能 ✓）
    reg pad_drv_en;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) pad_drv_en <= 1'b0;
        else        pad_drv_en <= (st == S_CHG);
    assign pad = pad_drv_en ? {NCH{1'b1}} : {NCH{1'bz}};"""
DRV_LINE = "    assign pad = (st == S_CHG) ? {NCH{1'b1}} : {NCH{1'bz}};"


def read(p):
    return io.open(p, encoding="utf-8-sig").read()


def write(p, s):
    io.open(p, "w", encoding="utf-8", newline="").write(s)


def set_ports(mode):
    """mode: 'inout' | 'input'；同时把 pad_scan 的端口与驱动赋值一起摆好"""
    for path, (a, b) in FILES.items():
        s = read(path)
        # 用正则吃掉中间任意空白与可能残留的注释
        s = re.sub(r'^\s*(inout|input)\s+wire \[15:0\] pad\s*$',
                   ('    inout  wire [15:0] pad' if mode == 'inout'
                    else '    input  wire [15:0] pad'), s, flags=re.M)
        write(path, s)

    s = read(PAD_SCAN)
    s = re.sub(r'^\s*(inout|input)\s+wire \[NCH-1:0\]\s+pad,.*$',
               ('    inout  wire [NCH-1:0]      pad,     // 电极：充/放/读同一根线'
                if mode == 'inout' else
                '    input  wire [NCH-1:0]      pad,     // [临时] 纯输入：三态会让 PnR 布不通'),
               s, flags=re.M)

    # ★ 先把【整段】电极驱动（含可能残留的注释/重复块）压成一个规范块，
    #   再按模式决定留“寄存器使能版”还是“注释停用版”。这样来回切不会累积碎片 ✓
    drv_re = re.compile(
        r'(?:^[ \t]*//[^\n]*\n|[ \t]*\n)*'
        r'^[ \t]*//[^\n]*C0[^\n]*\n(?:^[ \t]*//[^\n]*\n)*'
        r'^[ \t]*(?:reg pad_drv_en;|//[ \t]*reg pad_drv_en;)\n'
        r'(?:^[ \t]*//[^\n]*\n)*'
        r'^[ \t]*always @\(posedge clk or negedge rst_n\)\n'
        r'^[ \t]*if \(!rst_n\) pad_drv_en <= 1\'b0;\n'
        r'^[ \t]*else[ \t]+pad_drv_en <= \(st == S_CHG\);\n'
        r'(?:^[ \t]*//[ \t]*assign pad[^\n]*\n|^[ \t]*assign pad[^\n]*\n)',
        re.M)

    if mode == 'inout':
        s2, n = drv_re.subn(DRV_REG + "\n", s)
        if n == 0:
            # 退路：只有一行被注释的 assign
            s2 = re.sub(r'^[ \t]*//[ \t]*assign pad[^\n]*$', DRV_REG, s, count=1, flags=re.M)
            n = 1
    else:
        s2, n = drv_re.subn(
            "    // [临时] 三态停用：纯输入状态下不能驱动电极。\n"
            "    // 恢复：python tools/scripts/pad_mode.py --inout （会写回寄存器使能版 ✓）\n"
            "    // " + DRV_LINE.strip() + "\n", s)
        if n == 0:
            s2 = re.sub(r'^[ \t]*assign pad[^\n]*$',
                        "    // " + DRV_LINE.strip(), s, count=1, flags=re.M)
            n = 1

    write(PAD_SCAN, s2)
    print("  电极驱动段替换块数 = %d" % n)


def show():
    for path in list(FILES) + [PAD_SCAN]:
        s = read(path)
        for line in s.split("\n"):
            if re.match(r'^\s*(inout|input)\s+wire \[(15:0|NCH-1:0)\]', line):
                print("  %-22s %s" % (path.split("/")[-1], line.strip()))
            if "assign pad" in line or ("// assign pad" in line):
                print("  %-22s %s" % (path.split("/")[-1], line.strip()))


if __name__ == "__main__":
    if "--show" in sys.argv:
        show()
    elif "--inout" in sys.argv:
        set_ports("inout")
        print("  已切到【三态 inout】")
        show()
    elif "--input" in sys.argv:
        set_ports("input")
        print("  已切到【纯输入 input】")
        show()
    else:
        print(__doc__)
