"""Inspect/bridge 5V_PERIPH islands while preserving existing power copper.

New trunks use 1 mm copper and 1.2/0.6 mm through vias. Explicit short IC
escapes use 0.8 mm at the power switch and 0.5 mm at the LDO supply pads.
This is geometric routing, not validation of actual screen current or voltage.
"""
import argparse,hashlib,json,math,sys,time
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import grid_route as grid
from physical_geometry import actual_pad
from native_review import ROOT,PROJECT
from resume_offline import read_native

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',required=True)
parser.add_argument('--output',default='periph-power-plan.json')
parser.add_argument('--inspect-only',action='store_true')
parser.add_argument('--with-ic-fanouts',action='store_true')
parser.add_argument('--all-angle-ic-escapes',action='store_true',help='Also check short in-body/sideways escapes; keep all copper/hole clearances and neck widths unchanged')
parser.add_argument('--exclude-native-net',nargs='*',default=[],help='Explicit offline coupled rip-up dependency; final proposal must also replace these nets')
parser.add_argument('--exclude-native-line-id',nargs='*',default=[],help='Explicit local offline line replacement dependency; keep all other copper/vias')
parser.add_argument('--snap-ic-escape-grid',action='store_true',help='Check escape ends at actual search grid nodes to avoid a clear point snapping into a blocked cell')
options=parser.parse_args()
source_path=ROOT/options.source;source=json.loads(source_path.read_text(encoding='utf-8'))
board=PROJECT/'pcb/PCB1.epcb2';pcb_sha=hashlib.sha256(board.read_bytes()).hexdigest()
net='5V_PERIPH';objects=[]
for p in source['pads']:
    if p['net']==net:objects.append({'mask':3 if p['layer']==12 else 1<<(p['layer']-1),'shape':actual_pad(p),'kind':'pad','p':p})
for p in source['lines']:
    if p['net']==net:objects.append({'mask':1<<(p['layer']-1),'shape':LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=16),'kind':'line','p':p})
for p in source['vias']:
    if p['net']==net:objects.append({'mask':3,'shape':Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2,resolution=24),'kind':'via','p':p})
parents=list(range(len(objects)))
def root(i):
    while parents[i]!=i:parents[i]=parents[parents[i]];i=parents[i]
    return i
for i,a in enumerate(objects):
    for j,b in enumerate(objects[:i]):
        if a['mask']&b['mask'] and root(i)!=root(j) and a['shape'].distance(b['shape'])<.000005:parents[root(i)]=root(j)
groups={}
for i,obj in enumerate(objects):groups.setdefault(root(i),[]).append(obj)
groups=[g for g in groups.values() if any(o['kind']=='pad' for o in g)]
anchors=[];inventory=[]
for index,group in enumerate(groups):
    points=[]
    for obj in group:
        p=obj['p']
        if obj['kind']=='pad' and min(p['shape'][1:3])*.0254>=.95:points.append(p)
        if obj['kind']=='line' and p['width']*.0254>=.95:
            length=math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254
            steps=max(1,math.ceil(length/2))
            for step in range(steps+1):
                t=step/steps
                points.append({'id':'line-anchor-'+p['id']+'-'+str(step),'ref':'POWER_TRACK','n':str(step),'net':net,'layer':p['layer'],
                               'x':p['x1']+(p['x2']-p['x1'])*t,'y':p['y1']+(p['y2']-p['y1'])*t,'rotation':0,'shape':['ELLIPSE',p['width'],p['width']]})
    anchors.append(points)
    inventory.append({'group':index,'pads':[(o['p']['ref'],o['p']['n']) for o in group if o['kind']=='pad'],
                      'wide_trunk_anchor_candidates':len(points)})
