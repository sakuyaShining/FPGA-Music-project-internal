"""Reopen saved PCB and record native full DRC after a route stage."""
import json
import sys
import time
import hashlib
from native_review import ROOT,PROJECT,invoke
from advance_routes import renew

stage=sys.argv[1]
if '--keep-session' not in sys.argv[2:]:renew(stage)
board_path=PROJECT/'pcb/PCB1.epcb2'
before_sha=hashlib.sha256(board_path.read_bytes()).hexdigest()
result=invoke('route-stage-drc-'+stage,'return await eda.pcb_Drc.check(true,false,true);',timeout=240)
raw=json.dumps(result,ensure_ascii=False,indent=2)
(ROOT/'pcb-drc.json').write_text(raw,encoding='utf-8')
(ROOT/('drc-stage-'+stage+'.json')).write_text(raw,encoding='utf-8')
after_sha=hashlib.sha256(board_path.read_bytes()).hexdigest()
(ROOT/('drc-stage-'+stage+'.meta.json')).write_text(json.dumps({'pcb_sha256_before':before_sha,'pcb_sha256_after':after_sha,
        'source_stable_during_drc':before_sha==after_sha,'manufacturing_release':False},indent=2),encoding='utf-8')
print('DRC',[(x['name'],x.get('count')) for x in result],flush=True)
for category in result:
    if category['name']=='Clearance Error':
        print('CLEARANCE TYPES',[(x['name'],x.get('count'),len(x.get('list',[]))) for x in category['list']],flush=True)
    if category['name']=='Connection Error':
        print('PENDING NETS',[x['name'] for x in category['list']],flush=True)
