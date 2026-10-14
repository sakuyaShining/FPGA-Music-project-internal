"""Stage1 safety/re-excitation checks; no hardware or baseline changes."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
IV = Path('D:/iverilog/bin')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'sim_build/engine-safety')
    parser.add_argument('--new-only', action='store_true', help='Only new frequency/re-excitation gates')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    project = ROOT/'src/gowin/tdm_synth/tdm_live_test.gprj'
    top_modules = [Path(f.attrib['path']).stem for f in ET.parse(project).findall('.//File')
                   if f.attrib.get('enable', '1') == '1' and f.attrib['path'].endswith('.v')]
    suites = [
        ('tb_note_frequency_guard', ['note_map', 'vel_shape'], 'RESULT note_frequency_guard=PASS'),
        ('tb_engine_safety', ['tdm_engine', 'osc_env', 'pitch_mod'], 'RESULT engine_safety=PASS'),
        ('tb_retrigger_top', top_modules, 'RESULT retrigger_top=PASS'),
        ('tb_release_continuity', ['tdm_engine', 'osc_env', 'pitch_mod'], 'RESULT release_continuity=PASS'),
        ('tb_osc_env', ['osc_env'], '[PASS]'),
        ('tb_finger_pitch', ['finger_pitch'], 'PASS finger_pitch:'),
    ]
    if args.new_only:
        suites = suites[:3]
    failed = 0
    for top, modules, marker in suites:
        work = args.out/top
        work.mkdir(exist_ok=True)
        for table in (ROOT/'src/gowin/tdm_synth').glob('*.hex'):
            shutil.copyfile(table, work/table.name)
        compile_result = subprocess.run(
            [str(IV/'iverilog.exe'), '-g2012', '-DSIM_INIT', '-s', top, '-o', str((work/'test.vvp').resolve())]
            + [str(ROOT/'src/rtl'/(m+'.v')) for m in modules]
            + [str(ROOT/'src/sim'/(top+'.v'))], cwd=work, capture_output=True,
            encoding='utf-8', errors='replace', timeout=60)
        (work/'compile.log').write_text(compile_result.stdout+compile_result.stderr, encoding='utf-8')
        if compile_result.returncode:
            print(compile_result.stderr, flush=True)
            failed += 1
            continue
        run = subprocess.run([str(IV/'vvp.exe'), str((work/'test.vvp').resolve())],
                             cwd=work, capture_output=True, encoding='utf-8', errors='replace', timeout=180)
        (work/'run.log').write_text(run.stdout+run.stderr, encoding='utf-8')
        passed = run.returncode == 0 and marker in run.stdout
        print(top+': '+('PASS' if passed else 'FAIL')+'\n'+run.stdout[-700:], flush=True)
        failed += not passed
    print('RESULT engine_safety_suite='+('FAIL' if failed else 'PASS'), flush=True)
    return int(bool(failed))


if __name__ == '__main__':
    sys.exit(main())
