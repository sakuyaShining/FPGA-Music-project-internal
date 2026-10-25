"""Build the EEPROM I2C capture probe (eeprom_capture_top).

Separate from build_product.py on purpose:
  · build_product.py hardcodes constraints/tdm_ship_owned.cst, and we must NOT
    touch the product constraint file for a throwaway probe. This script uses
    eeprom_probe/eeprom_probe.cst (pins copied from the audited product files).
  · The probe needs its own small source set (top + the teammate's unmodified
    cfg_eeprom_store.v + uart_tx.v), not all of engine/src.

    python build_probe.py build_01 full
    python build_probe.py synth_01 synth

Output goes to eeprom_probe/<label>/ (gitignored). Never programs the device.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent          # fpga/current/eeprom_probe
R = HERE.parent                                  # fpga/current

TOP = 'eeprom_capture_top'

SOURCES = [
    HERE / 'eeprom_capture_top.v',
    HERE / 'cfg_eeprom_store.v',
    R / 'engine/src/uart_tx.v',
]
CONSTRAINTS = [HERE / 'eeprom_probe.cst', HERE / 'eeprom_probe.sdc']

# The teammate's module must be byte-identical to what he shipped, otherwise the
# captured waveform is not evidence about HIS code.
CFG_SHA = 'ce40c936c63f09e7dee182884d4abaa7994834388396155c21144ffd65fe931b'


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

    got = sha(HERE / 'cfg_eeprom_store.v')
    assert got == CFG_SHA, ('cfg_eeprom_store.v 不是原样拷贝，波形就不再是证据了', got)

    D = HERE / label
    assert not D.exists(), 'Refuse to overwrite an existing build: ' + label
    D.mkdir()

    inputs = {}
    entries = []
    for p in SOURCES + CONSTRAINTS:
        assert p.exists(), p
        shutil.copyfile(p, D / p.name)
        inputs[p.name] = dict(source=p.relative_to(R).as_posix(), sha256=sha(p))
        kind = {'.v': 'file.verilog', '.cst': 'file.cst', '.sdc': 'file.sdc'}[p.suffix]
        entries.append('<File path="' + p.name + '" type="' + kind + '" enable="1"/>')

    (D / 'board.gprj').write_text(
        '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project>'
        '<Template>FPGA</Template><Version>5</Version>'
        '<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device>'
        '<FileList>' + ''.join(entries) + '</FileList></Project>')

    # NOTE: no -use_sspi_as_gpio here. None of our pins (4/25/26/69/15..20) are
    # SSPI, so the bitstream should program AND verify. If PnR complains about an
    # SSPI pin, add it -- but then Verify Failed 0x00006020 comes back and the
    # only proof of a good load is the UART output itself.
    (D / 'build.tcl').write_text(
        'open_project "' + (D / 'board.gprj').as_posix() + '"\n'
        'set_option -top_module ' + TOP + '\n'
        + ('run all' if mode == 'full' else 'run syn') + '\nexit\n')

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
