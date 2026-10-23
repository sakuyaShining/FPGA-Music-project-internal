#!/usr/bin/env python3
"""gen_compact_defaults.py —— 从 reg_bank.v 的 initial 生成 reg_bank_compact 的 DEFAULTS

为什么需要它
============
上电默认值有【两处实现】，而产品顶层只例化后者：

    reg_bank.v            initial begin mem[8'hXX] = 8'hYY; ... end   ← 可读、有注释
    reg_bank_compact.v    localparam [1023:0] DEFAULTS = 1024'h...;   ← 一个 256 字符的字面量

两处不同步的后果，本项目已经踩过一次：
    0x6E 在 reg_bank.v 里改成 0x80，板上读回仍然是 0x00 ——
    因为产品顶层根本没例化 reg_bank，改错了模块。
（另一层坑：0x6E/0x6F 曾经连 DEFAULTS 都没写，只靠 initial，
  而那段被综合器推成 RAM 后 initial 被丢弃 —— 所以**引导序列**才是最终保险。）

本工具把"唯一可读的真相"钉在 reg_bank.v，DEFAULTS 变成生成物：
    python tools/gen_compact_defaults.py           # 重新生成并就地改写
    python tools/gen_compact_defaults.py --check   # 只校验（CI/提交前跑）

解析规则：只认 `mem[8'hXX] = 8'hYY;` 这一种写法（reg_bank.v 里全部如此）。
其它写法（循环赋 0）忽略 —— 未列出的地址默认 0，与 reg_bank 的行为一致。
"""
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
REG_BANK = R / 'engine/src/reg_bank.v'
COMPACT = R / 'engine/src/reg_bank_compact.v'

PAT = re.compile(r"mem\[\s*8'h([0-9A-Fa-f]{2})\s*\]\s*=\s*8'h([0-9A-Fa-f]{2})\s*;")


def read_table():
    text = REG_BANK.read_text(encoding='utf-8')
    table = {}
    for m in PAT.finditer(text):
        addr, val = int(m.group(1), 16), int(m.group(2), 16)
        if addr in table and table[addr] != val:
            raise SystemExit('reg_bank.v 里 0x%02X 被赋了两个不同的值' % addr)
        table[addr] = val
    return table


def render(table):
    """128 字节 → 1024 位 → 256 个十六进制字符（高位在前）。"""
    value = 0
    for addr, val in table.items():
        value |= val << (addr * 8)
    return '%0256x' % value


def main():
    table = read_table()
    want = render(table)
    text = COMPACT.read_text(encoding='utf-8')
    m = re.search(r"localparam \[1023:0\] DEFAULTS\s*=\s*1024'h([0-9A-Fa-f]{256})\s*;", text)
    if not m:
        raise SystemExit('在 reg_bank_compact.v 里找不到 DEFAULTS = 1024\'h<256 hex>;')

    if '--check' in sys.argv:
        ok = m.group(1).lower() == want
        print('reg_bank_compact DEFAULTS: %s（%d 个非零字节）'
              % ('一致' if ok else '与 reg_bank.v 不一致，请重跑生成器', len(table)))
        if not ok:
            for i in range(128):
                got = int(m.group(1)[-(i * 2 + 2):-(i * 2) or None] or '0', 16) if i else int(m.group(1)[-2:], 16)
                exp = table.get(i, 0)
                if got != exp:
                    print('   0x%02X  DEFAULTS=0x%02X  reg_bank=0x%02X' % (i, got, exp))
        return 0 if ok else 1

    text = text[:m.start(1)] + want + text[m.end(1):]
    COMPACT.write_text(text, encoding='utf-8')
    print('已写入 %s（%d 个非零字节）' % (COMPACT.name, len(table)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
