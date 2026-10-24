#!/usr/bin/env python3
"""run_sims.py —— 一次跑完所有仿真测试台，汇总判据

为什么需要它
------------
此前每个测试台都是手敲 iverilog/vvp 命令行，参数记在脑子里：
  · 哪个 tb 要带 vendor 桩（RAM16SDP4 / ALU54D / MAC18）
  · 哪个 tb 要在 sim_work 下跑（因为 $readmemh 走相对路径）
  · 输出必须落在 sim_work/（输出到 /tmp 会触发 iverilog 的 code generator failure）
这些都靠记忆 ⇒ 换个人、隔几天就重现不了。本脚本把它固化成一张表。

用法
----
    python tools/run_sims.py                 # 跑全部
    python tools/run_sims.py tb_rst_gen      # 只跑一个
    python tools/run_sims.py -v              # 打印完整输出

判据
----
每个 tb 自己在末尾打印 `RESULT...: PASS/FAIL`。本脚本额外把
`[FAIL]` 行数也统计进来 —— 有些 tb 打 FAIL 但没更新 RESULT 行，
只看 RESULT 会漏。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
SIM = R / 'sim'
WORK = R / 'sim_work'

IV = os.environ.get('FPGA_IVERILOG', 'D:/iverilog/bin/iverilog.exe')
VVP = os.environ.get('FPGA_VVP', 'D:/iverilog/bin/vvp.exe')

VENDOR = [R / 'tb/vendor_ram16sdp4.v', R / 'tb/vendor_alu54d.v', R / 'tb/vendor_mac18.v']

# tb 名 -> (源文件列表, 需要的 vendor 桩, 需要复制到工作目录的数据文件)
CASES = {
    'tb_rst_gen': (
        [SIM / 'tb_rst_gen.v', R / 'engine/src/rst_gen.v'],
        [], []),
    'tb_beacon': (
        [SIM / 'tb_beacon.v', R / 'engine/src/uart_beacon.v'],
        [], []),
    'tb_pad_velocity': (
        [SIM / 'tb_pad_velocity.v', R / 'engine/src/pad_scan.v'],
        VENDOR, []),
    # 必须同时编 reg_bank_compact（产品真正用的）和 reg_bank（参考模型）：
    # 只编后者的话，"0x6E 默认 0x80"会在仿真里绿、板上却是 0x00。
    'tb_vel_shape': (
        [SIM / 'tb_vel_shape.v', R / 'engine/src/vel_shape.v',
         R / 'engine/src/reg_bank_compact.v', R / 'engine/src/reg_bank.v'],
        VENDOR, ['engine/src/vel_wtab.hex']),
    'tb_pad_chain': (
        [SIM / 'tb_pad_chain.v', R / 'engine/src/pad_scan.v', R / 'engine/src/pad_pitch.v'],
        VENDOR, []),
    # 通道→力度映射（缺口 G4）：64 位 vel_bus 只装得下 16 路，而音高通道有 NPIT=25 路。
    # 只编 pad_pitch，不拉 pad_scan —— 本台要隔离"映射"这一件事，
    # 混进扫描器的话，一旦失败分不清是映射错还是采样时点错。
    'tb_pad_velmap': (
        [SIM / 'tb_pad_velmap.v', R / 'engine/src/pad_pitch.v'],
        [], []),
    # 双段衰减：只编 osc_env（无状态组合单元），不需要 vendor 桩和数据文件。
    'tb_decay2': (
        [SIM / 'tb_decay2.v', R / 'engine/src/osc_env.v'],
        [], []),
    # 激发模式：向量由 tools/gen_strike_vectors.py 从 Python 侧算出，
    # 本测试台把 RTL 的结果逐项比回去（规格 §6 验收第 8 条）。
    'tb_strike': (
        [SIM / 'tb_strike.v', R / 'engine/src/note_map_owned.v',
         R / 'engine/src/instrument_table.v', R / 'engine/src/vel_shape.v',
         R / 'engine/src/osc_env.v'],
        VENDOR,
        ['engine/src/note_inc.hex', 'engine/src/preset_part.hex',
         'engine/src/recip_inc.hex', 'engine/src/tilt_wtab.hex',
         'engine/src/vel_wtab.hex',
         'sim/strike_cases.hex', 'sim/strike_expect.hex']),
}


def run_one(name, verbose=False):
    srcs, vendor, data = CASES[name]
    for p in srcs + vendor:
        if not p.exists():
            return name, False, f'缺文件 {p}'
    WORK.mkdir(exist_ok=True)
    for d in data:
        src = R / d
        if not src.exists():
            return name, False, f'缺数据文件 {src}'
        shutil.copyfile(src, WORK / src.name)

    vvp = WORK / f'{name}.vvp'
    cmd = [IV, '-g2005', '-o', str(vvp)] + [str(p) for p in srcs + vendor]
    # 用 errors='replace'：iverilog/vvp 的输出里混着中文消息与可能的二进制
    #   （中文消息在 $display 里被截断时会切出非法 UTF-8 字节），
    #   严格解码会让整个脚本抛 UnicodeDecodeError，看起来像"仿真崩了"。
    c = subprocess.run(cmd, capture_output=True, text=True, errors='replace', cwd=str(WORK))
    if c.returncode != 0:
        return name, False, '编译失败:\n' + (c.stdout + c.stderr)[-1500:]

    # 在 sim_work 下跑：$readmemh/$dumpfile 都是相对路径
    try:
        r = subprocess.run([VVP, vvp.name], capture_output=True, text=True,
                           errors='replace', cwd=str(WORK), timeout=900)
    except subprocess.TimeoutExpired:
        return name, False, '运行超时（>900 s）'
    out = r.stdout + r.stderr

    # 判据要覆盖两种汇总风格：
    #   · tb_rst_gen / tb_beacon:  "RESULT(main): PASS"
    #   · 其余 tb:                 " PASS —— N 项检查全部通过"
    n_fail = len(re.findall(r'\[FAIL\]', out))
    has_fail = bool(re.search(r'RESULT[^:\n]*:\s*FAIL|^\s*FAIL\s*——', out, re.M))
    has_pass = bool(re.search(r'RESULT[^:\n]*:\s*PASS|^\s*PASS\s*——', out, re.M))
    ok = (n_fail == 0) and has_pass and not has_fail

    if verbose or not ok:
        return name, ok, out
    # 非 verbose 时只给判据摘要
    lines = [l for l in out.splitlines()
             if re.search(r'\[(OK|FAIL)\]|RESULT|measured|占比|结论', l)]
    return name, ok, '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('names', nargs='*', help='只跑指定的 tb')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()

    if not Path(IV).exists():
        print(f'找不到 iverilog：{IV}')
        print('  用环境变量覆盖：FPGA_IVERILOG=/path/to/iverilog')
        return 2

    names = args.names or list(CASES)
    bad = []
    for n in names:
        if n not in CASES:
            print(f'未知测试台：{n}（可选：{", ".join(CASES)}）')
            return 2
        print(f'\n{"="*70}\n== {n}\n{"="*70}')
        name, ok, text = run_one(n, args.verbose)
        print(text)
        print(f'-- {name}: {"PASS" if ok else "FAIL"}')
        if not ok:
            bad.append(name)

    print(f'\n{"="*70}')
    if bad:
        print(f'汇总: FAIL ({len(bad)}/{len(names)}) -> {", ".join(bad)}')
        return 1
    print(f'汇总: PASS ({len(names)}/{len(names)})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
