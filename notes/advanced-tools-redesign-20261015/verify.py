import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')
OUT = Path(__file__).resolve().parent
env = dict(os.environ, PYTHONPATH=str(ROOT/'tools/host')+';'+str(ROOT/'tools/scripts'),
           QT_QPA_PLATFORM='offscreen', QT_QPA_FONTDIR='C:/Windows/Fonts', PYTHONIOENCODING='utf-8')
jobs = [
    ('host-tests', ['-m', 'unittest', 'discover', '-s', 'tools/host', '-p', 'test_*.py'], {}),
    ('dpi-125', ['-m', 'unittest', 'test_advanced_tools.AdvancedToolsTests.test_small_screens_and_large_text_keep_close_and_apply_visible'], {'QT_SCALE_FACTOR':'1.25'}),
    ('dpi-150', ['-m', 'unittest', 'test_advanced_tools.AdvancedToolsTests.test_small_screens_and_large_text_keep_close_and_apply_visible'], {'QT_SCALE_FACTOR':'1.5'}),
    ('dpi-200', ['-m', 'unittest', 'test_advanced_tools.AdvancedToolsTests.test_small_screens_and_large_text_keep_close_and_apply_visible'], {'QT_SCALE_FACTOR':'2'}),
    ('gui-selftest', ['tools/host/dsp_gui.py', '--selftest'], {}),
    ('workbench-selftest', ['tools/host/dsp_gui.py', '--workbench-selftest'], {}),
    ('normal-startup', ['tools/host/dsp_gui.py', '--startup-check'], {}),
]
records = []
for name, args, extra in jobs:
    result = subprocess.run([sys.executable, '-X', 'utf8'] + args, cwd=ROOT,
                            env=dict(env, **extra), capture_output=True, timeout=120)
    (OUT / (name+'.log')).write_bytes(result.stdout + result.stderr)
    records.append(dict(name=name, command=args, extra_env=extra, exit_code=result.returncode,
                        log=str(OUT / (name+'.log'))))
    print(name, result.returncode, flush=True)
(OUT/'checks.json').write_text(json.dumps(dict(scope='离线Qt布局、模拟协议与主机回归；非板测',
    status='PASS' if all(r['exit_code']==0 for r in records) else 'FAIL', checks=records),
    ensure_ascii=False, indent=2), encoding='utf-8')
sys.exit(0 if all(r['exit_code']==0 for r in records) else 1)
