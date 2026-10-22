"""Offline coupled rip-up trial; never edits the native PCB or calls EDA.

Free connected core/audio trunks together with blank pending control nets.
Reject geometric and quality regressions, then recheck retained failed routes.
"""
import argparse,copy,gc,hashlib,json,math,sys,time,traceback
from datetime import datetime,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run-dir',required=True)
parser.add_argument('--fanout-max',type=float,default=.65)
parser.add_argument('--pending-first',action='store_true')
parser.add_argument('--defer-failed-restore',action='store_true')
args=parser.parse_args()
OUT=(BASE/args.run_dir).resolve()
assert OUT.parent==BASE,'Use a new single-level run directory'
OUT.mkdir(exist_ok=False)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
sys.path.insert(0,str(ROOT))
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import grid_route as grid
import reserve_escape as escape
from physical_geometry import actual_pad,connected_subset
from resume_offline import read_native

sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
PCB=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Dualscreen-Review-20261019/pcb/PCB1.epcb2')
from current_state import current_checkpoint
CHECK,checkpoint,SRC=current_checkpoint(ROOT)
source=read(SRC);checkpoint=read(CHECK);board_sha=sha(PCB)
assert board_sha==checkpoint['pcb_sha256']
native=read_native(PCB)
by_id={p['id']:p for p in source['lines']}
extra=[]
for (kind,i),p in native.items():
    if kind=='LINE' and p.get('layerId') in [1,2]:
        if i in by_id:
            q=by_id[i]
            for a,b in [('net','netName'),('layer','layerId'),('x1','startX'),('x2','endX'),('y1','startY'),('y2','endY'),('width','width')]:
                assert q[a]==p[b] if isinstance(q[a],str) else abs(q[a]-p[b])<.00011,(i,a)
        else:
            assert math.hypot(p['endX']-p['startX'],p['endY']-p['startY'])*.0254<=.003
            extra.append(dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']))
native_vias={i:p for (kind,i),p in native.items() if kind=='VIA'}
assert len(native_vias)==len(source['vias'])
normalized_via_dimensions=[]
for p in source['vias']:
    n=native_vias[p['id']]
    for a,b in [('net','netName'),('x','centerX'),('y','centerY'),('diameter','viaDiameter'),('hole','holeDiameter')]:
        if isinstance(p[a],str):assert p[a]==n[b]
        elif abs(p[a]-n[b])>=.00011:
            # Four large power vias were displayed at 0.1mil precision.
            # Validate that rounding, then plan with exact saved dimensions.
            assert a in ['diameter','hole'] and abs(p[a]-n[b])<=.05001,(p['id'],a,p[a],n[b])
            normalized_via_dimensions.append(dict(id=p['id'],field=a,capture=p[a],native=n[b]))
            p[a]=n[b]
source['lines']+=extra
pending=checkpoint['pending_nets']
u15=list(dict.fromkeys(p['net'] for p in source['pads'] if p['ref']=='U15' and p['net'] not in ['GND','3V3_IO','3V3_PERIPH']))
rip=[n for n in u15+['SCAN_LATCH'] if n not in pending]
rip.sort(key=lambda n:sum(p['net']==n for p in source['vias']))
order=rip+[n for n in u15+['SCAN_LATCH'] if n in pending]
assert len(order)==len(set(order))==16
reserve_nets=order+[n for n in pending if n not in order]
working={**source,'pads':copy.deepcopy(source['pads']),
         'lines':[p for p in source['lines'] if p['net'] not in order],
         'vias':[p for p in source['vias'] if p['net'] not in order]}
grid.pad_shape=escape.pad_shape=actual_pad
grid.WIDTH=escape.WIDTH=.1524;grid.GAP=escape.GAP=.165
grid.GRID=escape.GRID=.05;grid.VIA_COST_MM=12;grid.SEARCH_MARGINS=[8,22,50]
original_raster=grid.raster
grid.raster=escape.raster=lambda gs,b,i,s:original_raster(gs,b,i+grid.GRID/math.sqrt(2),s)
routes=[];failures=[];phase='initial';batch_ok=False;collisions=[]
started=time.monotonic()

def log(*a):
    line=' '.join(str(x) for x in a);print(line,flush=True)
    with (OUT/'planner.log').open('a',encoding='utf-8') as f:f.write(line+'\n')

def save():
    obj=dict(utc=datetime.now(timezone.utc).isoformat(),phase=phase,source_file=str(SRC),source_sha256=sha(SRC),
        native_pcb_sha256=board_sha,native_microtracks_included=len(extra),normalized_via_dimensions=normalized_via_dimensions,pending_nets=pending,ripped_connected_nets=rip,
        proposed_nets=[r['net'] for r in routes],routes=routes,failed_planning=failures,
        retained_route_collision_checks=collisions,batch_final_geometry_pass=batch_ok,
        native_imported=False,manufacturing_release=False,options=vars(args),executed_script_sha256=sha(Path(__file__)),
        requires_native_drc_and_ground_return_review=True,
        elapsed_seconds=time.monotonic()-started,
        planner_sha256={n:sha(ROOT/n) for n in ['grid_route.py','reserve_escape.py','physical_geometry.py']})
    (OUT/'joint-plan.json').write_text(json.dumps(obj,indent=2),encoding='utf-8')

def length(lines):return sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in lines)

