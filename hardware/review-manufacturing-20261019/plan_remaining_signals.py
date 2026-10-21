"""Plan pending control/display nets against the saved 102-open PCB.

All fine-pitch escapes are considered before trunks so one completed bus does
not consume another pin's only exit. Only complete, independently checked nets
enter the native application plan; failed nets remain untouched.
"""
import argparse,copy,gc,hashlib,json,math,sys,time
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import grid_route as grid
import reserve_escape as escape
from physical_geometry import actual_pad,connected_subset
from native_review import ROOT,PROJECT
from resume_offline import read_native

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',default='controls-source-102.json')
parser.add_argument('--checkpoint',default='route-checkpoint-0clear-102open.json')
parser.add_argument('--output',default='controls-plan-102.json')
parser.add_argument('--resume',action='store_true')
parser.add_argument('--allow-testpoint-vias',action='store_true')
parser.add_argument('--only',nargs='+')
parser.add_argument('--fanout-max',type=float,default=.6)
parser.add_argument('--via-cost-mm',type=float)
parser.add_argument('--max-vias',type=int)
parser.add_argument('--max-length-factor',type=float)
options=parser.parse_args()
source_path=ROOT/options.source;raw=source_path.read_bytes();source=json.loads(raw)
checkpoint=json.loads((ROOT/options.checkpoint).read_text(encoding='utf-8'))
board=PROJECT/'pcb/PCB1.epcb2';board_sha=hashlib.sha256(board.read_bytes()).hexdigest()
assert board_sha==checkpoint['pcb_sha256'],'Recapture current source before planning'
nets=[n for n in checkpoint['pending_nets'] if n!='5V_PERIPH']
assert all(not any(p['net']==n for p in source['lines']+source['vias']) for n in nets),'This planner starts from blank pending nets'
ids={p['id'] for p in source['lines']};extra=[]
for (kind,identity),p in read_native(board).items():
    if kind=='LINE' and p.get('layerId') in [1,2] and identity not in ids:
        extra.append({'id':identity,'net':p['netName'],'layer':p['layerId'],
                      'x1':p['startX'],'y1':p['startY'],'x2':p['endX'],'y2':p['endY'],'width':p['width']})
working={**source,'pads':copy.deepcopy(source['pads']),'lines':source['lines']+extra,'vias':list(source['vias'])}
grid.pad_shape=escape.pad_shape=actual_pad
grid.WIDTH=escape.WIDTH=.1524;grid.GAP=escape.GAP=.17;grid.GRID=escape.GRID=.05
grid.VIA_COST_MM=options.via_cost_mm
original_raster=grid.raster
def raster(geoms,bounds,inflate,shape):return original_raster(geoms,bounds,inflate+grid.GRID/math.sqrt(2),shape)
grid.raster=escape.raster=raster
if options.allow_testpoint_vias:
    original_geometries=grid.geometries
    def testpoint_geometries(data,net):
        foreign,pads,keepouts=original_geometries(data,net)
        # Only bare independent test pads qualify. Component solder pads retain
        # their original hole exclusion; foreign-net copper is never relaxed.
        pads=[actual_pad(p) for p in data['pads'] if not p['id'].startswith('anchor-')
              and not(p['net']==net and p['ref']==p['n'] and p['ref'].startswith('TP') and p['layer']==1)]
        return foreign,pads,keepouts
    grid.geometries=escape.geometries=testpoint_geometries
def extent(net):
    ps=[p for p in source['pads'] if p['net']==net]
    return (max(p['x'] for p in ps)-min(p['x'] for p in ps)+max(p['y'] for p in ps)-min(p['y'] for p in ps))*.0254
order=sorted(nets,key=lambda n:(extent(n),n));refs={p['ref'] for p in source['pads'] if p['ref'].startswith('U')}
output=ROOT/options.output
fanout_name=output.stem+'-fanouts.json'
if options.resume:
    saved=json.loads(output.read_text(encoding='utf-8'))
    assert saved['source_sha256']==hashlib.sha256(raw).hexdigest()
    output.with_name(output.stem+'-before-retry-'+str(time.time_ns())+'.json').write_bytes(output.read_bytes())
    fanout_name=saved['reserved_unapplied_fanouts_file']
    frozen=json.loads((ROOT/fanout_name).read_text(encoding='utf-8'))
    working=frozen['working'];fans=frozen['fanouts'];routes=saved['routes']
    for r in routes:
        working['lines']+=[p for p in r['lines'] if p not in fans['lines']]
        working['vias']+=[p for p in r['vias'] if p not in fans['vias']]
    completed={r['net'] for r in routes};order=[n for n in order if n not in completed]
    failed=[p for p in saved['failed_planning'] if options.only and p['net'] not in options.only]
