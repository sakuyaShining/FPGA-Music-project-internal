"""Release must preserve the current sounding slot spectrum, including refreshes."""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[2]
out=root/'sim_build/release-continuity'
out.mkdir(parents=True,exist_ok=True)
(out/'sine256.hex').write_bytes((root/'src/gowin/tdm_synth/sine256.hex').read_bytes())
iv=Path('D:/iverilog/bin')
subprocess.run([str(iv/'iverilog.exe'),'-g2012','-DSIM_INIT','-s','tb_release_continuity',
 '-o',str(out/'test.vvp'),*[str(root/'src/rtl'/f) for f in ('tdm_engine.v','osc_env.v','pitch_mod.v')],
 str(root/'src/sim/tb_release_continuity.v')],check=True)
r=subprocess.run([str(iv/'vvp.exe'),str(out/'test.vvp')],cwd=out,capture_output=True,text=True,timeout=150)
(out/'result.log').write_text(r.stdout+r.stderr,encoding='utf-8')
print(r.stdout)
if r.returncode or 'RESULT release_continuity=PASS' not in r.stdout:
 raise SystemExit(1)
