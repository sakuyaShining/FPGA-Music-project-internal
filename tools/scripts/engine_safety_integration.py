"""Focused integration regression for stage1; no board access or source generation."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
import regress_all as gate

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'sim_build/engine-safety-integration')
    parser.add_argument('--case', help='Run one existing case, or tdm_golden')
    args = parser.parse_args()
    out = args.out.resolve()
    out.relative_to(ROOT/'sim_build') # Existing gate cleanup must stay inside this worktree.
    out.mkdir(parents=True, exist_ok=True)
    gate.BUILD = str(out)
    results = []
    project = ROOT/'src/gowin/tdm_synth/tdm_live_test.gprj'
    rtl = [str((project.parent/f.attrib['path']).resolve()) for f in ET.parse(project).findall('.//File')
           if f.attrib.get('enable', '1') == '1' and f.attrib['path'].endswith('.v')]
    for top, marker, judge in [
        ('tb_alloc', 'RESULT alloc=PASS', None),
        ('tb_legato', 'RESULT legato=PASS', None),
        ('tb_event_sources', 'RESULT event_sources=PASS', None),
        ('tb_finger_top', 'PASS finger_top:', None),
        ('tb_protocol_join', 'RESULT protocol_join=PASS', None),
        ('tb_i2s_top', None, 'i2s_top_check.py'),
        ('tb_pitch_mod512', None, 'pitch_mod512_check.py'),
    ]:
        if args.case and args.case != top:
            continue
        extra_hex = []
        if top == 'tb_pitch_mod512':
            # This bench runs at 25MHz/512, not the 27MHz product sample rate.
            fixture = out/'pitch512-tables'
            subprocess.run([sys.executable, str(ROOT/'tools/scripts/note_map_gen.py'), 'gen',
                            '--fs', '48828.125', '--outdir', str(fixture)],
                           check=True, capture_output=True)
            extra_hex = [str(p) for p in fixture.glob('*.hex')]
        log, err = gate.compile_and_run(top, rtl+[str(ROOT/'src/sim'/(top+'.v'))],
                                        defines=('SIM_INIT',), need_hex=True, extra_hex=extra_hex)
        (out/(top+'.log')).write_text(err or log or '', encoding='utf-8')
        passed = not err and bool(log)
        if marker:
            passed = passed and marker in log
        elif passed:
            passed, detail = gate.judge_script(top, judge)
        results.append({'test': top, 'passed': bool(passed)})
        print(top+': '+('PASS' if passed else 'FAIL'), flush=True)
        if not passed:
            print((err or log or '')[-1200:], flush=True)
    for mask in (1, 3, 15, 0xFFFF, 0xFFFFFFFF, 0x55555555, 0xAAAAAAAA, 0x80000001):
        if args.case and args.case != 'tdm_golden':
            continue
        for env in (0, 1):
            passed, detail = gate.run_tdm_mask(mask, env)
            results.append({'test': 'tdm_golden', 'mask': mask, 'envelope': env, 'passed': passed})
            print(detail, flush=True)
    (out/'summary.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    passed = bool(results) and all(row['passed'] for row in results)
    print('RESULT engine_safety_integration='+('PASS' if passed else 'FAIL'), flush=True)
    return int(not passed)


if __name__ == '__main__':
    sys.exit(main())