else:
    print('SIGNAL ORDER',order,flush=True)
    fanouts=escape.grid_mux_fanouts(working,order,refs=refs,max_pad_short_mm=options.fanout_max)
    print('GRID FANOUTS',len(fanouts['new_fanouts']),fanouts['new_fanouts'],flush=True)
    direct=escape.new_mux_fanouts(working,order,refs=refs,max_pad_short_mm=options.fanout_max)
    print('DIRECT FANOUTS',len(direct['new_fanouts']),direct['new_fanouts'],flush=True)
    fans={'lines':fanouts['lines']+direct['lines'],'vias':fanouts['vias']+direct['vias']}
    pending=[(p['ref'],p['n'],p['net']) for p in working['pads'] if p['net'] in nets and p['ref'] in refs and min(p['shape'][1:3])*.0254<=options.fanout_max and not p.get('routing_pad_exclude')]
    (ROOT/fanout_name).write_text(json.dumps({'working':working,'fanouts':fans,'unescaped_fine_pads':pending,'source_sha256':hashlib.sha256(raw).hexdigest()},indent=2),encoding='utf-8')
    print('UNESCAPED',pending,flush=True)
    routes=[];failed=[]
if options.only:order=[n for n in order if n in options.only]
print('REMAINING ORDER',order,flush=True)
def save():
    plan={'nets':[r['net'] for r in routes],'routes':routes,
          'lines':[p for r in routes for p in r['lines']],'vias':[p for r in routes for p in r['vias']],
          'source_file':str(source_path),'source_sha256':hashlib.sha256(raw).hexdigest(),
          'native_pcb_sha256':board_sha,'native_short_line_obstacles':len(extra),
          'failed_planning':failed,'reserved_unapplied_fanouts_file':fanout_name,
          'bare_testpoint_vias_permitted':options.allow_testpoint_vias,
          'native_imported':False,'requires_ground_rebuild_and_native_drc':True,'manufacturing_release':False}
    output.write_text(json.dumps(plan,indent=2),encoding='utf-8')
save()
for net in order:
    started=time.monotonic()
    try:
        grid.GRID=.075
        route=grid.plan(working,net)
        lines=[p for p in fans['lines'] if p['net']==net]+route['lines']
        vias=[p for p in fans['vias'] if p['net']==net]+route['vias']
        connection=connected_subset([p for p in source['pads'] if p['net']==net],lines,vias)
        if not connection['complete']:raise RuntimeError('Real-pad continuity failed '+str(connection))
        ps=[p for p in source['pads'] if p['net']==net];chosen={0};mst=0.
        while len(chosen)<len(ps):
            distance,j=min((math.hypot(ps[i]['x']-ps[j]['x'],ps[i]['y']-ps[j]['y'])*.0254,j) for i in chosen for j in range(len(ps)) if j not in chosen)
            mst+=distance;chosen.add(j)
        route_length=sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in lines)
        if options.max_vias is not None and len(vias)>options.max_vias:raise RuntimeError('Quality budget: too many vias '+str(len(vias)))
        if options.max_length_factor is not None and route_length>mst*options.max_length_factor:raise RuntimeError('Quality budget: detour exceeds chosen MST factor '+str(route_length/mst))
        foreign,pads,keepouts=grid.geometries(working,net)
        copper={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2]);ko=unary_union(keepouts)
        gaps=[]
        for p in lines:
            q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
            gap=q.distance(copper[p['layer']])-p['width']*.0254/2;gaps.append(gap)
            if gap<.158 or q.distance(ko)<p['width']*.0254/2+.15:raise RuntimeError('Independent track clearance failed '+str(gap))
        for i,p in enumerate(vias):
            q=Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-p['diameter']*.0254/2;gaps.append(gap)
            if gap<.158 or q.distance(ko)<p['diameter']*.0254/2+.15:raise RuntimeError('Independent via clearance failed '+str(gap))
            for old in [v for v in working['vias'] if v['net']!=net]+vias[:i]:
                if math.hypot(p['x']-old['x'],p['y']-old['y'])*.0254-(p['hole']+old['hole'])*.0254/2<.3499:raise RuntimeError('Independent drill spacing failed')
        route.update({'lines':lines,'vias':vias,'edges':[{'min_foreign_copper_gap_mm':min(gaps)}],
                      'independent_geometry_pass':True,'real_pad_continuity_pass':True,
                      'quality_budget':{'length_mm':route_length,'pad_mst_lower_bound_mm':mst,'vias':len(vias),'max_vias':options.max_vias,'max_length_factor':options.max_length_factor}})
        routes.append(route)
        working['lines']+=[p for p in lines if p not in fans['lines']]
        working['vias']+=[p for p in vias if p not in fans['vias']]
        print('PLANNED',net,len(lines),len(vias),'min gap',min(gaps),round(time.monotonic()-started,1),'seconds',flush=True)
    except Exception as error:
        failed.append({'net':net,'error':str(error)})
        print('PENDING',net,type(error).__name__,str(error),round(time.monotonic()-started,1),'seconds',flush=True)
    save();gc.collect()
assert hashlib.sha256(board.read_bytes()).hexdigest()==board_sha,'Native PCB changed during offline work'
print('SIGNAL PLAN COMPLETE',len(routes),'complete nets;',len(failed),'pending',flush=True)
