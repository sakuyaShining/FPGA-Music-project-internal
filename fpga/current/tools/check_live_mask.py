#!/usr/bin/env python3
"""check_live_mask.py —— 检查"逻辑读的寄存器"是否都在 REG_LIVE_MASK 里

为什么需要这个工具
==================
`reg_bank_compact.v` 里有两套存储，**它们的作用完全不同**：

  · `mem[0:127]`  —— 只服务【回读】（rd_data）。任何地址 < 0x80 的写入都会进这里。
  · `value`       —— 只服务【逻辑】（regs_flat），**仅当 FLAT_MASK[g] = 1 才存在**。
                     未选中的字节 regs_flat 恒为 0（UNUSED 分支 assign 0）。

于是有一个非常隐蔽的失效模式：

  上位机写 0xXX → mem 收到 → 回读正确 → 上位机以为配好了
                 但 FLAT_MASK[0xXX] = 0 → 逻辑侧永远是 0 → 配置完全无效

**回读正确 ≠ 配置生效。** 2026-10-23 板上实测踩到的就是这个：
`0x6F` VEL_SHIFT 不在 mask 里，`selftest` 显示 `0x6F = 0x05` 全绿，
但 `r_vel_shift` 恒为 0，力度只有 0/15 两档。

本工具做什么
============
  1. 从 tdm_top_owned.v 解析 REG_LIVE_MASK
  2. 抓出所有 `R[8'hXX*8 +: N]` 形式的读取（即逻辑真正消费的地址）
  3. 报告【被读取但不在 mask 里】的地址 —— 这些读取恒为 0

用法
====
    python tools/check_live_mask.py
    python tools/check_live_mask.py --strict   # 有问题就返回非零
"""
import argparse
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
TOP = R / 'engine/src/tdm_top_owned.v'
TB = R / 'sim/tb_vel_shape.v'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()

    if not TOP.exists():
        print(f'找不到 {TOP}')
        return 2

    text = TOP.read_text(encoding='utf-8', errors='replace')

    m = re.search(r"REG_LIVE_MASK\s*=\s*128'h([0-9a-fA-F]+)", text)
    if not m:
        print('解析不到 REG_LIVE_MASK')
        return 2
    mask_val = int(m.group(1), 16)
    live = [(mask_val >> i) & 1 for i in range(128)]

    # 所有形如 R[8'hXX*8 +: N] 的读取
    reads = {}
    for mm in re.finditer(r"R\[\s*8'h([0-9A-Fa-f]{2})\s*\*\s*8\s*\+:\s*(\d+)\s*\]", text):
        addr, width = int(mm.group(1), 16), int(mm.group(2))
        # 记录首次出现的行号，方便定位
        line = text[:mm.start()].count('\n') + 1
        reads.setdefault(addr, []).append((width, line))

    print(f'REG_LIVE_MASK 覆盖 {sum(live)} 个字节；逻辑侧共读取 {len(reads)} 个地址\n')

    dead = sorted(a for a in reads if not live[a])
    alive = sorted(a for a in reads if live[a])

    if dead:
        print(f'[DEAD READ] {len(dead)} 个地址被逻辑读取，但不在 REG_LIVE_MASK 里：')
        print('            ⇒ regs_flat 恒为 0，这些读取拿到的永远是 0')
        for a in dead:
            spots = ', '.join(f'L{l}({w}位)' for w, l in reads[a])
            print(f'    0x{a:02X}  读取位置 {spots}')
        print()
        print('            修法：把该地址加进 tdm_top_owned.v 的 REG_LIVE_MASK')
        print('            （按位加，注意 mask 是 128 位、bit g 对应地址 g）')
        print()
    else:
        print('[DEAD READ] 无 —— 逻辑读取的每个地址都是活的\n')

    print(f'[ALIVE] {len(alive)} 个地址：' + ' '.join(f'0x{a:02X}' for a in alive))

    # 顺带提示：mask 里有、但没人读的字节（不是错误，只是信息）
    idle = sorted(a for a in range(128) if live[a] and a not in reads)
    if idle:
        print(f'\n[LIVE BUT UNREAD] {len(idle)} 个地址在 mask 里但逻辑没读：'
              + ' '.join(f'0x{a:02X}' for a in idle))
        print('            （正常：有些字节是给别的模块或回读用的）')

    #-------------------------------------------------------------------------
    # 仿真侧的一致性：tb_vel_shape 里有一份 LIVE 常量副本。
    # 它必须与 RTL 的 REG_LIVE_MASK 逐位一致，否则仿真测的是另一套 mask，
    # 判据就失效了（这正是 2026-10-23 那个 bug 的另一种形态）。
    #-------------------------------------------------------------------------
    if TB.exists():
        tbt = TB.read_text(encoding='utf-8', errors='replace')
        tm = re.search(r"localparam\s*\[127:0\]\s*LIVE\s*=\s*128'h([0-9a-fA-F]+)", tbt)
        if not tm:
            print('\n[SYNC] tb_vel_shape.v 里找不到 LIVE 常量 —— 无法核对一致性')
        else:
            tb_val = int(tm.group(1), 16)
            if tb_val != mask_val:
                print(f'\n[SYNC MISMATCH] tb_vel_shape 的 LIVE 与 RTL 的 REG_LIVE_MASK 不一致：')
                print(f'    RTL  = {mask_val:032x}')
                print(f'    tb   = {tb_val:032x}')
                diff = [f'0x{i:02X}' for i in range(128) if ((mask_val ^ tb_val) >> i) & 1]
                print(f'    差异地址: {" ".join(diff)}')
                dead.append(-1)   # 让 --strict 也失败
            else:
                print(f'\n[SYNC] tb_vel_shape 的 LIVE 与 RTL 一致（{mask_val:032x}）')

    if dead and args.strict:
        print('\n结论: FAIL')
        return 1
    print('\n结论: PASS' if not dead else '\n结论: 有 DEAD READ，见上')
    return 0


if __name__ == '__main__':
    sys.exit(main())
