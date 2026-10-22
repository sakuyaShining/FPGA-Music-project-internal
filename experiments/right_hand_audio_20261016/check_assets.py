"""Verify generator-only validation changes without re-running unchanged RTL."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
lut=ROOT/'fader_gain_q8.hex';before=sha(lut)
r=subprocess.run([sys.executable,str(ROOT/'generate_assets.py')],cwd=ROOT,capture_output=True,text=True)
assert r.returncode==0,r.stderr
assert before==sha(lut),'Generated data changed; re-run functional validation'
config=json.loads((ROOT/'audition-config.json').read_text(encoding='utf-8'))
values=[int(s,16) for s in lut.read_text().split()]
lo,hi=config['fader_y_min'],config['fader_y_max']
assert len(values)==1024 and values[lo]==config['max_gain_q8'] and values[hi]==256
assert all(a>=b for a,b in zip(values,values[1:]))
assert all(v==256+(config['max_gain_q8']-256)*(hi-max(lo,min(hi,y)))//(hi-lo) for y,v in enumerate(values))
record=dict(status='PASS asset generation and all1024 values',generator_sha256=sha(ROOT/'generate_assets.py'),lut_sha256=sha(lut),config_sha256=sha(ROOT/'audition-config.json'),generated_data_unchanged=True,reason='Added geometry/map validation assertions only; generated data and validated RTL unchanged')
(ROOT/'evidence/assets-check.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record))
