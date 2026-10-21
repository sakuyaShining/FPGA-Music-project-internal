"""Reuse the established exchange/router against fresh R21 native geometry."""
from pathlib import Path
import json,sys,hashlib,shutil
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(BASE))
from native_project import invoke,PROJECT,info
sys.path.insert(0,str(ROOT))
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
import grid_route as g
g.invoke=invoke
capture=g.capture()
(BASE/'source-capture.json').write_text(json.dumps(capture),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
meta=dict(project=str(PROJECT),pcb_sha256=sha(PROJECT/'pcb/PCB1.epcb2'))
assert meta['pcb_sha256']==info['source_pcb_sha256']
(BASE/'source-meta.json').write_text(json.dumps(meta,indent=2),encoding='utf8')
selected=['TP_RESET_MOD_N','TP_RESET_N','VIS_CS_N','VIS_BL_EN','BUS_RETURN','VIS_DC','DISP_RESET_N','DISP_VIS_DC','HARM_CS_N','BUS_SCK','BUS_MOSI','DISP_MOSI']
(BASE/'regional-edit-plan.json').write_text(json.dumps(dict(routing_nets=selected),indent=2),encoding='utf8')
old=ROOT/'regional-signals-20261021-r20'
text=(old/'exchange.py').read_text(encoding='utf8')
start=text.index('def read():');end=text.index('\ndef build():',start)
text=text[:start]+'''def read():
    cp=json.loads((OUT/'source-meta.json').read_text(encoding='utf8'))
    pcb=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(pcb)==cp['pcb_sha256']
    s=json.loads((OUT/'source-capture.json').read_text(encoding='utf8'));raw=read_native(pcb)
    s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in LAYERS]
    s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
    return cp,pcb,s
''' +text[end:]
(BASE/'exchange.py').write_text(text,encoding='utf8')
for name in ['ses.py','run_bounded.py']:shutil.copy2(old/name,BASE/name)
from ses import parse
calibration=ROOT/'freerouting-comparison-20261021-r14/calibration.ses'
prior=json.loads((old/'calibration-result.json').read_text())
assert sha(calibration)==prior['ses_sha256']
test=parse(calibration.read_text(),{'CAL'})
assert len(test['vias'])==1 and {p['layer'] for p in test['lines']}=={1,16}
assert all(p['width']==6 for p in test['lines'])
assert any(p['layer']==1 and (p['x2'],p['y2'])==(200,300) for p in test['lines'])
assert any(p['layer']==16 and (p['x1'],p['y1'])==(800,700) for p in test['lines'])
assert test['vias'][0]==dict(net='CAL',x=200.,y=260.938,diameter=24.,hole=12)
(BASE/'calibration-result.json').write_text(json.dumps(dict(passed=True,method='Replay preserved asymmetric calibration SES with current parser; verify endpoint coordinates, distinct layers, width and forced through-via',source_parser_sha256=sha(BASE/'ses.py'),ses_sha256=sha(calibration),historical_parser_sha256=prior['source_parser_sha256'],historical_parser_hash_matches=False),indent=2),encoding='utf8')
print(json.dumps(dict(source=meta,selected=selected)),flush=True)
