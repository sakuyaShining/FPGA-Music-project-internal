"""Replace complete signal nets only when measured routing quality improves."""
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
parser.add_argument('--source',default='controls-final-source-78.json')
parser.add_argument('--checkpoint',default='route-checkpoint-0clear-78open.json')
parser.add_argument('--output',default='quality-i2s-plan.json')
parser.add_argument('--nets',nargs='+',default=['I2S_LRCK','I2S_DIN','I2S_BCK'])
parser.add_argument('--via-cost-mm',type=float,default=20)
parser.add_argument('--grid',type=float,default=.1)
parser.add_argument('--margins',nargs='+',type=float,default=[10,22,50])
parser.add_argument('--relax-ground',action='store_true',help='Allow removal of explicitly colliding old GND tracks/vias; all pads remain protected')
options=parser.parse_args()
src=ROOT/options.source;raw=src.read_bytes();source=json.loads(raw)
board=PROJECT/'pcb/PCB1.epcb2';board_sha=hashlib.sha256(board.read_bytes()).hexdigest()
assert board_sha==json.loads((ROOT/options.checkpoint).read_text())['pcb_sha256']
ids={p['id'] for p in source['lines']};extra=[]
for (kind,identity),p in read_native(board).items():
    if kind=='LINE' and p.get('layerId') in [1,2] and identity not in ids:
        assert p['netName'] not in options.nets,'Selected net has hidden native microsegments'
        extra.append(dict(id=identity,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']))
excluded=set(options.nets)|({'GND'} if options.relax_ground else set())
working={**source,'pads':copy.deepcopy(source['pads']),'lines':[p for p in source['lines']+extra if p['net'] not in excluded],
         'vias':[p for p in source['vias'] if p['net'] not in excluded]}
grid.pad_shape=escape.pad_shape=actual_pad
grid.WIDTH=escape.WIDTH=.1524;grid.GAP=escape.GAP=.17
grid.GRID=escape.GRID=options.grid;grid.VIA_COST_MM=options.via_cost_mm
grid.SEARCH_MARGINS=options.margins
original_raster=grid.raster
grid.raster=escape.raster=lambda gs,b,inflate,shape:original_raster(gs,b,inflate+grid.GRID/math.sqrt(2),shape)
fans={net:escape.reserve(source,working,net) for net in options.nets}
print('FANOUTS',{n:(len(f['lines']),len(f['vias'])) for n,f in fans.items()},flush=True)
routes=[];failed=[];batch_validated=False;ground_removals={'lines':[],'vias':[]}
def length(lines):return sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in lines)
def save():
    value={'nets':[r['net'] for r in routes],'routes':routes,'lines':[p for r in routes for p in r['lines']],'vias':[p for r in routes for p in r['vias']],
           'source_file':str(src),'source_sha256':hashlib.sha256(raw).hexdigest(),'native_pcb_sha256':board_sha,'failed_planning':failed,
           'via_cost_mm':options.via_cost_mm,'batch_final_geometry_pass':batch_validated,'ground_removals':ground_removals,
           'requires_ground_rebuild_and_native_drc':True,'manufacturing_release':False}
    (ROOT/options.output).write_text(json.dumps(value,indent=2),encoding='utf-8')
for net in options.nets:
    started=time.monotonic()
    try:
        result=grid.plan(working,net)
        lines=fans[net]['lines']+result['lines'];vias=fans[net]['vias']+result['vias']
        connection=connected_subset([p for p in source['pads'] if p['net']==net],lines,vias)
        assert connection['complete'],connection
        foreign,pads,keepouts=grid.geometries(working,net)
        copper={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2]);ko=unary_union(keepouts)
        gaps=[]
        for p in lines:
            shape=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
            gap=shape.distance(copper[p['layer']])-p['width']*.0254/2;gaps.append(gap)
            assert gap>=.158 and shape.distance(ko)>=p['width']*.0254/2+.15,('track gap',gap)
        for i,p in enumerate(vias):
            point=Point(p['x']*.0254,p['y']*.0254);gap=point.distance(both)-p['diameter']*.0254/2;gaps.append(gap)
            assert gap>=.158 and point.distance(ko)>=p['diameter']*.0254/2+.15,('via gap',gap)
            for old in [p for p in working['vias'] if p['net']!=net]+vias[:i]:
                assert math.hypot(p['x']-old['x'],p['y']-old['y'])*.0254-(p['hole']+old['hole'])*.0254/2>=.3499,'Drill spacing'
        oldlines=[p for p in source['lines'] if p['net']==net];oldvias=[p for p in source['vias'] if p['net']==net]
        metrics={'before_length_mm':length(oldlines),'after_length_mm':length(lines),'before_vias':len(oldvias),'after_vias':len(vias)}
        print('CANDIDATE',net,metrics,flush=True)
        assert len(vias)<len(oldvias) and length(lines)<=length(oldlines),'Reject trade of added length for fewer vias'
        result.update(lines=lines,vias=vias,edges=[{'min_foreign_copper_gap_mm':min(gaps)}],independent_geometry_pass=True,real_pad_continuity_pass=True,quality_comparison=metrics)
        routes.append(result)
        working['lines']+=[p for p in lines if p not in fans[net]['lines']]
        working['vias']+=[p for p in vias if p not in fans[net]['vias']]
        print('QUALITY ACCEPTED',net,len(lines),len(vias),round(time.monotonic()-started,1),'seconds',flush=True)
    except Exception as error:
        failed.append({'net':net,'error':repr(error)})
        # The original route remains an obstacle for subsequently planned nets.
        working['lines']=[p for p in working['lines'] if p['net']!=net]+[p for p in source['lines'] if p['net']==net]
        working['vias']=[p for p in working['vias'] if p['net']!=net]+[p for p in source['vias'] if p['net']==net]
        print('QUALITY REJECTED',net,repr(error),round(time.monotonic()-started,1),'seconds',flush=True)
    save();gc.collect()
