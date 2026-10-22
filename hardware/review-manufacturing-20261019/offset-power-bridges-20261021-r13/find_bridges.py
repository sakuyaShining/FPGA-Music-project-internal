"""Find clearance-safe local inner16 bridge candidates across blocking top rails."""
from pathlib import Path
import sys,json,math,hashlib
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
sys.path.insert(0,str(ROOT))
from four_layer_geometry import copper,connected
from physical_geometry import actual_pad
from resume_offline import read_native
cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
pcb=Path(cp['project'])/'pcb/PCB1.epcb2';assert hashlib.sha256(pcb.read_bytes()).hexdigest()==cp['pcb_sha256']
s=json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'));raw=read_native(pcb)
s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
graph=json.loads((ROOT/'topology-graph-20261021-r12/graph.json').read_text(encoding='utf-8'));geom=json.loads((ROOT/'topology-graph-20261021-r12/geometry.json').read_text(encoding='utf-8'))
topregions=[shapely.from_wkb(h) for h in geom['regions']['1']];tree=STRtree(topregions)
quiet=unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in s['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or p['net'].startswith('RC') or __import__('re').match(r'L[0-5]_',p['net']))])
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
padshapes=unary_union([actual_pad(p) for p in s['pads']])
def where(p):return next((int(i) for i in tree.query(p) if topregions[int(i)].covers(p)),None)
def segment(net,layer,a,b,width):return dict(net=net,layer=layer,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=width)
probe=json.loads((ROOT/'topology-graph-20261021-r12/top-barrier-probe.json').read_text(encoding='utf-8'));byid={p['id']:p for p in s['lines']}
ids={r['id'] for row in probe['terminals'] for r in row['boundary_lines'] if r['net'] in ['3V3_IO','DISP_RESET_N']}
cache={};valid=[];failure={}
for lineid in sorted(ids):
    p=byid[lineid];a=(p['x1']*.0254,p['y1']*.0254);b=(p['x2']*.0254,p['y2']*.0254);length=math.dist(a,b)
    if length<3.1:continue
    net=p['net']
    if net not in cache:
        f,_=copper(s,net);cache[net]=(unary_union([q for qs in f.values() for q in qs]),unary_union(f[16]),unary_union(f[1]))
    foreign,inner,top=cache[net];ux,uy=(b[0]-a[0])/length,(b[1]-a[1])/length
    reason_counts={}
    for j in range(math.ceil((length-3.0)/.5)+1):
        along=min(length-1.5,1.5+j*.5);cx,cy=a[0]+ux*along,a[1]+uy*along
        baseends=[(cx-ux*1.1,cy-uy*1.1),(cx+ux*1.1,cy+uy*1.1)]
        for da,db in [(0,0)]+[(d,d) for d in [-.5,.5,-.75,.75,-1.,1.,-1.25,1.25]]+[(d,-d) for d in [-.5,.5,-.75,.75,-1.,1.]]:
            ends=[(xy[0]-uy*d,xy[1]+ux*d) for xy,d in zip(baseends,[da,db])]
            reason=None
            if any(LineString([a,b]).length>1e-8 and LineString([a,b]).distance(top)-p['width']*.0254/2<.158 for a,b in zip(baseends,ends)):reason='top power spur copper'
            for xy in ends:
                pt=Point(xy)
                if pt.distance(foreign)-.3048<.158:reason='via foreign copper';break
                if pt.distance(padshapes)-.1524<.25:reason='via drill pad';break
                if pt.distance(quiet)-.3048<.158:reason='via quiet projection';break
                if pt.distance(mount)-.3048<.15:reason='mount';break
                if any(math.dist(xy,(v['x']*.0254,v['y']*.0254))-(12+v['hole'])*.0254/2<.35 for v in s['vias']):reason='via drill drill';break
            bridge=LineString(ends)
            if reason is None and bridge.distance(inner)-p['width']*.0254/2<.158:reason='inner bridge copper'
            if reason is None and bridge.distance(quiet)-p['width']*.0254/2<.158:reason='inner bridge quiet'
            normaldistance=p['width']*.0254/2+.2367+.02
            sides=[Point(cx-uy*normaldistance,cy+ux*normaldistance),Point(cx+uy*normaldistance,cy-ux*normaldistance)]
            regions=[where(pt) for pt in sides]
            if reason is None and (None in regions or regions[0]==regions[1]):reason='not two distinct source regions'
            if reason:
                reason_counts[reason]=reason_counts.get(reason,0)+1;continue
            newlines=[segment(net,1,a,baseends[0],p['width']),segment(net,16,*ends,p['width']),segment(net,1,baseends[1],b,p['width'])]+[segment(net,1,u,v,p['width']) for u,v in zip(baseends,ends) if math.dist(u,v)>1e-8]
            vias=[dict(net=net,x=x/.0254,y=y/.0254,diameter=24,hole=12) for x,y in ends]
            gap=LineString([(q.x,q.y) for q in sides])
            newtop=unary_union([LineString([(q['x1']*.0254,q['y1']*.0254),(q['x2']*.0254,q['y2']*.0254)]).buffer(q['width']*.0254/2,quad_segs=32) for q in newlines if q['layer']==1]+[Point(xy).buffer(.3048,quad_segs=32) for xy in ends])
            if gap.distance(newtop)<.0762+.158:reason_counts['gap blocked by new power copper']=reason_counts.get('gap blocked by new power copper',0)+1;continue
            valid.append(dict(remove_line_id=lineid,net=net,normal_offsets_mm=[da,db],center_mm=[cx,cy],opened_source_top_regions=regions,
                              old_length_mm=length,new_centerline_length_mm=sum(math.dist((q['x1'],q['y1']),(q['x2'],q['y2']))*.0254 for q in newlines),width_mm=p['width']*.0254,
                              lines=newlines,vias=vias,inner_bridge_foreign_gap_mm=bridge.distance(inner)-p['width']*.0254/2))
    failure[lineid]=reason_counts
    print('LINE',lineid,net,'valid',sum(r['remove_line_id']==lineid for r in valid),'failed',reason_counts,flush=True)
# Choose a compact subset for full connectivity checks; all alternatives remain.
representatives={}
for r in valid:representatives.setdefault((r['remove_line_id'],tuple(r['opened_source_top_regions'])),r)
checked=[]
for r in representatives.values():
    net=r['net'];pads=[p for p in s['pads'] if p['net']==net]
    lines=[p for p in s['lines'] if p['net']==net and p['id']!=r['remove_line_id']]+r['lines']
    vias=[p for p in s['vias'] if p['net']==net]+r['vias']
    proof=connected(pads,lines,vias)
    r={**r,'modified_net_continuity':proof};checked.append(r)
    print('CONTINUITY',r['remove_line_id'],proof,flush=True)
result=dict(source_pcb_sha256=cp['pcb_sha256'],native_imported=False,manufacturing_release=False,
            alternatives=valid,representatives=checked,failed_candidate_reasons=failure,
            limitations=['Individual bridge checks do not prove joint bridges fit each other.','A gap must be rechecked against new via annuli and all other top copper.','Full native DRC/pours/ground-reference and supply voltage-drop/transient audit required.','24/12mil via choice preserves existing ordinary through-via dimensions; no power-current rating is claimed.'])
(OUT/'local-bridge-candidates.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
assert hashlib.sha256(pcb.read_bytes()).hexdigest()==cp['pcb_sha256']
print('BRIDGE CANDIDATES',len(valid),'CHECKED REPRESENTATIVES',len(checked),flush=True)
