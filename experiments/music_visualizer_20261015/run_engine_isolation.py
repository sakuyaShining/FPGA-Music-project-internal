import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DST = ROOT / 'engine_probe'
sources = [str(p.name) for p in DST.glob('*.v')
           if p.name not in ('music_visualizer_engine_probe.v', 'resource_core_probe.v')]
subprocess.run(['D:/iverilog/bin/iverilog.exe', '-g2012', '-I', '.', '-s', 'tb_engine_isolation',
                '-o', 'engine-isolation.vvp', *sources, '../tb_engine_isolation.v'], cwd=DST, check=True)
with (ROOT / 'engine-isolation.log').open('w') as log:
    subprocess.run(['D:/iverilog/bin/vvp.exe', 'engine-isolation.vvp'], cwd=DST,
                   stdout=log, stderr=subprocess.STDOUT, check=True)
print((ROOT / 'engine-isolation.log').read_text())