if options.relax_ground:
    signals={l:[] for l in [1,2]}
    for r in routes:
        for p in r['lines']:
            signals[p['layer']].append(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2))
        for p in r['vias']:
            for l in [1,2]:signals[l].append(Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2))
    copper={l:unary_union(signals[l]) for l in [1,2]};both=unary_union(signals[1]+signals[2])
    for p in source['lines']:
        if p['net']!='GND':continue
        q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
        if q.distance(copper[p['layer']])-p['width']*.0254/2<.17:ground_removals['lines'].append(p['id'])
    for p in source['vias']:
        if p['net']!='GND':continue
        q=Point(p['x']*.0254,p['y']*.0254)
        if q.distance(both)-p['diameter']*.0254/2<.17 or any(math.hypot(p['x']-v['x'],p['y']-v['y'])*.0254-(p['hole']+v['hole'])*.0254/2<.35 for r in routes for v in r['vias']):ground_removals['vias'].append(p['id'])
    print('EXPLICIT GROUND REMOVALS',{k:len(v) for k,v in ground_removals.items()},flush=True)
final={**source,'lines':[p for p in source['lines']+extra if p['net'] not in {r['net'] for r in routes} and p['id'] not in ground_removals['lines']]+[p for r in routes for p in r['lines']],
       'vias':[p for p in source['vias'] if p['net'] not in {r['net'] for r in routes} and p['id'] not in ground_removals['vias']]+[p for r in routes for p in r['vias']]}
for r in routes:
    foreign,_,_=grid.geometries(final,r['net']);cu={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2])
    for p in r['lines']:
        q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
        assert q.distance(cu[p['layer']])-p['width']*.0254/2>=.158,'Final batch collision with retained net'
    for p in r['vias']:
        assert Point(p['x']*.0254,p['y']*.0254).distance(both)-p['diameter']*.0254/2>=.158,'Final batch via collision'
batch_validated=True;save()
assert hashlib.sha256(board.read_bytes()).hexdigest()==board_sha
print('COMPLETE',len(routes),'improved nets',flush=True)
