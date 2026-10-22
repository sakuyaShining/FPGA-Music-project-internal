from pathlib import Path
import json,random
from slot_format import encode,decode,example
R=Path(__file__).resolve().parent;E=R/'evidence';E.mkdir(exist_ok=True)
rng=random.Random(70);n=0
for _ in range(100):
    parts=[dict(ratio_q8=rng.randint(1,65535),amplitude=rng.randint(0,255),sustain_q15=rng.randint(0,32768),decay_m=rng.randint(1,3),decay_k=rng.randint(0,31)) for k in range(16)]
    assert decode(encode(parts))==parts;n+=1
for field,value in [('ratio_q8',0),('amplitude',256),('sustain_q15',32769),('decay_m',0),('decay_k',32),('amplitude',True),('attack_ms',5)]:
    parts=example(24576);parts[0][field]=value
    try:encode(parts)
    except ValueError:pass
    else:raise AssertionError((field,value))
for name,sustain in [('sustain',24576),('strike',0)]:
    parts=example(sustain)
    (R/(name+'.json')).write_text(json.dumps(parts,indent=2),encoding='utf-8')
    (R/(name+'.hex')).write_text(''.join('%012x\n'%w for w in encode(parts)),encoding='ascii')
(E/'slot-format.json').write_text(json.dumps(dict(status='PASS',random_round_trips=n,invalid_inputs_rejected=7,scope='low-level v0 only; GUI schema and wire protocol not integrated'),indent=2),encoding='utf-8')
print('PASS slot format: 100 random round trips, 7 invalid inputs rejected')