def lower_bound(net):
    pads=[p for p in source['pads'] if p['net']==net];seen={0};total=0.
    while len(seen)<len(pads):
        d,j=min((math.hypot(pads[i]['x']-pads[j]['x'],pads[i]['y']-pads[j]['y'])*.0254,j)
            for i in seen for j in range(len(pads)) if j not in seen)
        total+=d;seen.add(j)
    return total

def validate(data,net,lines,vias):
    foreign,_,keepouts=grid.geometries(data,net)
    cu={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2]);ko=unary_union(keepouts)
    minimum=float('inf')
    for p in lines:
        q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
        gap=q.distance(cu[p['layer']])-p['width']*.0254/2;minimum=min(minimum,gap)
        assert gap>=.158 and q.distance(ko)>=p['width']*.0254/2+.15,('track_gap',gap)
    for i,p in enumerate(vias):
        q=Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-p['diameter']*.0254/2;minimum=min(minimum,gap)
        assert gap>=.158 and q.distance(ko)>=p['diameter']*.0254/2+.15,('via_gap',gap)
        for old in [p for p in data['vias'] if p['net']!=net]+vias[:i]:
            gap=math.hypot(p['x']-old['x'],p['y']-old['y'])*.0254-(p['hole']+old['hole'])*.0254/2
            assert gap>=.3499,('drill_gap',gap)
    return minimum

phase='reserve_coupled_escapes';save()
log('SOURCE',board_sha,'native microtracks',len(extra),'JOINT NETS',order)
# Reuse previously checked physical fanouts from the exact same source.
cache=read(BASE/'u15-all/reserved-fanouts.json')
assert cache['source_sha256']==sha(SRC) and cache['native_pcb_sha256']==board_sha
fans=cache['fanouts']
for n in rip:escape.reserve(source,working,n)
for n,f in fans.items():
    added_lines=[p for p in f['lines'] if 'id' not in p]
    added_vias=[p for p in f['vias'] if 'id' not in p]
    working['lines']+=added_lines;working['vias']+=added_vias
    key=lambda x,y:(round(x,5),round(y,5))
    adj={}
    for p in added_lines:
        a=key(p['x1'],p['y1']);b=key(p['x2'],p['y2'])
        adj.setdefault(a,[]).append(b);adj.setdefault(b,[]).append(a)
    targets={key(v['x'],v['y']):v for v in added_vias}
    for pad in list(working['pads']):
        if pad['net']!=n or pad.get('routing_pad_exclude'):continue
        start=key(pad['x'],pad['y'])
        if start not in adj:continue
        stack=[start];seen=set();found=None
        while stack:
            node=stack.pop()
            if node in seen:continue
            seen.add(node)
            if node in targets:found=targets[node];break
            stack+=adj.get(node,[])
        assert found is not None,(n,pad['ref'],pad['n'])
        working['pads']=[{**p,'routing_pad_exclude':True} if p['id']==pad['id'] else p for p in working['pads']]
        working['pads'].append({**pad,'id':'anchor-'+pad['id'],'ref':'FANOUT-'+pad['ref'],
            'x':found['x'],'y':found['y'],'rotation':0,'layer':12,'shape':['ELLIPSE',found['diameter'],found['diameter'],0]})
