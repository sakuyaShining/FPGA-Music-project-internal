"""Read-only continuous topology audit of the retained R7 copper and R9 trial."""
from pathlib import Path
import sys, json, hashlib, math
ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent
sys.path.insert(0, 'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
sys.path.insert(0, str(ROOT))
from shapely.geometry import Point, LineString, box
from shapely.ops import unary_union
from six_layer_geometry import copper, connected
from physical_geometry import actual_pad
from resume_offline import read_native
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
cp = json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text(encoding='utf-8'))
pcb = Path(cp['project'])/'pcb/PCB1.epcb2'
assert sha(pcb) == cp['pcb_sha256']
s = json.loads((ROOT/cp['source_capture']).read_text(encoding='utf-8'))
raw = read_native(pcb)
s['lines'] = [dict(id=i,net=p['netName'],layer=17 if p['layerId']==16 else p['layerId'],
                  x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width'])
              for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
s['vias'] = [dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],
                 diameter=p['viaDiameter'],hole=p['holeDiameter'])
             for (k,i),p in raw.items() if k=='VIA']
fan = json.loads((ROOT/'control-closure-20261021-r8/diagnostic-harm-v4/fanouts-HARM_CS_N.json').read_text(encoding='utf-8'))
plan = json.loads((ROOT/'six-layer-comparison-20261021-r9/shielded-inner-trial/plan.json').read_text(encoding='utf-8'))
mount=unary_union([box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]])
def polygons(q):
    if q.geom_type=='Polygon': yield q
    elif hasattr(q,'geoms'):
        for p in q.geoms: yield from polygons(p)
def line_shape(p):
    return LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32)
def entries(data):
    result=[]
    for p in data['lines']:
        if p['layer']==17 and p['net']!='HARM_CS_N': result.append((p.get('id','trial'),p['net'],'line',line_shape(p)))
    for p in data['pads']:
        if p['layer']==12 and p['net']!='HARM_CS_N': result.append((p['id'],p['net'],'pad',actual_pad(p)))
    for p in data['vias']:
        if p['net']!='HARM_CS_N': result.append((p.get('id','trial'),p['net'],'via',Point(p['x']*.0254,p['y']*.0254).buffer(p['diameter']*.0254/2,quad_segs=32)))
    return result
results=[]
figures=[]
for title,extra in [('source-only',[]),('with-unaccepted-PRESET3',plan['routes'][:1])]:
    data={**s,'lines':list(s['lines']),'vias':list(s['vias'])}
    for route in extra:
        data['lines']+=route['lines']; data['vias']+=route['vias']
    objects=entries(data)
    obstacle=unary_union([q for _,_,_,q in objects])
    variants=[]
    for margin in [.0762+.158,.0762+.158+.05*math.sqrt(2)]:
        free=box(.5,.5,139.5,99.5).difference(unary_union([obstacle,mount]).buffer(margin,quad_segs=32))
        parts=sorted(polygons(free),key=lambda q:q.area,reverse=True)
        rows=[]
        for xy in fan['anchors']:
            q=Point(xy)
            neighbors=sorted(objects,key=lambda o:q.distance(o[3]))[:6]
            rows.append(dict(xy_mm=xy,free_components=[i for i,p in enumerate(parts) if p.covers(q)],
                             foreign_copper_gap_mm=q.distance(obstacle),mount_gap_mm=q.distance(mount),
                             nearest=[dict(id=i,net=n,type=k,gap_mm=q.distance(g)) for i,n,k,g in neighbors]))
        variants.append(dict(centerline_clearance_mm=margin,component_count=len(parts),
                             component_areas_mm2=[p.area for p in parts[:12]],anchors=rows))
        if margin < .25: figures.append((title,objects,parts,rows))
    results.append(dict(case=title,variants=variants))
    print(title,[(v['centerline_clearance_mm'],[a['free_components'] for a in v['anchors']]) for v in variants],flush=True)
# Explicit controls: overlapping copper on different layers cannot join without a barrel.
pads=[dict(s['pads'][0],id='test1',net='TEST',layer=1,x=1000,y=1000,shape=['RECT',30,30],rotation=0),
      dict(s['pads'][0],id='test2',net='TEST',layer=17,x=1000,y=1000,shape=['RECT',30,30],rotation=0)]
negative=connected(pads,[],[])
positive=connected(pads,[],[dict(net='TEST',x=1000,y=1000,diameter=24,hole=12)])
assert not negative['complete'] and positive['complete']
assert sha(pcb)==cp['pcb_sha256']
report=dict(source_pcb_sha256=cp['pcb_sha256'],native_imported=False,manufacturing_release=False,
            actual_six_layer_stack_created=False,helper_cross_layer_controls=dict(negative=negative,positive=positive),cases=results)
(OUT/'topology.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig,axes=plt.subplots(1,2,figsize=(15,8),layout='constrained')
for ax,(title,objects,parts,rows) in zip(axes,figures):
    for p in parts:
        x,y=p.exterior.xy; ax.fill(x,y,color='#e7f2ff',alpha=.7)
        for r in p.interiors:
            x,y=r.xy; ax.fill(x,y,color='white')
    for _,_,_,q in objects:
        for p in polygons(q):
            x,y=p.exterior.xy;ax.fill(x,y,color='#a16c3e',alpha=.7)
    for i,r in enumerate(rows):
        x,y=r['xy_mm'];ax.scatter([x],[y],color='red',s=25);ax.text(x+.5,y+.5,f'{i}: region {r["free_components"]}',fontsize=8)
    ax.set(xlim=(48,91),ylim=(34,70),title=title,xlabel='x mm',ylabel='y mm');ax.set_aspect('equal');ax.grid(alpha=.2)
fig.suptitle('HARM_CS_N continuous free space / 0.1524mm track + 0.158mm clearance\nR7 source unchanged; proposed inner17 mapping is diagnostic only')
fig.savefig(OUT/'harm-topology.png',dpi=160)
print('SAVED topology.json / harm-topology.png',flush=True)
