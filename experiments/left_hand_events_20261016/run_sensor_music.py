"""Actual 595 control, ideal Schmitt transitions, then real voice/PCM chain."""
from pathlib import Path
import hashlib,json
from run_validation import ROOT,E,IV,VVP,run
files=[p for p in (ROOT/'engine').glob('*.v') if p.name!='pitch_mod.v']+list((ROOT/'candidate').glob('*.v'))+list((ROOT/'rtl').glob('*.v'))+[ROOT/'optimization/pitch_mod.v',ROOT/'tb_sensor_music.v']
run([IV,'-g2012','-I',str(ROOT/'rtl'),'-s','tb_sensor_music','-o',str(E/'sensor-music.vvp'),*[str(p) for p in files]],'compile-sensor-music')
text=run([VVP,str(E/'sensor-music.vvp')],'run-sensor-music',cwd=ROOT/'engine')
assert 'PASS sensor_music' in text
inputs=files+list((ROOT/'engine').glob('*.hex'))+list((ROOT/'rtl').glob('*.vh'))+[Path(__file__).resolve()]
(E/'sensor-music-validation.json').write_text(json.dumps(dict(status='PASS digital end-to-end sensor timing to real PCM',analog_hardware_tested=False,optimized_glide_selected=True,display_refresh_tested=False,log=text,inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}),indent=2),encoding='utf-8')
