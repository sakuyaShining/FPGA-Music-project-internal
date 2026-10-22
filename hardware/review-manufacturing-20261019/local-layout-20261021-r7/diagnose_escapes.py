"""Local top free components and full-stack via access; no native changes."""
import sys,json,math,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
assert not (BASE/'native-candidate-checkpoint.json').exists(), 'Accepted r7 stage is frozen; continue in a new source-bound stage instead of replaying it'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(ROOT))
import grid_route as g
from four_layer_geometry import copper
from resume_offline import read_native
from scipy.ndimage import label
from shapely.geometry import box
from shapely.ops import unary_union
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'));s=json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'));PCB=Path(cp['project'])/'pcb/PCB1.epcb2';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert sha(PCB)==cp['pcb_sha256'];raw=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
g.GRID=.025;g.GAP=.165;g.WIDTH=.1524
rows=[]
for net in ['INV2','PRESET3','DISP_SCK','DISP_MOSI','BUS_SCK','BUS_MOSI','HARM_CS_N']:
 f,ps=copper(s,net);allcu=[q for gs in f.values() for q in gs]
 for p in s['pads']:
  if p['net']!=net or p['layer']!=1 or not p['ref'].startswith('U'):continue
  x,y=p['x']*.0254,p['y']*.0254;bounds=(x-4,y-4,x+4,y+4);shape=(321,321)
  blocked=g.raster(f[1],bounds,g.WIDTH/2+g.GAP+g.GRID*math.sqrt(2),shape)
  labels,n=label(~blocked);island=labels[160,160];reachable=(labels==island) if island else g.np.zeros(shape,dtype=bool)
  via=g.raster(allcu,bounds,.6096/2+g.GAP+g.GRID*math.sqrt(2),shape)|g.raster(ps,bounds,.3048/2+.25+g.GRID*math.sqrt(2),shape)
  eligible=reachable&(~via);yy,xx=g.np.nonzero(eligible);nearest=[]
  if len(xx):
   order=g.np.argsort((xx-160)**2+(yy-160)**2)[:5];nearest=[dict(x_mm=bounds[0]+xx[i]*g.GRID,y_mm=bounds[1]+yy[i]*g.GRID,distance_mm=math.hypot(xx[i]-160,yy[i]-160)*g.GRID) for i in order]
  boundary=bool(reachable[0,:].any() or reachable[-1,:].any() or reachable[:,0].any() or reachable[:,-1].any())
  row=dict(net=net,ref=p['ref'],pin=p['n'],x_mm=x,y_mm=y,start_blocked=not bool(island),top_component_touches_local_boundary=boundary,local_via_cells=int(eligible.sum()),nearest_via_cells=nearest)
  rows.append(row);print(row,flush=True)
assert sha(PCB)==cp['pcb_sha256'];(BASE/'escape-diagnosis.json').write_text(json.dumps(dict(source_pcb_sha256=cp['pcb_sha256'],local_margin_mm=4,grid_mm=g.GRID,not_a_global_impossibility_proof=True,rows=rows),indent=2),encoding='utf-8')