(OUT/'working-before-trunks.json').write_text(json.dumps(working),encoding='utf-8')
log('FANOUTS',{n:(len(f['lines']),len(f['vias'])) for n,f in fans.items()})
(OUT/'reserved-fanouts.json').write_text(json.dumps(dict(fanouts=fans,source_sha256=sha(SRC),native_pcb_sha256=board_sha),indent=2),encoding='utf-8')
for net in order:
    phase='planning:'+net;save();begin=time.monotonic();log('START',net)
    try:
        trial=grid.plan(working,net)
        lines=fans[net]['lines']+trial['lines'];vias=fans[net]['vias']+trial['vias']
        connected=connected_subset([p for p in source['pads'] if p['net']==net],lines,vias)
        assert connected['complete'],('real_pad_continuity',connected)
        # Discard unattached objects but retain every real pad.
        lines=connected['lines'];vias=connected['vias']
        minimum=validate(working,net,lines,vias)
        oldlines=[p for p in source['lines'] if p['net']==net];oldvias=[p for p in source['vias'] if p['net']==net]
        mst=lower_bound(net);metrics=dict(before_length_mm=length(oldlines),after_length_mm=length(lines),
            before_vias=len(oldvias),after_vias=len(vias),mst_lower_bound_mm=mst,min_foreign_gap_mm=minimum)
        log('METRICS',net,metrics)
        if net in rip:
            assert len(vias)<=max(4,len(oldvias)+1) and length(lines)<=max(length(oldlines)*1.20,mst*1.35),'Connected-net quality budget exceeded'
            if net.startswith('I2S_'):assert len(vias)<=3 and length(lines)<=length(oldlines),'Audio quality budget: <=3 vias, no length increase'
        else:
            npads=len([p for p in source['pads'] if p['net']==net])
            assert len(vias)<=npads+2 and length(lines)<=mst*2.0,'Pending-net quality budget exceeded'
        trial.update(lines=lines,vias=vias,quality=metrics,real_pad_continuity_pass=True,independent_geometry_pass=True)
        routes.append(trial)
        working['lines']=[p for p in working['lines'] if p['net']!=net]+lines
        working['vias']=[p for p in working['vias'] if p['net']!=net]+vias
        log('ACCEPTED_OFFLINE',net,round(time.monotonic()-begin,1),'s')
    except Exception as e:
        failures.append(dict(net=net,error=repr(e),elapsed_seconds=time.monotonic()-begin))
        for kind in ['lines','vias']:
            working[kind]=[p for p in working[kind] if p['net']!=net]
            if not args.defer_failed_restore:working[kind]+=[p for p in source[kind] if p['net']==net]
        log('REJECTED',net,repr(e),round(time.monotonic()-begin,1),'s')
    save();gc.collect()
if args.defer_failed_restore:
    for kind in ['lines','vias']:
        working[kind]+=[p for p in source[kind] if p['net'] in {f['net'] for f in failures}]
phase='final_retained_route_check';save()
pruned=[]
while True:
    invalid=[]
    for r in routes:
        try:validate(working,r['net'],r['lines'],r['vias'])
        except Exception as e:invalid.append((r,repr(e)))
    if not invalid:break
    for r,error in invalid:
        pruned.append(dict(net=r['net'],error=error))
        for k in ['lines','vias']:working[k]=[p for p in working[k] if p['net']!=r['net']]+[p for p in source[k] if p['net']==r['net']]
        routes.remove(r)
log('PRUNED_RESTORED_NET_COLLISIONS',pruned)
(OUT/'pruned.json').write_text(json.dumps(pruned,indent=2),encoding='utf-8')
for r in routes:
    try:
        minimum=validate(working,r['net'],r['lines'],r['vias'])
        collisions.append(dict(net=r['net'],pass_geometry=True,min_gap_mm=minimum))
    except Exception as e:collisions.append(dict(net=r['net'],pass_geometry=False,error=repr(e)))
batch_ok=bool(routes) and all(c['pass_geometry'] for c in collisions)
# Joint candidate must improve total routed copper while adding pending nets.
old_rip_vias=sum(p['net'] in rip for p in source['vias'])
new_rip_vias=sum(len(r['vias']) for r in routes if r['net'] in rip)
# Every rejected net is restored, then a fixed-point pruning audit below selects only safe candidates.
if new_rip_vias>old_rip_vias:batch_ok=False
phase='complete';save()
assert sha(PCB)==board_sha
log('COMPLETE',len(routes),'offline candidate nets',len(failures),'rejected; final geometry',batch_ok,'NO NATIVE IMPORT')
