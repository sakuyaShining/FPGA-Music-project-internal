"""Explain local escapes and power islands from actual current saved copper."""
import collections,hashlib,json,math,sys
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
import grid_route as grid
from physical_geometry import actual_pad
from resume_offline import read_native

read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
d=read(ROOT/'quality-r1-source-78.json');before=sha(PCB)
assert before==read(ROOT/'route-checkpoint-0clear-78open-quality-r1-20261021.json')['pcb_sha256']
v=read_native(PCB);native_vias={i:p for (k,i),p in v.items() if k=='VIA'}
for p in d['vias']:
    p['diameter']=native_vias[p['id']]['viaDiameter'];p['hole']=native_vias[p['id']]['holeDiameter']
ids={p['id'] for p in d['lines']}
for (k,i),p in v.items():
    if k=='LINE' and p.get('layerId') in [1,2] and i not in ids:
        d['lines'].append(dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']))

def objects(data,net=None):
    out=[]
    for p in data['pads']:
        if net is not None and p['net']!=net:continue
        out.append(dict(mask=3 if p['layer']==12 else 1<<(p['layer']-1),shape=actual_pad(p),kind='pad',p=p))
    for p in data['lines']:
        if net is not None and p['net']!=net:continue
        out.append(dict(mask=1<<(p['layer']-1),shape=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2),kind='line',p=p))
    for p in data['vias']:
        if net is not None and p['net']!=net:continue
        out.append(dict(mask=3,shape=Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2),kind='via',p=p))
    return out

obs=objects(d,'5V_PERIPH');parents=list(range(len(obs)))
def root(i):
    while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
    return i
for i,a in enumerate(obs):
    for j,b in enumerate(obs[:i]):
        if a['mask']&b['mask'] and a['shape'].distance(b['shape'])<.000005:parents[root(i)]=root(j)
groups={}
for i,o in enumerate(obs):groups.setdefault(root(i),[]).append(o)
groups=[g for g in groups.values() if any(o['kind']=='pad' for o in g)]
power=[dict(group=i,pads=[(o['p']['ref'],o['p']['n']) for o in g if o['kind']=='pad'],
    lines=sum(o['kind']=='line' for o in g),vias=sum(o['kind']=='via' for o in g)) for i,g in enumerate(groups)]
selected=set(read(OUT/'joint-plan.json')['pending_nets']+read(OUT/'joint-plan.json')['ripped_connected_nets'])
free={**d,'lines':[p for p in d['lines'] if p['net'] not in selected],'vias':[p for p in d['vias'] if p['net'] not in selected]}
cases=[]
for ref,pin in [('U7','6'),('U9','5'),('U15','7')]:
    pad=next(p for p in d['pads'] if p['ref']==ref and p['n']==pin);origin=(pad['x']*.0254,pad['y']*.0254)
    for label,data in [('current',d),('joint_trunks_removed',free)]:
        local=[o for o in objects(data) if o['p']['net']!=pad['net'] and o['shape'].distance(Point(origin))<5]
        pads=unary_union([actual_pad(p) for p in d['pads']]);blockers=collections.Counter();routes=[]
        for radius in [1.25,1.75,2.25,3.0]:
            for degrees in range(0,360,15):
                angle=math.radians(degrees);end=(origin[0]+radius*math.cos(angle),origin[1]+radius*math.sin(angle))
                trace=LineString([origin,end]);via=Point(end)
                blocked=[]
                for o in local:
                    if ((o['mask']&(1<<(pad['layer']-1))) and trace.distance(o['shape'])<.1524/2+.17) or via.distance(o['shape'])<.6096/2+.17:
                        blocked.append(o)
                for o in blocked:blockers[o['p']['net']]+=1
                if not blocked and via.distance(pads)>=.3048/2+.25:
                    routes.append(dict(radius_mm=radius,degrees=degrees,end_mm=end))
        nearest=sorted(local,key=lambda o:o['shape'].distance(Point(origin)))[:8]
        cases.append(dict(ref=ref,pin=pin,net=pad['net'],scenario=label,checked_straight_rays=96,
            straight_escapes_with_via=routes,frequent_blocking_nets=blockers.most_common(8),
            nearest_foreign_copper=[dict(net=o['p']['net'],kind=o['kind'],id=o['p']['id'],center_gap_mm=o['shape'].distance(Point(origin))) for o in nearest]))
result=dict(pcb_sha256=before,source_sha256=sha(ROOT/'quality-r1-source-78.json'),
    power_pad_islands=power,local_escapes=cases,
    scope='Straight-ray diagnostic only; absence is not proof that no bent path or better layout exists. No native mutation or DRC.',manufacturing_release=False)
(OUT/'bottleneck-results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
assert sha(PCB)==before
print('POWER PAD ISLANDS',power)
for c in cases:print(c['ref'],c['pin'],c['scenario'],'rays',len(c['straight_escapes_with_via']),'blockers',c['frequent_blocking_nets'][:4])
