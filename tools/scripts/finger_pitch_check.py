"""Run contact expression unit and full 512-slot top integration checks."""
from pathlib import Path
import regress_all as r

ROOT = Path(r.ROOT)
build = ROOT / 'sim_build/finger_pitch'
build.mkdir(parents=True, exist_ok=True)
missing = r.copy_data(str(build))
if missing:
    raise SystemExit(f'Missing data: {missing}')
sources = [str(p) for p in (ROOT / 'src/rtl').glob('*.v')]
for name in ('tb_finger_pitch', 'tb_finger_top'):
    exe = build / (name + '.vvp')
    rc, out = r.run([str(Path(r.IV) / 'iverilog.exe'), '-g2005', '-DSIM_INIT',
                     '-s', name, '-o', str(exe),
                     str(ROOT / 'src/sim' / (name + '.v')), *sources], str(build))
    (build / (name + '_compile.log')).write_text(out, encoding='utf-8')
    if rc:
        print(out)
        raise SystemExit(1)
    rc, out = r.run([str(Path(r.IV) / 'vvp.exe'), str(exe)], str(build), timeout=60)
    (build / (name + '.log')).write_text(out, encoding='utf-8')
    print(out)
    if rc or f'PASS {name[3:]}' not in out or 'ERROR' in out:
        raise SystemExit(1)
print('PASS continuous per-contact pitch integration')
