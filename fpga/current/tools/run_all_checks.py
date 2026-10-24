#!/usr/bin/env python3
"""run_all_checks.py —— 一次跑完【全部】判据，出一张表

为什么需要它
============
仓库里有两套互不知道对方存在的测试驱动：

  · `tools/run_sims.py`  —— 10 个 `sim/tb_*.v`，单模块级，几秒一个
  · `check_*.py`（12 个） —— `tb/` 与根目录的 `tb_*.v`，整链级，几十秒到几分钟

此前"哪些测试台能跑"只存在于人的记忆里。实际后果：`sim/tb_audio_clk_en.v`
被 `audio_clk_en.v` 的注释引用了半年，**文件根本不存在**，采样率零覆盖；
`tb/tb_board_scan.v` 至今没有任何驱动。这两件事都不是"忘了写测试"，
而是"没有地方能看出缺了什么"。

本脚本做两件事：
  1. 跑 run_sims.py 的全部 case + 全部 check_*.py，汇总 PASS/FAIL
  2. 扫一遍仓库，报出【没有任何驱动】的 tb —— 它们要么是死代码，要么是漏登记

用法
====
    python tools/run_all_checks.py                # 全跑
    python tools/run_all_checks.py --fast         # 只跑 run_sims（跳过慢的 check_*）
    python tools/run_all_checks.py --list         # 只出清单，不跑
    python tools/run_all_checks.py --only tb_octave,check_sensor

注意：`check_*.py` 里的 `common.py` 会校验"运行期间输入文件没被改过"。
     跑本脚本期间不要改 `engine/src/**`，否则会看到 AssertionError（不是 RTL 错）。
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parent.parent
PY = sys.executable
IV = r'D:/iverilog/bin/iverilog.exe'

# 每个 check 脚本的判据要点（人工登记，改判据时一起改这里）
CHECK_DOC = {
    'check_delta.py':          '三配置逐拍比对 delta 帧（120k cycles/配置）',
    'check_scan_store.py':     '扫描器 + 存储：行协议、越界、背压',
    'check_joint.py':          '整链联仿：扫描→存储→重心→引擎→PCM→回放',
    'check_joint_variant.py':  '联仿变体（MAC 资源路径）',
    'check_scan_variant.py':   '扫描器变体',
    'check_pitch.py':          '音高存储器读写/复位/同址双写',
    'check_sensor.py':         '传感器：160 帧独立参考、标定、坏节点、滞回、背压',
    'check_native.py':         '原生通路',
    'check_renderer.py':       '渲染器：8388608 像素穷举 + 单像素变异',
    'check_envelope.py':       '包络状态机与 Python 参考模型逐拍比对',
    'check_phase_wrap.py':     '相位回绕',
    'check_engine_compat.py':  '引擎兼容层（音乐/图层/传感器图层）',
}


def run(cmd, timeout=3600):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           errors='replace', cwd=str(R), timeout=timeout)
        return p.returncode, p.stdout + p.stderr, time.time() - t0
    except subprocess.TimeoutExpired:
        return 124, f'超时（>{timeout}s）', time.time() - t0


def sim_cases():
    """从 run_sims.py 里读出 case 名，避免两处清单不同步。"""
    t = (R / 'tools/run_sims.py').read_text(encoding='utf-8')
    return re.findall(r"^\s{4}'(tb_[a-z_0-9]+)':", t, re.M)


def tb_files():
    got = {}
    for d in ('tb', 'sim', '.'):
        for p in sorted((R / d).glob('tb_*.v')):
            got[p.stem] = str(p.relative_to(R)).replace('\\', '/')
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fast', action='store_true', help='只跑 run_sims（跳过 check_*）')
    ap.add_argument('--list', action='store_true', help='只出清单不跑')
    ap.add_argument('--only', default='', help='逗号分隔的 tb 名或 check 脚本名')
    args = ap.parse_args()

    only = [x.strip() for x in args.only.split(',') if x.strip()]
    cases = sim_cases()
    checks = sorted(p.name for p in R.glob('check_*.py'))

    # 覆盖率体检：哪些 tb 没有驱动
    driven = set(cases)
    for c in checks:
        t = (R / c).read_text(encoding='utf-8', errors='replace')
        driven |= set(re.findall(r'tb_[a-z_0-9]+', t))
    files = tb_files()
    orphan = sorted(n for n in files if n not in driven)

    print('测试台清单')
    print('=' * 78)
    print(f'  sim/tb_*.v   : {len([n for n in cases])} 个（run_sims.py）')
    print(f'  tb_*.v 合计  : {len(files)} 个')
    print(f'  check 脚本   : {len(checks)} 个')
    if orphan:
        print(f'  【无驱动】   : {len(orphan)} 个 -> {", ".join(orphan)}')
        print('                 这些测试台不会被任何脚本跑到，等于没有判据。')
    else:
        print('  【无驱动】   : 无')
    print()

    if args.list:
        for n in sorted(files):
            mark = '  ' if n in driven else '!!'
            print(f'  {mark} {n:24s} {files[n]}')
        return 0

    if not Path(IV).exists():
        print(f'找不到 iverilog：{IV}')
        return 2

    rows = []

    #---- 第一段：run_sims ----
    if not only or any(x in cases for x in only):
        sub = [x for x in only if x in cases] or cases
        print(f'== run_sims.py（{len(sub)} 个）')
        for name in sub:
            rc, out, dt = run([PY, 'tools/run_sims.py', name])
            ok = rc == 0
            rows.append((name, 'run_sims.py', ok, dt, ''))
            print(f'  {"PASS" if ok else "FAIL"}  {name:22s} {dt:6.1f}s')
            if not ok:
                for l in out.splitlines():
                    if '[FAIL]' in l or '编译失败' in l:
                        print('        ' + l.strip()[:120])

    #---- 第二段：check_*.py ----
    if not args.fast:
        sub = [x for x in only if x in checks] if only else checks
        print(f'\n== check_*.py（{len(sub)} 个，慢）')
        for name in sub:
            rc, out, dt = run([PY, name])
            ok = rc == 0
            note = ''
            m = re.search(r'^PASS (.*)$', out, re.M)
            if m:
                note = m.group(1).strip()[:70]
            rows.append((name, 'check_*', ok, dt, note))
            print(f'  {"PASS" if ok else "FAIL"}  {name:24s} {dt:6.1f}s  {note}')
            if not ok:
                tail = [l for l in out.splitlines() if l.strip()][-4:]
                for l in tail:
                    print('        ' + l.strip()[:120])

    #---- 汇总 ----
    bad = [r for r in rows if not r[2]]
    print()
    print('=' * 78)
    if bad:
        print(f'汇总: FAIL ({len(bad)}/{len(rows)})')
        for n, k, _, _, _ in bad:
            print(f'  · {n}（{k}）')
        if orphan:
            print(f'  另有 {len(orphan)} 个测试台无驱动：{", ".join(orphan)}')
        return 1
    print(f'汇总: PASS ({len(rows)}/{len(rows)})')
    if orphan:
        print(f'注意：{len(orphan)} 个测试台无驱动：{", ".join(orphan)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