(ROOT/'periph-power-islands.json').write_text(json.dumps({'groups':inventory,'source_file':str(source_path)},indent=2),encoding='utf-8')
print('POWER ISLANDS',json.dumps(inventory),flush=True)
if options.inspect_only:sys.exit(0)
ids={p['id'] for p in source['lines']};extra=[]
for (kind,identity),p in read_native(board).items():
    if kind=='LINE' and p.get('layerId') in [1,2] and identity not in ids and p['netName'] not in options.exclude_native_net and identity not in options.exclude_native_line_id:
        extra.append({'id':identity,'net':p['netName'],'layer':p['layerId'],'x1':p['startX'],'y1':p['startY'],'x2':p['endX'],'y2':p['endY'],'width':p['width']})
working={**source,'lines':source['lines']+extra,'vias':list(source['vias'])}
grid.pad_shape=actual_pad;grid.WIDTH=1.;grid.VIA_D=1.2;grid.VIA_H=.6;grid.GAP=.17;grid.GRID=.1
original_raster=grid.raster
grid.raster=lambda geoms,bounds,inflate,shape:original_raster(geoms,bounds,inflate+grid.GRID/math.sqrt(2),shape)
routes=[];failed=[]
if options.with_ic_fanouts:
    for index,group in enumerate(groups):
        if anchors[index]:continue
        pads=[o['p'] for o in group if o['kind']=='pad']
        pad=next((p for p in pads if p['n']=='1'),pads[0])
        neck=.8 if pad['ref']=='U17' else .5
        siblings=[p for p in source['pads'] if p['ref']==pad['ref']]
        cx=sum(p['x'] for p in siblings)/len(siblings);cy=sum(p['y'] for p in siblings)/len(siblings)
        angle=math.radians(pad['rotation'])
        axis=(math.cos(angle),math.sin(angle)) if pad['shape'][1]>=pad['shape'][2] else (-math.sin(angle),math.cos(angle))
        sign=1 if axis[0]*(pad['x']-cx)+axis[1]*(pad['y']-cy)>=0 else -1
        out=(axis[0]*sign,axis[1]*sign)
        foreign,allpads,keepouts=grid.geometries(working,net)
        copper={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2]);pad_union=unary_union(allpads);ko=unary_union(keepouts)
        start=(pad['x']*.0254,pad['y']*.0254);chosen=None
        for distance in [1.3,1.5,1.7,2.,2.3]:
            ends=[(start[0]+out[0]*distance-out[1]*lateral,start[1]+out[1]*distance+out[0]*lateral) for lateral in [0,.2,-.2,.4,-.4,.6,-.6]]
            if options.all_angle_ic_escapes:
                ends += [(start[0]+math.cos(math.radians(a))*distance,start[1]+math.sin(math.radians(a))*distance) for a in range(0,360,15)]
            for turn in [-30,30,-60,60,-90,90]:
                a=math.radians(turn);dx=out[0]*math.cos(a)-out[1]*math.sin(a);dy=out[0]*math.sin(a)+out[1]*math.cos(a)
                ends.append((start[0]+dx*distance,start[1]+dy*distance))
            for end in ends:
                if options.snap_ic_escape_grid:end=(round(end[0]/grid.GRID)*grid.GRID,round(end[1]/grid.GRID)*grid.GRID)
                q=Point(end);line=LineString([start,end])
                if line.distance(copper[pad['layer']])<neck/2+.17 or line.distance(ko)<neck/2+.15:continue
                if q.distance(copper[pad['layer']])>=.5+.17+grid.GRID/math.sqrt(2) and q.distance(ko)>=.5+.15:
                    chosen=(end,False);break
                if q.distance(both)<.6+.17 or q.distance(pad_union)<.3+.25 or q.distance(ko)<.6+.15:continue
                if any(q.distance(Point(v['x']*.0254,v['y']*.0254))-(.6+v['hole']*.0254)/2<.35 for v in working['vias']):continue
                chosen=(end,True);break
            if chosen:break
        if chosen is None:
            failed.append({'group':index,'pad':[pad['ref'],pad['n']],'reason':'No checked short supply-pin escape'})
            continue
        point,add_via=chosen
        line={'net':net,'layer':pad['layer'],'x1':pad['x'],'y1':pad['y'],'x2':point[0]/.0254,'y2':point[1]/.0254,'width':neck/.0254}
        via={'net':net,'x':point[0]/.0254,'y':point[1]/.0254,'diameter':1.2/.0254,'hole':.6/.0254}
        working['lines'].append(line)
        if add_via:working['vias'].append(via)
        routes.append({'kind':'ic_supply_escape','group':index,'pad':[pad['ref'],pad['n']],'neck_width_mm':neck,'lines':[line],'vias':[via] if add_via else []})
        anchors[index].append({'id':'power-fanout-'+pad['id'],'ref':'POWER_FANOUT','n':pad['n'],'net':net,'layer':12 if add_via else pad['layer'],'x':via['x'],'y':via['y'],'rotation':0,'shape':['ELLIPSE',1./.0254,1./.0254]})
        print('POWER IC ESCAPE',pad['ref'],pad['n'],neck,'mm; endpoint',point,'via',add_via,flush=True)
