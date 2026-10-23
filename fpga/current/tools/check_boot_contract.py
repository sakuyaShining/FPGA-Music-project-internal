#!/usr/bin/env python3
"""check_boot_contract.py —— 上电默认值的"引导契约"检查

为什么需要这个工具
==================
2026-10-23 板上实测发现：`reg_bank.v` 的 `initial` 块**并非对所有地址都生效**。

  重新烧录 build_prod_v3 后立刻读（引导序列不写这些地址，只有 initial 给值）：
      0x5C -> 0x70   ✓  initial 生效
      0x7F -> 0x11   ✓  initial 生效
      0x6E -> 0x00   ✗  应为 0x80
      0x6F -> 0x00   ✗  应为 0x05

  差别在于：`0x10-0x6F` 是连续 96 字节的 PITCH 区，被综合器推成独立 RAM，
  这一段的 initial 内容被丢弃；分散的单字节寄存器则正常。
  `0x6E/0x6F` 正好是这段的最后两个字节 ⇒ 成了牺牲品。

  后果（实测过）：0x6E=0 ⇒ vel_vscale=0 ⇒ 力度对音色零影响；
                  0x6F=0 ⇒ 力度只有 0/15 两档。

结论 / 契约
===========
  **凡是"上电必须有确定值"的寄存器，都必须由 tdm_top_owned.v 的引导序列写入，
    不能只依赖 reg_bank.v 的 initial。**

  引导序列是运行时写，不依赖综合器如何切分存储器。
  （已验证：0x00->0x02 / 0x40->0x01 / 0x48->0x80 三项板上全部读回正确。）

本工具做什么
============
  静态对比两处默认值来源，输出三类结果：

  [AT RISK]  initial 给了非零值，但引导序列不写  → 上电值不可信，必须在板上核
  [MISMATCH] initial 与引导序列给的值不一致       → 文档/实现矛盾
  [BOOT ONLY] 引导写、initial 没写                  → 正常（推荐写法）

用法
====
    python tools/check_boot_contract.py            # 报告
    python tools/check_boot_contract.py --strict   # 有 AT RISK 就返回非零退出码
"""
import argparse
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
REG_BANK = R / 'engine/src/reg_bank.v'
TOP = R / 'engine/src/tdm_top_owned.v'

# 板上实测表（2026-10-23，build_prod_v3，重新烧录后立刻读）
#
# 只记录"initial 给了非零值、引导序列不写"的地址，因为只有这些能判别
# initial 到底有没有被综合进去。
#
#   地址   initial  板上实测  结论
#   0x5C    0x70      0x70     initial 生效
#   0x7F    0x11      0x11     initial 生效
#   0x6E    0x80      0x00     initial **被丢弃**
#   0x6F    0x05      0x00     initial **被丢弃**
#
# 注意：起初我以为"0x10-0x6F 整段连续 RAM 都会丢"，但 0x5C 实测是对的，
# 所以这个假设**不成立**。真正的原因尚未定位（可能与综合器如何切分存储器
# 有关），因此本工具不再猜区间，只用实测数据说话。
BOARD_VERIFIED = {
    0x5C: (0x70, 'initial 生效（实测）'),
    0x7F: (0x11, 'initial 生效（实测）'),
}


def parse_initial(path):
    """reg_bank.v: mem[8'hXX] = 8'hYY;  ->  {addr: value}"""
    text = path.read_text(encoding='utf-8', errors='replace')
    out = {}
    for m in re.finditer(r"mem\[8'h([0-9A-Fa-f]{2})\]\s*=\s*8'h([0-9A-Fa-f]{2})\s*;", text):
        out[int(m.group(1), 16)] = int(m.group(2), 16)
    # for 循环把整片清零：未被上面覆盖的地址默认 0
    if re.search(r'for\s*\(\s*i\s*=\s*0\s*;\s*i\s*<\s*NW', text):
        for a in range(0x00, 0x80):
            out.setdefault(a, 0)
    return out


def parse_boot(path):
    """tdm_top_owned.v 引导序列: b_addr <= 8'hXX; b_data <= 8'hYY;  ->  {addr: value}"""
    text = path.read_text(encoding='utf-8', errors='replace')
    out = {}
    # 一条 case 分支可能跨行，先按 begin/end 粗切
    for m in re.finditer(
            r"b_addr\s*<=\s*8'h([0-9A-Fa-f]{2})\s*;\s*b_data\s*<=\s*8'h([0-9A-Fa-f]{2})",
            text):
        a, v = int(m.group(1), 16), int(m.group(2), 16)
        # 同一地址出现多次时，后写的生效（引导里 0x59 写了 16 次）
        out[a] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true',
                    help='有 AT RISK 项时返回非零退出码')
    args = ap.parse_args()

    if not REG_BANK.exists() or not TOP.exists():
        print(f'找不到源文件：{REG_BANK} / {TOP}')
        return 2

    ini = parse_initial(REG_BANK)
    boot = parse_boot(TOP)

    at_risk, mismatch, boot_only, verified = [], [], [], []

    for a in sorted(set(ini) | set(boot)):
        iv, bv = ini.get(a), boot.get(a)
        if iv not in (None, 0) and bv is None:
            if a in BOARD_VERIFIED and BOARD_VERIFIED[a][0] == iv:
                verified.append((a, iv, BOARD_VERIFIED[a][1]))
            else:
                at_risk.append((a, iv))
        elif iv is not None and bv is not None and iv != bv:
            mismatch.append((a, iv, bv))
        elif bv is not None and iv in (None, 0):
            boot_only.append((a, bv))

    print(f'reg_bank initial 覆盖 {len(ini)} 个地址；引导序列写 {len(boot)} 个地址\n')

    if at_risk:
        print(f'[AT RISK] {len(at_risk)} 项 —— initial 有非零值、引导不写、且未在板上验证：')
        for a, v in at_risk:
            print(f'    0x{a:02X} = 0x{v:02X}    ← 上电值不可信，请在板上读一次')
        print('    修法：把这一项加进 tdm_top_owned.v 的引导序列（b_idx case）。\n')
    else:
        print('[AT RISK] 无 —— 所有非零默认值要么由引导序列写入，要么已板上验证\n')

    if verified:
        print(f'[VERIFIED] {len(verified)} 项 —— initial 非零、引导不写，但板上实测正确：')
        for a, v, why in verified:
            print(f'    0x{a:02X} = 0x{v:02X}    {why}')
        print()

    if mismatch:
        print(f'[MISMATCH] {len(mismatch)} 项 —— initial 与引导序列不一致：')
        for a, iv, bv in mismatch:
            print(f'    0x{a:02X}  initial=0x{iv:02X}  引导=0x{bv:02X}')
        print()
    else:
        print('[MISMATCH] 无\n')

    if boot_only:
        print(f'[BOOT ONLY] {len(boot_only)} 项 —— 由引导序列定义（推荐写法）：')
        for a, v in boot_only[:8]:
            print(f'    0x{a:02X} = 0x{v:02X}')
        if len(boot_only) > 8:
            print(f'    ... 另有 {len(boot_only) - 8} 项')
        print()

    if at_risk and args.strict:
        print('结论: FAIL（--strict 下 AT RISK 视为失败）')
        return 1
    print('结论: PASS' if not at_risk else '结论: 需人工确认 AT RISK 项')
    return 0


if __name__ == '__main__':
    sys.exit(main())
