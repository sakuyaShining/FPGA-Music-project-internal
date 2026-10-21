from pathlib import Path
import sys,json,math,hashlib,copy,zipfile
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(ROOT/'inv2-comparison-20261021-r16'))
from exchange import read
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
from shapely.affinity import rotate,translate
from physical_geometry import actual_pad
cp,PCB,s=read()
docs={};current=None
for text in PCB.read_text(encoding='utf-8').splitlines():
    if '||' not in text:continue
    h,b=text.split('||',1);h=json.loads(h);v=json.loads(b.rstrip('|')) if b.rstrip('|').strip() else None
    if h['type']=='DOCHEAD':current=v['uuid'];docs.setdefault(current,{})
    if current:docs[current][h['type'],h.get('id')]=v
from resume_offline import read_native
raw=read_native(PCB)
def points(path):
    if path and path[0]=='CIRCLE':
        _,x,y,r=path;return [(x-r,y-r),(x+r,y+r)]
    if not path or not isinstance(path[0],(int,float)):return []
    x,y=path[:2];out=[(x,y)];i=2;mode=None
    while i<len(path):
        if isinstance(path[i],str):mode=path[i];i+=1
        if mode=='L':x,y=path[i:i+2];i+=2;out.append((x,y))
        elif mode=='ARC':
            angle,tx,ty=path[i:i+3];i+=3;t=math.radians(angle);dx,dy=tx-x,ty-y
            if abs(t)>1e-8:
                ax=(x+tx)/2-dy/(2*math.tan(t/2));ay=(y+ty)/2+dx/(2*math.tan(t/2));radius=math.hypot(x-ax,y-ay);out.extend([(ax-radius,ay-radius),(ax+radius,ay+radius)])
            x,y=tx,ty;out.append((x,y))
        else:break
    return out
attrs={}
for (k,i),v in raw.items():
    if k=='ATTR':attrs.setdefault(v['parentId'],{})[v['key']]=v['value']
boxes={};local_r=None;locals_by_ref={}
for cid,a in attrs.items():
    if 'Designator' not in a or 'Footprint' not in a or ('COMPONENT',cid) not in raw:continue
    geoms=[]
    for (k,i),p in docs[a['Footprint']].items():
        if not p:continue
        if k=='POLY':
            pts=points(p.get('path',[]));sw=p.get('width',0)/2
            if pts:geoms.append(box(min(x for x,y in pts)-sw,min(y for x,y in pts)-sw,max(x for x,y in pts)+sw,max(y for x,y in pts)+sw))
        if k=='PAD':
            q=p['defaultPad'];x,y=p['centerX'],p['centerY'];geoms.append(rotate(box(x-q['width']/2,y-q['height']/2,x+q['width']/2,y+q['height']/2),p.get('padAngle',0),origin=(x,y)))
    if not geoms:continue
    geometry=unary_union(geoms);locals_by_ref[a['Designator']]=geometry;c=raw['COMPONENT',cid]
    q=translate(rotate(geometry,c['angle'],origin=(0,0)),c['x'],c['y']);boxes[a['Designator']]=box(*[v*.0254 for v in q.bounds])
    if a['Designator']=='R30':local_r=geometry
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert all(sha(Path(cp['project'])/p)==h for p,h in cp['files'].items())
snapshot=OUT/'source-before-regional-layout.zip'
if not snapshot.exists():
    with zipfile.ZipFile(snapshot,'x',zipfile.ZIP_DEFLATED) as z:
        for rel in cp['files']:z.write(Path(cp['project'])/rel,rel)
with zipfile.ZipFile(snapshot) as z:
    assert z.testzip() is None and all(hashlib.sha256(z.read(rel)).hexdigest()==h for rel,h in cp['files'].items())
cid_by_ref={a['Designator']:cid for cid,a in attrs.items() if 'Designator' in a and ('COMPONENT',cid) in raw}
for p in s['pads']:
    if p['ref'] not in cid_by_ref:boxes[p['ref']]=box(*actual_pad(p).bounds)
