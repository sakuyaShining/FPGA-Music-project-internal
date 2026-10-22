"""Compare independently exported Protel nets against the intended pin contract."""
import csv
import hashlib
import json
import re
from phase import ROOT

def main():
    expected=json.loads((ROOT/'expected-pin-nets.json').read_text())
    native=(ROOT/'native-protel.net').read_text(encoding='utf-8')
    actual={}; groups={}
    for block in re.findall(r'^\(\s*\n(.*?)^\)',native,re.M|re.S):
        lines=[s.strip() for s in block.splitlines() if s.strip()]
        net=lines[0];pins=[]
        for line in lines[1:]:
            token=line.split()[0]
            ref,pin=token.rsplit('-',1)
            if ref not in expected:raise AssertionError('Unexpected exported ref '+ref)
            key=(ref,pin)
            assert key not in actual,'Pin on two nets '+str(key)
            actual[key]=net;pins.append(token)
        groups[net]=pins
    rows=[]
    for ref,pins in expected.items():
        for pin,wanted in pins.items():
            got=actual.get((ref,pin))
            assert (got==wanted if wanted is not None else got is None),(ref,pin,wanted,got)
            rows.append({'Reference':ref,'Pin':pin,'Expected net':wanted or 'NC','Native net':got or 'NC','Match':True})
    assert set(actual)=={(r,p) for r,ps in expected.items() for p,n in ps.items() if n is not None}
    with (ROOT/'pin-net-audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    status={'status':'已验证','scope':'Native exported pin connectivity against intended draft only; not physical validation',
            'components':len(expected),'pins':len(rows),'connected_pins':len(actual),'intentional_nc':len(rows)-len(actual),
            'nets':len(groups),'mismatches':0,
            'native_drc':json.loads((ROOT/'evidence/native-schematic-drc.json').read_text())['value'],
            'sources':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['native-protel.net','expected-pin-nets.json','pin-net-audit.csv']},
            'manufacturing_release':False}
    (ROOT/'connectivity-audit.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(status,ensure_ascii=True))

if __name__=='__main__':main()
