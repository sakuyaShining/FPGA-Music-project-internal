"""Build the bench audio self-test bitstream (audio_selftest_top).

Why a separate script instead of build_product.py:
  · build_product.py only copies engine/src/*.v, so it cannot see
    audio_probe/audio_selftest_top.v. Putting the self-test top into
    engine/src/ would pollute the product source set (and the run.json
    input list that the product build record depends on).
  · The product constraint files are used READ-ONLY here (copied into the
    build dir, never edited), so the pin assignment is byte-identical to
    the shipping bitstream. That is the whole point: same pins, same I2S.

    python build_selftest.py build_01 full
    python build_selftest.py synth_01 synth

Output goes to audio_probe/<label>/ (gitignored). Never programs the device.

★ -use_sspi_as_gpio 1 is REQUIRED here, unlike build_probe.py.
  dac_bck/dac_ws/dac_din land on 56/55/54, which are SSPI mux pins on
  GW2AR-18. Without the switch, place&route fails with "pin already used by
  SSPI". The cost is that the SSPI verify path disappears, so programming
  always reports "Verify Failed" + Status Code 0x00006020. Judge success by
  the UserCode read back, not by the status code.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # fpga/current/audio_probe
R = HERE.parent                                  # fpga/current

TOP = 'audio_selftest_top'

# Same source set as build_product.py, plus our own top. engine/rtl holds the
# SDRAM/PCM storage subsystem; engine/src holds everything else.
SOURCES = (
    [HERE / 'audio_selftest_top.v']
    + sorted((R / 'engine/src').glob('*.v'))
    + sorted((R / 'engine/rtl').glob('*.v'))
    + sorted((R / 'engine/src').glob('*.hex'))
    + sorted((R / 'engine/src').glob('*.vh'))
)

# Read-only reuse of the shipping constraints: identical pins to the product.
CONSTRAINTS = [R / 'constraints/tdm_ship_owned.cst',
               R / 'constraints/tdm_ship_owned.sdc']


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    label = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'full'
    assert mode in ('full', 'synth'), mode
    assert re.fullmatch(r'(synth|build)_[a-zA-Z0-9_]+', label), label

    D = HERE / label
    assert not D.exists(), 'Refuse to overwrite an existing build: ' + label
    D.mkdir()

    inputs = {}
    entries = []
    for p in SOURCES + CONSTRAINTS:
        assert p.exists(), p
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

    run_step = 'run all' if mode == 'full' else 'run syn'
    (D / 'build.tcl').write_text(
        'open_project "' + (D / 'board.gprj').as_posix() + '"\n'
        'set_option -top_module ' + TOP + '\n'
        'set_option -use_sspi_as_gpio 1\n'
        + run_step + '\nexit\n')

    exe = os.environ.get('FPGA_GOWIN_GW_SH',
        'D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/'
        'Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe')
    start = time.monotonic()
    with (D / 'console.log').open('w', encoding='utf-8') as f:
        proc = subprocess.Popen([exe, str(D / 'build.tcl')], cwd=D,
                                stdout=f, stderr=subprocess.STDOUT)
        try:
            rc = proc.wait(timeout=1800)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
            proc.wait()
            rc = 124

    log = (D / 'console.log').read_text(encoding='utf-8', errors='replace')
    has_err = bool(re.search(r'\bERROR\s*\(', log))
    ok = rc == 0 and not has_err and (
        'Synthesis' in log if mode == 'synth' else 'Bitstream generation completed' in log)

    data = dict(status='ok' if ok else 'FAILED', returncode=rc, mode=mode, top=TOP,
                seconds=round(time.monotonic() - start, 2), inputs=inputs,
                project_sha256=sha(D / 'board.gprj'), tcl_sha256=sha(D / 'build.tcl'),
                hardware_programmed=False)
    (D / 'run.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in data.items() if k != 'inputs'}))
    if not ok:
        print(log[-6000:])
        return 1

    for name in ('impl/pnr/' + TOP + '.fs', 'impl/pnr/' + TOP + '.bin'):
        p = D / name
        print(('  ' + name + '  ' + str(p.stat().st_size) + ' B') if p.exists()
              else ('  MISSING ' + name))
    return 0


if __name__ == '__main__':
    sys.exit(main())
