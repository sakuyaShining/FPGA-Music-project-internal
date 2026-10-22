import importlib.util
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
tree=ROOT/'sim_build/board_diag_20261009/diagnostic_v5'
spec=importlib.util.spec_from_file_location('r',tree/'tools/scripts/regress_all.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
r.BUILD=str(ROOT/'sim_build/board_diag_20261009/sim')
files=[str(p) for p in (tree/'src/rtl').glob('*.v')]
files.append(str(ROOT/'src/board_diag/tb_board_diag.v'))
log,error=r.compile_and_run('diagnostic_uart',files,defines=('SIM_INIT',),need_hex=True)
output=error or log or ''
(ROOT/'sim_build/board_diag_20261009/diagnostic-sim.log').write_text(output,encoding='utf-8')
print(output[-5000:])
sys.exit(0 if not error and 'RESULT board_diag=PASS' in output and 'FAIL ' not in output else 1)