motions={'U15':(84,43,270),'C35':(89.6,46.2,90),'R30':(78,39.8,0),'R31':(78,43.4,0),'TP13':(74.5,46.2,0),'TP14':(75,40.4,0),'R63':(73,44.2,0),'R64':(70.5,38,0)}
selected={p['net'] for p in s['pads'] if p['ref']=='U15' and p['net'] not in ['GND','3V3_IO','3V3_PERIPH','']}
assert len(set(cp['pending_nets'])&selected)==4
def make_variant(label,dx,dy):
    targets={ref:(x+(dx if ref in ['U15','C35'] else 0),y+(dy if ref in ['U15','C35'] else 0),angle) for ref,(x,y,angle) in motions.items()}
    pads=list(s['pads']);newboxes={};changes=[]
    for ref,(x,y,angle) in targets.items():
        if ref not in cid_by_ref:
            oldps=[p for p in s['pads'] if p['ref']==ref];assert len(oldps)==1
            p=oldps[0];moved=[{**p,'x':x/.0254,'y':y/.0254,'rotation':angle}]
            newboxes[ref]=box(*actual_pad(moved[0]).bounds)
            pads=[p for p in pads if p['ref']!=ref]+moved
            changes.append(dict(type='free_pad',ref=ref,id=p['id'],pad_midpoint_mm=[x,y],rotation=angle,prior_origin_mil=[p['x'],p['y']],prior_rotation=p['rotation'],expected_pads=moved))
            continue
        cid=cid_by_ref[ref];c=raw['COMPONENT',cid];oldps=[p for p in s['pads'] if p['ref']==ref]
        mx=sum(p['x'] for p in oldps)/len(oldps)*.0254;my=sum(p['y'] for p in oldps)/len(oldps)*.0254
        rad=math.radians(angle-c['angle']);cs,sn=math.cos(rad),math.sin(rad)
        ox,oy=c['x']*.0254-mx,c['y']*.0254-my
        origin=(x+ox*cs-oy*sn,y+ox*sn+oy*cs)
        geometry=translate(rotate(locals_by_ref[ref],angle,origin=(0,0)),origin[0]/.0254,origin[1]/.0254)
        newboxes[ref]=box(*[v*.0254 for v in geometry.bounds])
        moved=[]
        for p in oldps:
            u,v=p['x']*.0254-mx,p['y']*.0254-my
            moved.append({**p,'x':(x+u*cs-v*sn)/.0254,'y':(y+u*sn+v*cs)/.0254,'rotation':p['rotation']+angle-c['angle']})
        pads=[p for p in pads if p['ref']!=ref]+moved
        changes.append(dict(type='component',ref=ref,id=cid,pad_midpoint_mm=[x,y],rotation=angle,prior_origin_mil=[c['x'],c['y']],prior_rotation=c['angle'],expected_pads=moved))
    gaps=[]
    for ref,q in newboxes.items():
        for other,r in {**boxes,**newboxes}.items():
            if ref==other:continue
            if q.distance(r)<.55:gaps.append(dict(a=ref,b=other,bbox_gap_mm=q.distance(r)))
    total=0;metrics=[]
    for net in ['BUS_SCK','BUS_MOSI','DISP_SCK','DISP_MOSI','HARM_CS_N','VIS_CS_N']:
        pts=[(p['x']*.0254,p['y']*.0254) for p in pads if p['net']==net];used={0};length=0
        while len(used)<len(pts):
            d,a,b=min((math.dist(pts[a],pts[b]),a,b) for a in used for b in range(len(pts)) if b not in used)
            used.add(b);length+=d
        metrics.append(dict(net=net,unrouted_euclidean_mst_lower_bound_mm=length));total+=length
    return dict(label=label,changes=changes,bbox_conflicts=gaps,airwire_lower_bound_mm=total,airwire_by_net=metrics,new_component_boxes_mm={r:list(q.bounds) for r,q in newboxes.items()},manufacturing_release=False)
variants=[make_variant('rotated-U15-center84',0,0),make_variant('rotated-U15-center83',-1,.3),make_variant('rotated-U15-center85',1,-.3)]
valid=[v for v in variants if not v['bbox_conflicts']]
report=dict(utc=datetime.now(timezone.utc).isoformat(),source_pcb_sha256=cp['pcb_sha256'],source_checkpoint=cp['checkpoint'],source_files=cp['files'],snapshot=str(snapshot),snapshot_sha256=sha(snapshot),pending_nets=cp['pending_nets'],cluster_pending_nets=[n for n in cp['pending_nets'] if any(p['ref'] in ['U8','U9','U15'] and p['net']==n for p in s['pads'])],first_batch_signal_nets=sorted(selected),variants=variants,classification='intermediate/design_draft',constraints=dict(hard=['Preserve component MPN/value/pin-net mapping, dual screens,84 channels,Tang Nano20K-only architecture and music functions','Preserve current outline,4-layer structure,connector and mounting positions,existing native rule configuration','Do not reduce existing local power widths or change supply domains'],preferences=['Shorter realizable routes and fewer vias; MST is only a placement screening lower bound','0.55mm component bbox screening margin, verified later against native physical rules'],unverified_assumptions=['0.5mm sensor/0.6mm audio projection guard margins inherited as initial comparison assumptions','Final mechanical Nano/screen/panel fit and factory stackup not qualified','Actual edge rates and SI timing budgets unknown']),manufacturing_release=False)
(OUT/'layout-comparison.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
assert valid,'No layout variant passes footprint bounding-box screening'
best=min(valid,key=lambda v:v['airwire_lower_bound_mm'])
(OUT/'selected-layout.json').write_text(json.dumps(dict(source_pcb_sha256=cp['pcb_sha256'],source_files=cp['files'],selected_variant=best,signal_nets=sorted(selected),routing_window_mm=[73.5,36.5,95,52],manufacturing_release=False),indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(valid=[v['label'] for v in valid],selected=best['label'],variants=[dict(label=v['label'],conflicts=v['bbox_conflicts'],airwire_lower_bound_mm=v['airwire_lower_bound_mm']) for v in variants]),indent=2),flush=True)
