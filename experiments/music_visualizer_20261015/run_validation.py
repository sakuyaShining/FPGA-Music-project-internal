"""Run from any directory with a Python containing numpy and Pillow."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run_sim(top, sources, stem):
    subprocess.run(['D:/iverilog/bin/iverilog.exe', '-g2012', '-I', 'rtl', '-s', top,
                    '-o', f'{stem}.vvp', *sources], cwd=ROOT, check=True)
    with (ROOT/f'{stem}-simulation.log').open('w') as output:
        subprocess.run(['D:/iverilog/bin/vvp.exe', f'{stem}.vvp'], cwd=ROOT,
                        stdout=output, stderr=subprocess.STDOUT, check=True)
    print((ROOT/f'{stem}-simulation.log').read_text(), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-existing', action='store_true', help='check bound captures without repeating simulation')
    parser.add_argument('--engine', action='store_true', help='also run the copied-engine isolation test')
    args = parser.parse_args()
    if args.check_existing:
        saved = json.loads((ROOT/'verification.json').read_text())
        for group in ('inputs_sha256', 'captures_sha256'):
            for relative, digest in saved[group].items():
                assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest() == digest, relative
    else:
        run_sim('tb_fft', ['rtl/mv_fft1024.v', 'tb_fft.v'], 'fft')
        run_sim('tb_wave', ['rtl/mv_wave_capture.v', 'tb_wave.v'], 'wave')
        run_sim('tb_visualizer', [str(p.relative_to(ROOT)) for p in (ROOT/'rtl').glob('*.v')]
                + ['tb_visualizer.v'], 'visualizer')
    subprocess.run([sys.executable, 'verify.py'], cwd=ROOT, check=True)
    if args.engine:
        subprocess.run([sys.executable, 'run_engine_isolation.py'], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
