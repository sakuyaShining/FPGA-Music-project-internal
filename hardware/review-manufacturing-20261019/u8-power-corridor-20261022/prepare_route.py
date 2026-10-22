"""Reuse short pin-escape search with real four-layer obstacles after the rail edit."""
from pathlib import Path
import sys,json,re,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
import reserve_escape as escape
from four_layer_geometry import copper
from shapely.geometry import LineString,box
from shapely.ops import unary_union
read=lambda p:json.loads(p.read_text(encoding='utf8'))
plan=read(OUT/'plan.json');assert plan['geometric_pass'];s=read(OUT/'source-capture.json')
assert hashlib.sha256((Path(plan['project'])/'pcb/PCB1.epcb2').read_bytes()).hexdigest()==plan['source_pcb_sha256']
remove={p['id'] for p in plan['remove_lines']};removev={p['id'] for p in plan['remove_vias']}
work={**s,'lines':[p for p in s['lines'] if p['id'] not in remove]+plan['lines'],'vias':[p for p in s['vias'] if p['id'] not in removev]+plan['vias']}
quiet=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in work['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))]
mount=[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]
def geometry(data,net):
 f,pads=copper(data,net)
 return {1:f[1],2:f[15]+f[16]+f[2]+quiet},pads,mount
escape.geometries=geometry
# Search only the changed local bus exits; no global raster router is built.
result=escape.grid_mux_fanouts(work,['BUS_MOSI','BUS_SCK'],refs=['U8','U9','U15','R63','R64','TP13','TP14'],max_pad_short_mm=10)
result.update(source_pcb_sha256=plan['source_pcb_sha256'],plan_sha256=hashlib.sha256((OUT/'plan.json').read_bytes()).hexdigest())
(OUT/'bus-escapes.json').write_text(json.dumps(result,indent=2))
for net,ref,pin in result['new_fanouts']:print('ESCAPED',ref,pin,net,flush=True)
print('TOTAL',len(result['new_fanouts']),len(result['lines']),len(result['vias']),flush=True)
