"""Correct two resistor placements after native test-pad clearance review."""
from pathlib import Path
import sys,json,hashlib,ast
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import invoke,PROJECT,info
from resume_offline import read_native
from physical_geometry import actual_pad
from shapely.geometry import Point,LineString
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
meta=json.loads((BASE/'native-layout-drc-meta.json').read_text(encoding='utf8'))
assert sha(PROJECT/'pcb/PCB1.epcb2')==meta['pcb_sha256']
assert not (BASE/'testpoint-clearance-correction.json').exists()
layout=json.loads((BASE/'selected-layout.json').read_text(encoding='utf8'));changes=[p for p in layout['selected_variant']['changes'] if p['ref'] in ['R63','R64']]
raw=read_native(PROJECT/'pcb/PCB1.epcb2');removeL={};removeV={}
for m in changes:
    for p in m['expected_pads']:
        q=actual_pad(p)
        for (k,i),v in raw.items():
            if k=='LINE' and v.get('layerId')==1 and v.get('netName')!=p['net']:
                shape=LineString([(v['startX']*.0254,v['startY']*.0254),(v['endX']*.0254,v['endY']*.0254)]).buffer(v['width']*.0254/2,quad_segs=32)
                if shape.distance(q)<.165:removeL[i]=dict(id=i,net=v['netName'])
            if k=='VIA':
                pt=Point(v['centerX']*.0254,v['centerY']*.0254)
                if (v['netName']!=p['net'] and pt.distance(q)-v['viaDiameter']*.0254/2<.165) or pt.distance(q)-v['holeDiameter']*.0254/2<.25:removeV[i]=dict(id=i,net=v['netName'])
# Reuse the already exercised mutation code instead of implementing another router/API layer.
tree=ast.parse((BASE/'prepare_and_apply_layout.py').read_text(encoding='utf8'))
code=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in n.targets))
result=invoke('correct-testpad-clearance',code,dict(project=info['parent_project_uuid'],changes=changes,remove_lines=list(removeL.values()),remove_vias=list(removeV.values())),180)
import grid_route as g;g.invoke=invoke;cap=g.capture()
(BASE/'native-layout-capture.json').write_text(json.dumps(cap),encoding='utf8')
audit=dict(source_pcb_sha256=meta['pcb_sha256'],pcb_sha256_after=sha(PROJECT/'pcb/PCB1.epcb2'),result=result,reason='Native DRC found R63 overlapping fixed I2C_SDA TP11; include every free test pad in placement screening. Move R64 away from TP12 clearance edge as well.',manufacturing_release=False)
(BASE/'testpoint-clearance-correction.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf8')
print(json.dumps(audit,indent=2),flush=True)
