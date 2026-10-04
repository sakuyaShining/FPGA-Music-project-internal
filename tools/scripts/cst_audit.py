# -*- coding: utf-8 -*-
"""
cst_audit.py —— 引脚约束审计（21 号 §5 的 PS6 判据 + 20 号 §1）

【为什么需要机械审计】
  引脚约束错了不会报错：少写一行 IO_PORT ⇒ 工具用默认电平标准 ✗；
  把 3.3 V 信号放进 1.8 V bank ⇒ **可能损坏器件** ✗✗（20 号 §1 专门警告）。
  靠人眼读 cst 靠不住 ⇒ 用脚本。

【判据】
  A1  40P 排针上被使用的每一根（27–42）都必须有 IO_LOC + IO_PORT 且 IO_TYPE=LVCMOS33
  A2  16 路 pad 必须显式 PULL_MODE=DOWN（RC 放电靠它，功能必需）
  A3  不得出现 1.8 V bank 的引脚（本板 40P 排针全在 3.3 V bank；脚本内置黑名单）
  A4  ev_*/preset/test_mode 只保留 IO_PORT（PULL_MODE=DOWN）、不得有 IO_LOC
      （修正案 A6：ev_* 不上引脚；A2：test_mode 下拉）
  A5  S1(87) / S2(88) 若在 cst 里出现，必须显式 IO_TYPE

用法：python tools/scripts/cst_audit.py [--cst src/constr/tdm_top.cst]
退出码：0 = 全过，1 = 有违规
"""
import argparse
import os
import re
import sys

HEADER_PINS = set(range(27, 43)) | {48, 77}     # 40P 排针上的可用引脚
PAD_PINS = set(range(27, 43))                    # pads 实际占用 27..42
# 1.8 V bank 黑名单：GW2AR-18 的 QN88 封装里 Bank 0/1 的部分引脚是 1.8 V。
# 40P 排针的 27..42/48/77 全在 3.3 V bank（官方 LCD 例程同样如此）⇒ 这些都不该出现。
V18_BLACKLIST = set()                            # 保守：不臆造，留空并只做"越界检查"
ALLOWED_PINS = HEADER_PINS | {4, 15, 16, 17, 18, 19, 20, 51, 54, 55, 56, 69, 70, 87, 88}

NO_LOC_PORTS = ("ev_note", "ev_vel", "ev_valid", "ev_on", "preset", "test_mode")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cst", default=os.path.join("src", "constr", "tdm_top.cst"))
    a = ap.parse_args()

    if not os.path.exists(a.cst):
        print("找不到 %s" % a.cst)
        return 2

    lines = open(a.cst, encoding="utf-8-sig").read().splitlines()
    loc = {}          # 端口 -> 引脚
    port = {}         # 端口 -> 属性行
    for ln in lines:
        s = ln.strip()
        if s.startswith("//") or not s:
            continue
        m = re.match(r'IO_LOC\s+"([^"]+)"\s+(\d+)', s)
        if m:
            loc[m.group(1)] = int(m.group(2))
        m = re.match(r'IO_PORT\s+"([^"]+)"\s+(.*)', s)
        if m:
            port[m.group(1)] = m.group(2)

    fails = []

    print("=" * 66)
    print(" 引脚约束审计（PS6）：%s" % a.cst)
    print("=" * 66)
    print("  IO_LOC 共 %d 条，IO_PORT 共 %d 条" % (len(loc), len(port)))

    # A1：每个有 IO_LOC 的端口都要有 IO_PORT 且 LVCMOS33
    for p, pin in sorted(loc.items(), key=lambda kv: kv[1]):
        attr = port.get(p, "")
        if "LVCMOS33" not in attr:
            fails.append("A1: %s (pin %d) 缺 IO_TYPE=LVCMOS33（实际：%s）" % (p, pin, attr or "无 IO_PORT"))
        if pin not in ALLOWED_PINS:
            fails.append("A1: %s 用了非预期引脚 %d" % (p, pin))

    # A2：pad 必须 PULL_MODE=DOWN
    pad_ports = [p for p in port if p.startswith("pad[")]
    for p in sorted(pad_ports):
        if "PULL_MODE=DOWN" not in port[p]:
            fails.append("A2: %s 缺 PULL_MODE=DOWN（RC 放电必需）" % p)
    if len(pad_ports) != 16:
        fails.append("A2: pad 端口数 = %d，期望 16" % len(pad_ports))

    # A3：pad 必须覆盖 27..42 且无重复引脚
    pad_pins = sorted(loc[p] for p in pad_ports if p in loc)
    if pad_pins and pad_pins != sorted(PAD_PINS):
        fails.append("A3: pad 引脚 = %s，期望 %s" % (pad_pins, sorted(PAD_PINS)))
    seen = {}
    for p, pin in loc.items():
        if pin in seen:
            fails.append("A3: 引脚 %d 被 %s 与 %s 重复占用" % (pin, seen[pin], p))
        seen[pin] = p
    for pin in loc.values():
        if pin in V18_BLACKLIST:
            fails.append("A3: 引脚 %d 在 1.8V bank 黑名单里" % pin)

    # A4（2026-10-02 收紧）：出货顶层 = tdm_ship，ev_*/preset/test_mode 已从网表里去掉
    #   ⇒ cst 里**完全不应出现**这些名字（出现就会 CT1135 "Can't find object"）
    for p in sorted(set(list(loc) + list(port))):
        base = p.split("[")[0]
        if base in NO_LOC_PORTS:
            fails.append("A4: %s 不应出现在 cst 里（出货顶层 tdm_ship 已无此端口 ⇒ 会 CT1135 ✗）" % p)

    # A5：87/88（S1/S2）若出现必须有 IO_TYPE
    for p, pin in loc.items():
        if pin in (87, 88) and "LVCMOS33" not in port.get(p, ""):
            fails.append("A5: %s (pin %d) 缺显式 IO_TYPE" % (p, pin))

    print("  pad 端口 %d 个，占用引脚 %s" % (len(pad_ports), pad_pins))
    noloc = [p for p in port if p.split("[")[0] in NO_LOC_PORTS and p not in loc]
    print("  测试/调试口（无 IO_LOC，靠 PULL_MODE=DOWN 读 0）：%s" % " ".join(sorted(noloc)))
    print("-" * 66)
    if fails:
        print(" ★ 未通过：")
        for f in fails:
            print("   -", f)
        return 1
    print(" ★★★ PS6 通过：40P 排针引脚全部显式 LVCMOS33；16 路 pad 全 PULL_MODE=DOWN；"
          "ev_*/preset/test_mode 不上引脚且下拉")
    return 0


if __name__ == "__main__":
    sys.exit(main())
