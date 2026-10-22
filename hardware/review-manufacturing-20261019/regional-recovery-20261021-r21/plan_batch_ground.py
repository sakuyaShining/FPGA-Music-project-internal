"""Select actual dual-reference GND stitches near new HARM transitions."""
from pathlib import Path
import sys,json,math,hashlib,re
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(BASE))
from native_project import PROJECT
from resume_offline import read_native
from native_plane_geometry import poured_planes
from physical_geometry import actual_pad
from four_layer_geometry import copper
pcb=PROJECT/'pcb/PCB1.epcb2';source_sha=hashlib.sha256(pcb.read_bytes()).hexdigest()
s=json.loads((BASE/'native-batch-capture.json').read_text(encoding='utf-8'));raw=read_native(pcb);planes=poured_planes(raw)
s['lines']=[dict(net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
audit=json.loads((BASE/'native-batch-apply.json').read_text(encoding='utf-8'));ids=set(audit['result']['createdV']);signals=[v for v in s['vias'] if v['id'] in ids]
f,pads=copper(s,'GND');foreign=unary_union([q for qs in f.values() for q in qs]);padunion=unary_union(pads)
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
references=[]
for v in s['vias']:
    if v['net']!='GND':continue
    q=Point(v['x']*.0254,v['y']*.0254);ring=q.buffer(v['diameter']*.0254/2,quad_segs=48).difference(q.buffer(v['hole']*.0254/2,quad_segs=48))
    if all(ring.intersection(planes[l]).area>1e-5 for l in [15,2]):references.append((q,{'type':'via','id':v['id']}))
for p in s['pads']:
    if p['net']=='GND' and p['layer']==12 and all(actual_pad(p).intersection(planes[l]).area>1e-5 for l in [15,2]):references.append((Point(p['x']*.0254,p['y']*.0254),{'type':'plated_ground_pad','id':p['id'],'ref':p['ref'],'pin':p['n']}))
before=[]
for v in signals:
    q=Point(v['x']*.0254,v['y']*.0254);pt,ref=min(references,key=lambda a:q.distance(a[0]));before.append(dict(signal_id=v['id'],xy_mm=[q.x,q.y],nearest_reference=ref,distance_mm=q.distance(pt)))
candidates=[];seen=set()
for v in signals:
    for radius in [.9,1.,1.1,1.2,1.3,1.4,1.5]:
        for i in range(32):
            angle=i*math.pi/16;x=round(v['x']*.0254+radius*math.cos(angle),6);y=round(v['y']*.0254+radius*math.sin(angle),6)
            if (x,y) in seen:continue
            seen.add((x,y));q=Point(x,y)
            if q.distance(foreign)-.3048<.165 or q.distance(padunion)-.1524<.25 or q.distance(quiet)-.3048<.158 or q.distance(mount)-.3048<.15:continue
            if any(q.distance(Point(p['x']*.0254,p['y']*.0254))-(12+p['hole'])*.0254/2<.35 for p in s['vias']):continue
            ring=q.buffer(.3048,quad_segs=64).difference(q.buffer(.1524,quad_segs=64));contacts={str(l):ring.intersection(planes[l]).area for l in [15,2]}
            if min(contacts.values())<.15:continue
            covered=[p['signal_id'] for p in before if q.distance(Point(p['xy_mm']))<=1.50001]
            candidates.append(dict(net='GND',x=x/.0254,y=y/.0254,diameter=24,hole=12,xy_mm=[x,y],covers=covered,predicted_reference_contact_mm2=contacts))
remaining={p['signal_id'] for p in before if p['distance_mm']>1.5};chosen=[]
while remaining:
    eligible=[p for p in candidates if set(p['covers'])&remaining and all(math.dist(p['xy_mm'],q['xy_mm'])-.3048>=.35 for q in chosen)]
    if not eligible:break
    def score(p):
        covered=set(p['covers'])&remaining
        distances=[math.dist(p['xy_mm'],q['xy_mm']) for q in before if q['signal_id'] in covered]
        return (-len(covered),max(distances),-min(p['predicted_reference_contact_mm2'].values()))
    best=min(eligible,key=score);chosen.append(best);remaining-=set(best['covers']);candidates.remove(best)
result=dict(source_pcb_sha256=source_sha,reference_layers=[15,2],signal_reference_connections_before=before,engineering_distance_goal_mm=1.5,
            distance_goal_is_not_a_standard_or_si_signoff=True,vias=chosen,uncovered_signal_ids=sorted(remaining),safe_candidates=len(candidates)+len(chosen),native_imported=False,manufacturing_release=False,
            rationale='Join the same GND net across actual top/inner-route reference planes; share a stitch when geometry permits. Avoid sensing/audio projection guards and preserve all source copper.')
(BASE/'reconnections-ground-plan.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==source_sha
print(json.dumps(result,indent=2),flush=True)
