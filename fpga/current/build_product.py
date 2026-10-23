"""Build the SHIPPING top (tdm_ship_owned) — synthesis-only or full PnR.

Unlike build_board.py (which builds the structural probe joint_timing_top and
must NEVER be programmed), this script targets the product wrapper that drives
real board pins per constraints/tdm_ship_owned.cst.

    python build_product.py synth_<label>            # ~1m45s, area only
    python build_product.py build_<label> full 1     # ~9-15min, bitstream

Refuses to overwrite an existing build directory. Never programs the device —
programming is a separate, explicit step.
"""
from common import *
import sys, shutil, time, re

label = sys.argv[1]
mode = sys.argv[2] if len(sys.argv) > 2 else 'synth'
assert mode in ('synth', 'full')
strategy = int(sys.argv[3]) if len(sys.argv) > 3 else 0
assert re.fullmatch(r'(synth|build)_[a-zA-Z0-9_]+', label)

TOP = sys.argv[4] if len(sys.argv) > 4 else 'tdm_ship_owned'
D = R / label
assert not D.exists(), 'Refuse to overwrite an existing build: ' + label
D.mkdir()

# Product sources only. rtl/ holds structural probes (joint_timing_top,
# sdram_*_probe) that the shipping top does not reference.
files = (list((R / 'engine/src').glob('*.v'))
         + list((R / 'engine/rtl').glob('*.v'))
         + list((R / 'engine/src').glob('*.hex'))
         + list((R / 'engine/src').glob('*.vh'))
         + [R / 'constraints/tdm_ship_owned.cst', R / 'constraints/tdm_ship_owned.sdc'])

inputs = {}
entries = []
for p in files:
    assert p.name not in inputs, 'duplicate filename: ' + p.name
    shutil.copyfile(p, D / p.name)
    inputs[p.name] = dict(source=p.relative_to(R).as_posix(), sha256=sha(p))
    kind = {'.v': 'file.verilog', '.cst': 'file.cst', '.sdc': 'file.sdc'}.get(p.suffix)
    if kind:
        entries.append('<File path="' + p.name + '" type="' + kind + '" enable="1"/>')

(D / 'board.gprj').write_text(
    '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project>'
    '<Template>FPGA</Template><Version>5</Version>'
    '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>'
    '<FileList>' + ''.join(entries) + '</FileList></Project>')

options = {0: '', 1: 'set_option -place_option 1\nset_option -route_option 1\n',
           2: 'set_option -route_option 1\n',
           5: 'set_option -place_option 2\n',
           6: 'set_option -place_option 2\nset_option -route_option 1\n'}[strategy]

run_step = 'run all' if mode == 'full' else 'run syn'

# ---------------------------------------------------------------------------
# -use_sspi_as_gpio 1 : 不能去掉，也不能被"顺手清理"掉
# ---------------------------------------------------------------------------
# 为什么必须有：
#   本设计的 I2S 三根线落在 54 / 55 / 56，这三个脚在 GW2AR-18 上是 SSPI
#   复用脚。不打开这个开关，place&route 会报 "pin already used by SSPI"，
#   `run all` 直接失败 —— 也就是说，这不是优化项，是能不能构建的问题。
#
# 代价（必须提前知道，否则会被误导）：
#   打开后 SSPI 配置口被当普通 IO 用掉，**"SRAM Program and Verify" 的
#   校验阶段必然报 `Error: Verify Failed` + `Status Code 0x00006020`**。
#   这是开关的直接后果，不是码流坏了。
#   证据：build_prod_v5 与 build_strike_v2 都报同一句，而 v5 在板上寄存器
#   读写全部正常（`tx 0f12 -> rx 12 00`）。⇒ 只要 program 阶段 100% 走完，
#   校验失败可以忽略。
#
# 想验证"是不是真的没烧进去"的唯一可靠办法：串口读一个已知寄存器。
#   python tools/board_velocity_check.py dump
# ---------------------------------------------------------------------------
(D / 'build.tcl').write_text(
    'open_project "' + (D / 'board.gprj').as_posix() + '"\n'
    'set_option -top_module ' + TOP + '\n'
    + ('' if os.environ.get('NO_SSPI') else 'set_option -use_sspi_as_gpio 1\n')
    + options + run_step + '\nexit\n')

exe = os.environ.get('FPGA_GOWIN_GW_SH',
    'D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe')
start = time.monotonic()
with (D / 'console.log').open('w', encoding='utf-8') as f:
    proc = subprocess.Popen([exe, str(D / 'build.tcl')], cwd=D, stdout=f, stderr=subprocess.STDOUT)
    try:
        rc = proc.wait(timeout=1800)
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
        proc.wait()
        rc = 124

log = (D / 'console.log').read_text(encoding='utf-8', errors='replace')
has_err = bool(re.search(r'\bERROR\s*\(', log))
if mode == 'synth':
    ok = rc == 0 and not has_err and 'Synthesis' in log
else:
    ok = rc == 0 and not has_err and 'Bitstream generation completed' in log

data = dict(status='ok' if ok else 'FAILED', returncode=rc, mode=mode, strategy=strategy, top=TOP,
            seconds=round(time.monotonic() - start, 2), inputs=inputs,
            project_sha256=sha(D / 'board.gprj'), tcl_sha256=sha(D / 'build.tcl'),
            hardware_programmed=False)
(D / 'run.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
print(json.dumps({k: v for k, v in data.items() if k != 'inputs'}))
if not ok:
    print(log[-4000:])
    sys.exit(1)
