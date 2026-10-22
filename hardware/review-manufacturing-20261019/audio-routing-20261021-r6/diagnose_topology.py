"""Offline grid-connectivity ablation; never changes native copper.
Diagnose whether preserved power/ground trunks or future-pin guards form cuts.
"""
import sys,json,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;OUT=Path(__file__).resolve().parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
from scipy import ndimage
from shapely.geometry import LineString
sys.path.insert(0,str(ROOT));import grid_route as g
from physical_geometry import actual_pad
from resume_offline import read_native
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text());PCB=Path(cp['project'])/'pcb/PCB1.epcb2';assert hashlib.sha256(PCB.read_bytes()).hexdigest()==cp['pcb_sha256'];s=json.loads((ROOT/cp['source_capture']).read_text());raw=read_native(PCB)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]];s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
nets=['I2S_LRCK','I2S_DIN','I2S_BCK'];g.pad_shape=actual_pad;g.GRID=.05;bounds=(.45,.45,139.55,99.55);nx=round((bounds[2]-bounds[0])/g.GRID)+1;ny=round((bounds[3]-bounds[1])/g.GRID)+1
w={**s,'lines':[p for p in s['lines'] if p['net'] not in nets],'vias':[p for p in s['vias'] if p['net'] not in nets]}
guards=[]
for p in s['pads']:
 if p['net'] not in cp['pending_nets'] or p['layer']!=1 or min(p['shape'][1:3])*.0254>.65:continue
 angle=math.radians(p['rotation']);ax=(math.cos(angle),math.sin(angle)) if p['shape'][1]>=p['shape'][2] else (-math.sin(angle),math.cos(angle));x,y=p['x']*.0254,p['y']*.0254;guards.append(LineString([(x-ax[0]*1.7,y-ax[1]*1.7),(x+ax[0]*1.7,y+ax[1]*1.7)]).buffer(.0762))
rows=[]
cases=[('physical_only',[],False),('with_future_pin_guards',[],True),('remove_IO_top_tracks',['3V3_IO'],True),('remove_5V_top_tracks',['5V_PERIPH'],True),('remove_PERIPH_top_tracks',['3V3_PERIPH'],True),('remove_GND_top_tracks',['GND'],True),('remove_IO_and_GND_top_tracks',['3V3_IO','GND'],True)]
for name,rm,guard in cases:
 data={**w,'lines':[p for p in w['lines'] if not(p['layer']==1 and p['net'] in rm)]};pernet=[]
 for net in nets:
  f,_,ko=g.geometries(data,net);blocked=g.raster(f[1]+ko+(guards if guard else []),bounds,.1524/2+.165+g.GRID/math.sqrt(2),(ny,nx));lab,num=ndimage.label(~blocked,structure=[[0,1,0],[1,1,1],[0,1,0]]);pairs=[]
  for pad in [p for p in s['pads'] if p['net']==net]:
   x=round((pad['x']*.0254-bounds[0])/g.GRID);y=round((pad['y']*.0254-bounds[1])/g.GRID);pairs.append(dict(pin=pad['ref']+'.'+pad['n'],x_mm=pad['x']*.0254,y_mm=pad['y']*.0254,component=int(lab[y,x])))
  ids={p['component'] for p in pairs};connected=len(ids)==1 and 0 not in ids;pernet.append(dict(net=net,pads=pairs,same_grid_component=connected))
 row=dict(case=name,removed_top_track_nets=rm,future_pin_guards=guard,results=pernet);rows.append(row);print(name,[(x['net'],x['same_grid_component'],[p['component'] for p in x['pads']]) for x in pernet],flush=True)
(OUT/'topology-ablation.json').write_text(json.dumps(dict(source_pcb_sha256=cp['pcb_sha256'],grid_mm=.05,diagnostic_only=True,native_unchanged=True,not_proof_of_a_valid_continuous_route=True,cases=rows),indent=2))