connected={max(range(len(groups)),key=lambda i:len(anchors[i]))}
while len(connected)<len(groups):
    options_list=sorted(((math.hypot(a['x']-b['x'],a['y']-b['y']),i,j,a,b) for i in connected for j in range(len(groups)) if j not in connected for a in anchors[i] for b in anchors[j]),key=lambda p:p[0])
    found=None;attempted=set()
    for distance,i,j,a,b in options_list:
        # Limit equivalent starts along the same narrow corridor before trying
        # another island. The original copper remains untouched on failure.
        key=(i,j,round(a['x']*.0254),round(a['y']*.0254),round(b['x']*.0254),round(b['y']*.0254))
        if key in attempted:continue
        attempted.add(key)
        if len(attempted)>18:break
        for margin in [5,15,35]:
            try:r=grid.search(working,net,a,b,margin)
            except grid.SealedEscape:break
            if r:found=(i,j,r);break
        if found:break
    if not found:
        failed.append({'connected_groups':sorted(connected),'remaining_groups':sorted(set(range(len(groups)))-connected),'reason':'No 1mm trunk with existing pad/track constraints'});break
    i,j,r=found;connected.add(j);r.update({'from_group':i,'to_group':j})
    routes.append(r);working['lines']+=r['lines'];working['vias']+=r['vias']
    print('POWER BRIDGE',i,j,len(r['lines']),len(r['vias']),flush=True)
routes=[r for r in routes if r.get('kind')!='ic_supply_escape' or r['group'] in connected]
plan={'net':net,'additive':True,'source_file':str(source_path),'source_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),
      'excluded_native_nets_require_joint_replacement':options.exclude_native_net,
      'excluded_native_line_ids_require_joint_replacement':options.exclude_native_line_id,
      'ic_escape_endpoints_grid_aligned':options.snap_ic_escape_grid,
      'native_pcb_sha256':pcb_sha,'routes':routes,'failed_planning':failed,'all_pad_groups_connected':len(connected)==len(groups),
      'lines':[p for r in routes for p in r['lines']],'vias':[p for r in routes for p in r['vias']],
      'new_trunk_width_mm':1.,'new_via_diameter_mm':1.2,'new_via_hole_mm':.6,
      'requires_independent_geometry_audit':True,'requires_native_drc':True,'manufacturing_release':False}
(ROOT/options.output).write_text(json.dumps(plan,indent=2),encoding='utf-8')
assert hashlib.sha256(board.read_bytes()).hexdigest()==pcb_sha
print('POWER PLAN',sum(r.get('kind')!='ic_supply_escape' for r in routes),'bridges;',sum(r.get('kind')=='ic_supply_escape' for r in routes),'IC escapes; connected',len(connected),'/',len(groups),flush=True)
