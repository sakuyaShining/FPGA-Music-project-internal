"""Reproduce controller-level checks. Requires Icarus and Python with Pillow.

--reuse-capture only reuses the completed full simulation when its compiled
artifact is newer than all main HDL inputs. Negative controls are still run.
This does not perform PnR or interact with the physical FPGA/display.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from check_capture import parse_capture

ROOT = Path(__file__).resolve().parent
IVERILOG = Path('D:/iverilog/bin/iverilog.exe')
VVP = IVERILOG.with_name('vvp.exe')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    result = subprocess.run([str(x) for x in args], cwd=ROOT, capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=240)
    (ROOT / 'evidence' / log).write_text(result.stdout + result.stderr, encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--reuse-capture', action='store_true')
    args = parser.parse_args()
    inputs = [ROOT / 'rtl/ili9341_spi_byte.v', ROOT / 'rtl/ili9341_window.v', ROOT / 'tb_ili9341.v']
    compiled = ROOT / 'sim.vvp'
    if args.reuse_capture:
        assert compiled.stat().st_mtime >= max(p.stat().st_mtime for p in inputs), 'stale compiled simulation'
        assert (ROOT / 'spi-bytes.log').stat().st_mtime >= compiled.stat().st_mtime
        assert 'PASS pin timing' in (ROOT / 'evidence/simulation.log').read_text(encoding='utf-8')
    else:
        build = run([IVERILOG, '-g2012', '-s', 'tb_ili9341', '-o', compiled, *inputs], 'compile.log')
        assert build.returncode == 0, 'HDL compile failed'
        sim = run([VVP, compiled], 'simulation.log')
        assert sim.returncode == 0 and 'PASS pin timing' in sim.stdout, 'simulation failed'
    check = run([sys.executable, ROOT / 'check_capture.py'], 'capture-check.log')
    assert check.returncode == 0
    negative = []
    for half, expected_success in ((2, True), (1, False)):
        exe = ROOT / f'serializer-{half}.vvp'
        build = run([IVERILOG, '-g2012', '-s', 'tb_spi_fault', f'-Ptb_spi_fault.HALF={half}',
                     '-o', exe, inputs[0], ROOT / 'tb_spi_fault.v'], f'serializer-{half}-compile.log')
        assert build.returncode == 0
        sim = run([VVP, exe], f'serializer-{half}.log')
        if expected_success:
            assert sim.returncode == 0 and 'PASS serializer' in sim.stdout
        else:
            assert sim.returncode != 0 and 'EXPECTED_TIMING_REJECTION' in sim.stdout
        negative.append({'kind': 'serializer clock bound', 'half_cycles': half,
                         'expected_success': expected_success, 'exit_code': sim.returncode})
    lines = (ROOT / 'spi-bytes.log').read_text(encoding='utf-8').splitlines()
    mutations = {}
    wrong_pixel = list(lines)
    for i, line in enumerate(wrong_pixel):
        if line.startswith('START ') and ' 1 0 0 239 319' in line:
            j = next(j for j in range(i+1, len(lines)) if lines[j].startswith('BYTE ') and lines[j].endswith(' 0 2c'))
            parts = wrong_pixel[j+1].split(); parts[-1] = '00'
            wrong_pixel[j+1] = ' '.join(parts)
            break
    mutations['corrupted_pixel'] = wrong_pixel
    truncated = list(lines)
    done = next(i for i, line in enumerate(truncated) if line.startswith('DONE ') and line.endswith(' 1'))
    last_byte = max(i for i in range(done) if truncated[i].startswith('BYTE '))
    del truncated[last_byte]
    mutations['missing_pixel_byte'] = truncated
    for name, content in mutations.items():
        path = ROOT / 'evidence' / f'negative-{name}.log'
        path.write_text('\n'.join(content) + '\n', encoding='utf-8')
        try:
            parse_capture(path)
        except AssertionError as exc:
            negative.append({'kind': name, 'rejected': True, 'reason': str(exc)})
        else:
            raise AssertionError(f'negative control accepted: {name}')
    result = {'status': 'PASS', 'scope': 'controller-level protocol/timing and reference-image checks only',
              'main_hdl_sha256': {p.relative_to(ROOT).as_posix(): sha(p) for p in inputs},
              'model_sha256': sha(ROOT / 'check_capture.py'),
              'capture_sha256': sha(ROOT / 'spi-bytes.log'), 'negative_controls': negative,
              'not_verified': ['actual module interface jumpers, supply and wiring', 'panel power/gamma settings',
                               'physical image or speed', 'music FFT/trajectory renderer',
                               'full combined PnR', 'touch-to-sound latency']}
    (ROOT / 'evidence/validation-summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
