"""Validate a combined reset-net replacement and two fully connected supply nets."""
from pathlib import Path
import json,math
from exchange import read,OUT,sha
from resume_offline import read_native
from four_layer_geometry import copper,connected
from shapely.geometry import LineString
from shapely.ops import unary_union
cp,pcb,s=read();raw=read_native(pcb)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
audit=json.loads((OUT/'complete-routes-validation.json').read_text());assert audit['geometric_pass']
route=json.loads((OUT/'accepted-complete-copper.json').read_text())
remove=[p for p in s['lines'] if p['net']=='TP_RESET_N'];removeV=[p for p in s['vias'] if p['net']=='TP_RESET_N']
ids={'19df74a6bd526870','eb25d4fa91bd7653','e0b3f1ccd5724d8c','f9536fedfa5eb06f','7e184d61415920ed','7323ef4891e8c60a'}
for p in s['lines']:
    if p['net']!='3V3_IO' or p['layer']!=1:continue
    ps=[(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]
    if p['id'] in ids or all(math.dist(a,z)<.002 for a,z in zip(ps,[(89,48.5),(87.575029,47.074971)])) or all(math.dist(a,z)<.002 for a,z in zip(ps,[(87.575029,47.074971),(87.216775,47.074971)])):remove.append(p)
assert len([p for p in remove if p['net']=='3V3_IO'])==8
p20=next(p for p in s['pads'] if p['ref']=='U15' and p['n']=='20');r61=next(p for p in s['pads'] if p['ref']=='R61' and p['n']=='1')
paths=[('3V3_IO',[(89,48.5),(87.860662,49.639338),(87.860662,50.329465)]),('3V3_PERIPH',[(p20['x']*.0254,p20['y']*.0254),(p20['x']*.0254,r61['y']*.0254),(r61['x']*.0254,r61['y']*.0254)])]
power=[dict(net=n,layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=z[0]/.0254,y2=z[1]/.0254,width=13.2) for n,ps in paths for a,z in zip(ps,ps[1:])]
route['lines']+=power
work={**s,'lines':[p for p in s['lines'] if p not in remove]+route['lines'],'vias':[p for p in s['vias'] if p not in removeV]+route['vias']}
gaps={}
for net in ['3V3_IO','3V3_PERIPH','TP_RESET_N']:
    f,_=copper(work,net);foreign={l:unary_union(q) for l,q in f.items()};values=[]
    for p in route['lines']:
        if p['net']!=net:continue
        q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
        gap=q.distance(foreign[p['layer']])-p['width']*.0254/2
        assert gap>=(.165 if net!='TP_RESET_N' else .158)-1e-7,(net,gap)
        values.append(gap)
    gaps[net]=min(values)
proof={}
for net in ['3V3_IO','3V3_PERIPH','TP_RESET_N','DISP_MOSI','DISP_SCK','VIS_CS_N','VIS_BL_EN']:
    proof[net]=connected([p for p in work['pads'] if p['net']==net],[p for p in work['lines'] if p['net']==net],[p for p in work['vias'] if p['net']==net]);assert proof[net]['complete'],(net,proof[net])
result=dict(source_pcb_sha256=cp['pcb_sha256'],remove_lines=remove,remove_vias=removeV,**route,minimum_clearances_mm=gaps,continuity=proof,manufacturing_release=False,rationale='Replace the complete TP_RESET_N net, preserve failed-net copper. Remove the obsolete leftward 3V3_IO stub and reconnect its lower branch farther south. This opens a direct original-width U15/C35 peripheral supply feed without added power vias.')
(OUT/'combined-plan.json').write_text(json.dumps(result,indent=2),encoding='utf8');assert sha(pcb)==cp['pcb_sha256']
print(json.dumps(dict(remove_lines=len(remove),remove_vias=len(removeV),new_lines=len(route['lines']),new_vias=len(route['vias']),minimum_clearances_mm=gaps,continuity=proof),indent=2))
