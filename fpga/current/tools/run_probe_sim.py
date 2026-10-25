#!/usr/bin/env python3
"""run_probe_sim.py —— EEPROM 探针的差分仿真驱动

为什么不是一个普通的"跑一下测试台"
------------------------------------
eeprom_probe/tb/tb_ack_last.v 要证明的是**缺陷存在**，不是"一切正常"。
所以它的通过条件不是"全绿"，而是：

    · 基线（队友原样的 cfg_eeprom_store.v）  → 必须红，且必须红在 4 条特定判据上
    · 变异（末字节改回 NACK）                → 必须全绿

只跑基线会得到一个"红"，无法区分"抓到真缺陷"和"测试台自己坏了"；
只跑变异会得到一个"绿"，无法区分"实现正确"和"判据根本没测到东西"。
两个一起跑，结论才闭合。这与 TEST-REGISTRY.md §3 记的三条教训是同一件事。

同时它还会用 tools/eeprom_capture_decode.py 把仿真导出的捕获解一遍，
确认解码器对**真 RTL 的行为**能给出正确结论（而不是只会解手搓样本）。

用法
----
    python tools/run_probe_sim.py            # 跑全套差分
    python tools/run_probe_sim.py -v         # 打印测试台完整输出

退出码
------
    0  差分结论符合预期（基线红在 4 条、变异全绿、解码器两路都对）
    1  有不符合预期的地方（此时才是真的要看）
    2  环境问题（找不到 iverilog / 源文件）
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent          # fpga/current
PROBE = R / 'eeprom_probe'
TB = PROBE / 'tb' / 'tb_ack_last.v'
MODEL = PROBE / 'tb' / 'ee24lc256.v'
CFG = PROBE / 'cfg_eeprom_store.v'
WORK = PROBE / 'sim_work'
DECODE = R / 'tools' / 'eeprom_capture_decode.py'

IV = os.environ.get('FPGA_IVERILOG', 'D:/iverilog/bin/iverilog.exe')
VVP = os.environ.get('FPGA_VVP', 'D:/iverilog/bin/vvp.exe')

# cfg_eeprom_store.v 必须是队友那份的原样拷贝。它一变，抓到的波形就不再是
# "他的代码在真芯片上的行为"，而是"我们改过的版本"——证据就失效了。
CFG_SHA = 'ce40c936c63f09e7dee182884d4abaa7994834388396155c21144ffd65fe931b'

# 基线必须红的 4 条（顺序即输出顺序）
BASE_MUST_FAIL = [
    '[FAIL] ACK      = 58，期望 57',
    '[FAIL] NACK     = 0，期望 1',
    '[FAIL] lastNACK = 0，期望 1',
    '[FAIL] STOP     = 1，期望 2',
]
# 变异必须全绿
MUT_MUST_PASS = [
    'ACK      = 57  OK',
    'NACK     = 1  OK',
    'lastNACK = 1  OK',
    '判据 7 项，失败 0 项',
]
# 解码器对两路捕获的结论
DEC_A_MUST = ['ACK×58  NACK×0  末字节=ACK', '有 STOP']
DEC_B_MUST = ['**没有 STOP']

MUT_OLD = "2'd0: begin sda_lo <= 1'b1; ph <= 2'd1; end           // 主机 ACK：拉低 SDA"
MUT_NEW = ("2'd0: begin sda_lo <= (rx_idx == rx_len - 8'd1) ? 1'b0 : 1'b1; "
           "ph <= 2'd1; end  // 末字节 NACK")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def compile_run(cfg, tag, rundir):
    """编译 + 运行，返回 (rc, 合并输出)。

    rundir 必须分开：测试台把捕获写成固定的 sim_capture_A/B.txt，
    基线那次和变异那次如果同目录，后跑的会把前一次的捕获覆盖掉，
    于是解码器验的其实是变异版的波形 —— 这条踩过一次。
    """
    rundir = Path(rundir)
    rundir.mkdir(parents=True, exist_ok=True)
    vvp = rundir / f'{tag}.vvp'
    cmd = [IV, '-g2005', '-o', str(vvp), '-s', 'tb_ack_last',
           str(TB), str(MODEL), str(cfg)]
    c = subprocess.run(cmd, capture_output=True, text=True,
                       errors='replace', cwd=str(rundir))
    if c.returncode != 0:
        return 2, '编译失败:\n' + (c.stdout + c.stderr)[-2000:]
    try:
        r = subprocess.run([VVP, vvp.name], capture_output=True, text=True,
                           errors='replace', cwd=str(rundir), timeout=600)
    except subprocess.TimeoutExpired:
        return 2, '运行超时（>600 s）'
    return 0, r.stdout + r.stderr


def decode(capture):
    r = subprocess.run([sys.executable, str(DECODE), str(capture)],
                       capture_output=True, text=True, errors='replace')
    return r.stdout + r.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()

    for p in (Path(IV), TB, MODEL, CFG):
        if not p.exists():
            print(f'找不到 {p}')
            return 2

    got = sha(CFG)
    if got != CFG_SHA:
        print(f'cfg_eeprom_store.v 的 sha256 不是原样拷贝：\n  期望 {CFG_SHA}\n  实际 {got}')
        print('  波形不再能代表队友那份代码的行为，先恢复原文件再跑。')
        return 1

    WORK.mkdir(exist_ok=True)
    bad = []

    # ---- 1. 基线：必须红，且红在这 4 条 ----
    print('=' * 70)
    print('== 1/4 基线：仓库原样的 cfg_eeprom_store.v —— 期望 4 条判据红')
    print('=' * 70)
    rc, out = compile_run(CFG, 'base', WORK / 'base')
    if rc != 0:
        print(out)
        return 2
    if args.verbose:
        print(out)
    else:
        for ln in out.splitlines():
            if re.search(r'\[(FAIL|NOTE)\]|rd_bytes|ACK  |NACK|STOP  |cfg_ok|判据|PASS ——|FAIL ——', ln):
                print(ln)
    for want in BASE_MUST_FAIL:
        if want not in out:
            print(f'  [差] 缺少预期的失败行: {want}')
            bad.append(f'base missing: {want}')
    nfail = len(re.findall(r'\[FAIL\]', out))
    if nfail != 4:
        print(f'  [差] [FAIL] 行数 {nfail}，期望正好 4（多/少都说明测试台变了）')
        bad.append(f'base fail count {nfail}')

    # ---- 2. 变异：必须全绿 ----
    print()
    print('=' * 70)
    print('== 2/4 变异：末字节改回 NACK —— 期望 7 条判据全绿')
    print('=' * 70)
    src = CFG.read_text(encoding='utf-8')
    if MUT_OLD not in src:
        print('  变异点找不到，cfg_eeprom_store.v 的 RXACK 分支被改过了：')
        print('  ' + MUT_OLD)
        return 1
    mut = WORK / 'cfg_last_nack.v'
    mut.write_text(src.replace(MUT_OLD, MUT_NEW), encoding='utf-8', newline='\n')
    rc, out2 = compile_run(mut, 'mut', WORK / 'mut')
    if rc != 0:
        print(out2)
        return 2
    if args.verbose:
        print(out2)
    else:
        for ln in out2.splitlines():
            if re.search(r'\[FAIL\]|rd_bytes|ACK  |NACK|STOP  |cfg_ok|判据|PASS ——|FAIL ——', ln):
                print(ln)
    for want in MUT_MUST_PASS:
        if want not in out2:
            print(f'  [差] 缺少预期的通过行: {want}')
            bad.append(f'mut missing: {want}')

    # ---- 3. 解码器：两路捕获 ----
    print()
    print('=' * 70)
    print('== 3/4 解码器：仿真导出的捕获 → 事务还原')
    print('=' * 70)
    for cap, must, label in (
            ('sim_capture_A.txt', DEC_A_MUST, 'A（0x003A=0xFF，STOP 侥幸成立）'),
            ('sim_capture_B.txt', DEC_B_MUST, 'B（0x003A=0x00，STOP 消失）')):
        f = WORK / 'base' / cap
        if not f.exists():
            print(f'  [差] 没有捕获文件 {f}（测试台没写出来？）')
            bad.append(f'no capture {cap}')
            continue
        txt = decode(f)
        print(f'\n--- 捕获 {label} ---')
        for ln in txt.splitlines():
            if re.search(r'记录|时间单位|事务 |读 |末 3 字节|没有 STOP|有 STOP|违规|结论', ln):
                print(ln)
        for want in must:
            if want not in txt:
                print(f'  [差] 解码结论里缺: {want}')
                bad.append(f'decode {cap}: {want}')

    # ---- 4. 汇总 ----
    print()
    print('=' * 70)
    if bad:
        print(f'差分结论: 不符合预期（{len(bad)} 处）')
        for b in bad:
            print('  - ' + b)
        return 1
    print('差分结论: 符合预期')
    print('  · 基线红在 4 条判据上 —— 缺陷存在，且位置明确')
    print('  · 变异全绿             —— 这 4 条判据确实在测这件事')
    print('  · 解码器两路都对       —— 捕获能还原成事务级结论')
    print('=' * 70)
    return 0


if __name__ == '__main__':
    sys.exit(main())
