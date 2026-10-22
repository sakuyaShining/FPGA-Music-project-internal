import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
config=json.loads((ROOT/'audition-config.json').read_text(encoding='utf-8'))
lo,hi=config['fader_y_min'],config['fader_y_max'];unity=config['unity_q8'];depth=config['max_gain_q8']-unity
assert 0<=lo<hi<=1023 and 256==unity<=unity+depth<=1023
assert (lo,hi)==(52,420),'Update the example panel geometry and fixtures together before changing coordinate bounds'
assert len(config['part_to_control'])==16 and all(type(x) is int and 0<=x<8 for x in config['part_to_control'])
values=[unity+depth*(hi-max(lo,min(hi,y)))//(hi-lo) for y in range(1024)]
path=ROOT/'fader_gain_q8.hex';path.write_text('\n'.join('%03x'%v for v in values)+'\n',encoding='ascii')
(ROOT/'assets.json').write_text(json.dumps(dict(config_sha256=hashlib.sha256((ROOT/'audition-config.json').read_bytes()).hexdigest(),gain_lut_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),entries=len(values),unity=values[hi],maximum=values[lo]),indent=2),encoding='utf-8')
print('Generated replaceable 1024-entry Q8 audition table')
