"""Adjust C35 after native device spacing rejection, preserving existing GND via."""
import sys,json,math,hashlib,shutil
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
assert not (BASE/'native-candidate-checkpoint.json').exists(), 'Accepted r7 stage is frozen; continue in a new source-bound stage instead of replaying it'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
from four_layer_geometry import copper,connected
from physical_geometry import actual_pad
from resume_offline import read_native
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
info=json.loads((BASE/'native-candidate-source.json').read_text(encoding='utf-8'));PCB=Path(info['candidate_project'])/'pcb/PCB1.epcb2';meta=json.loads((BASE/'native-drc-meta.json').read_text(encoding='utf-8'));assert sha(PCB)==meta['pcb_sha256_after']
source=json.loads((BASE/'native-verified-capture.json').read_text(encoding='utf-8'));s={**source};raw=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
audit=json.loads((BASE/'native-decoupling-audit.json').read_text(encoding='utf-8'));remove=audit['result']['createdL'];retained=next(p for p in s['vias'] if p['id']==audit['result']['createdV'][0]);w={**s,'pads':[p for p in s['pads'] if p['ref']!='C35'],'lines':[p for p in s['lines'] if p['id'] not in remove]}
oldpads=[p for p in s['pads'] if p['ref']=='C35'];pads=[{**p,'x':(77+(.7 if p['n']=='1' else -.7))/.0254,'y':46.8/.0254,'rotation':0} for p in oldpads];power=next(p for p in pads if p['n']=='1');ground=next(p for p in pads if p['n']=='2');vcc=next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='20')
def line(net,a,b,width):return dict(net=net,layer=1,x1=a[0],y1=a[1],x2=b[0],y2=b[1],width=width/.0254)
ls=[line('3V3_PERIPH',(power['x'],power['y']),(vcc['x'],vcc['y']),.33528),line('GND',(ground['x'],ground['y']),(retained['x'],retained['y']),.254)];work={**w,'pads':w['pads']+pads,'lines':w['lines']+ls}
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
text=(BASE/'plan_decoupling.py').read_text(encoding='utf-8');exec(text[text.index('def validate('):text.index('results=[]')],globals())
gap=validate(work,pads,ls,[retained]);assert connected([p for p in work['pads'] if p['net']=='3V3_PERIPH'],[p for p in work['lines'] if p['net']=='3V3_PERIPH'],[p for p in work['vias'] if p['net']=='3V3_PERIPH'])['complete']
length=math.hypot(power['x']-vcc['x'],power['y']-vcc['y'])*.0254;assert length<2.6
plan=dict(source_pcb_sha256=sha(PCB),source_capture=str(BASE/'native-verified-capture.json'),source_capture_sha256=sha(BASE/'native-verified-capture.json'),component='C35',component_x_mm=77.,component_y_mm=46.8,component_rotation=180,pads=pads,remove_line_ids=remove,remove_via_ids=[],lines=ls,vias=[],retained_ground_via_id=retained['id'],min_gap_mm=gap,vcc_centerline_mm=length,ground_stub_mm=math.hypot(ground['x']-retained['x'],ground['y']-retained['y'])*.0254,device_x_bbox_gap_estimate_mm=.6225,requires_native_device_spacing_check=True,native_imported=False,manufacturing_release=False)
(BASE/'decoupling-courtyard-repair-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8');(BASE/'decoupling-repaired-working.json').write_text(json.dumps(work),encoding='utf-8')
for name in ['native-drc.json','native-drc-meta.json','native-verified-capture.json']:
 p=BASE/('first-position-'+name);assert not p.exists();shutil.copy2(BASE/name,p)
print(json.dumps({k:v for k,v in plan.items() if k not in ['pads','lines']},indent=2),flush=True)
