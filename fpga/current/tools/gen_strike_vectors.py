#!/usr/bin/env python3
"""gen_strike_vectors.py —— 生成 strike 激发模式的【跨语言一致性】向量

为什么要这个文件
----------------
strike 的梯度公式在两处实现：
    · Python：`articulation_v2.part_ms()` / `exp_steps()`  ← 上位机 GUI 用它显示时长
    · Verilog：`note_map_owned.v` 的 k_curve_off / strike_d_k + `osc_env.v` 的衰减推进
`>>4` 和"钳到 0"只要有一处写错，GUI 显示 340 ms、板子发出 3.4 ms —— 差一个数量级，
而且两边各自的单元测试都会是绿的（因为它们只跟自己比）。

本脚本用 Python 算出**期望值**写进 hex，Verilog 测试台读 hex 逐项比对。
这就是规格 §6 验收第 8 条的机器化版本。

产出
----
sim/strike_cases.hex   每个 case 一行，128 位：
    [127:112] base   [111:96] curve   [95:80] d_m
    [79:64]   s_lvl  [63:48]  k       [47:0]  0
sim/strike_expect.hex  与 cases 逐行对应，128 位：
    [127:112] d_k    [111:96] s_lvl_q15
    [95:80]   steps_to_0    （衰减到 0 需要多少拍）
    [79:64]   steps_to_slvl （衰减到余音电平需要多少拍）
    [63:0]    0

用法
----
    python tools/gen_strike_vectors.py          # 写文件
    python tools/gen_strike_vectors.py --check  # 只校验当前文件是否最新（CI 用）
"""
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R))

from articulation_v2 import PART, exp_steps          # noqa: E402


# (base, curve, d_m, s_lvl) —— 覆盖：推荐默认、无梯度、强梯度、钳位、
#   极短、极长、余音最大、m=1、m=2
CASES = [
    (14, 10, 3,  2),   # 规格推荐默认
    (14,  8, 3,  0),   # §2.3 实测表第一行（无余音）
    (14, 12, 3,  2),   # §2.3 实测表第二行
    (12,  8, 3,  2),   # §2.3 实测表第三行
    (10,  8, 3,  0),   # §2.3 实测表第四行
    ( 5, 15, 3,  2),   # 强梯度 ⇒ k≥6 全部钳到 0
    ( 0,  0, 1,  0),   # 最短：d_k=0 ⇒ 1 拍
    (31,  0, 2,  4),   # 最长 base、无梯度、m=2
    (20, 15, 3, 15),   # 余音最大（15/16）
    (14, 10, 1,  2),   # m=1
]


def dk_of(base, curve, k):
    """与 note_map_owned.v 的 `k_curve_off = (k*curve)>>4; d_k = max(0, base-off)` 一致。"""
    return max(0, base - ((k * curve) >> 4))


def slvlq15(s_lvl, k):
    """与 RTL 的 `has_tail = (k<4) && s_lvl!=0; q15 = s_lvl<<11` 一致。"""
    return (s_lvl << 11) if (k < 4 and s_lvl != 0) else 0


def build():
    cases, expect = [], []
    for base, curve, d_m, s_lvl in CASES:
        for k in range(PART):
            d_k = dk_of(base, curve, k)
            q15 = slvlq15(s_lvl, k)
            cases.append((base << 112) | (curve << 96) | (d_m << 80)
                         | (s_lvl << 64) | (k << 48))
            expect.append((d_k << 112) | (q15 << 96)
                          | (exp_steps(0, d_m, d_k) << 80)
                          | (exp_steps(q15, d_m, d_k) << 64))
    return cases, expect


def render(values, pad=256):
    """每行一个 128 位字。**补零到固定长度**：iverilog 的 $readmemh 在文件行数
    少于数组时会给一条 "Not enough words" 警告，噪声会淹没真正的判据；
    而补零后测试台用"最后一个非零行"来数条数，两端都能自适应。"""
    lines = ['%032x\n' % v for v in values]
    lines += ['%032x\n' % 0] * (pad - len(values))
    return ''.join(lines)


def main():
    cases, expect = build()
    assert len(cases) <= 256, '向量超过 256 条，测试台的数组要一起改'
    out_c = R / 'sim' / 'strike_cases.hex'
    out_e = R / 'sim' / 'strike_expect.hex'
    tc, te = render(cases), render(expect)

    if '--check' in sys.argv:
        ok = (out_c.exists() and out_c.read_text() == tc
              and out_e.exists() and out_e.read_text() == te)
        print('strike 向量: %s (%d 条)' % ('一致' if ok else '已过期，请重跑生成器', len(cases)))
        return 0 if ok else 1

    out_c.write_text(tc)
    out_e.write_text(te)
    print('写入 %s / %s，共 %d 条' % (out_c.name, out_e.name, len(cases)))

    # 顺手把推荐默认值的完整 16 泛音表打出来（和规格 §2.3 的表对一遍）
    print('\nbase=14 curve=10 d_m=3 s_lvl=2 的 16 泛音表：')
    for k in range(PART):
        d_k = dk_of(14, 10, k)
        q15 = slvlq15(2, k)
        ms = exp_steps(q15, 3, d_k) * 1000 / (27000000 / 512)
        print('  k=%2d  d_k=%2d  s_lvl=%5d  %7.1f ms' % (k, d_k, q15, ms))
    return 0


if __name__ == '__main__':
    sys.exit(main())
