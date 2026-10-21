"""Co-plan the adjacent DAC mute and ground escapes; native PCB is unchanged."""
import copy,hashlib,json,math,sys
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import grid_route as grid
import reserve_escape as escape
from physical_geometry import actual_pad,connected_subset
from native_review import ROOT,PROJECT
from resume_offline import read_native

sp=ROOT/'resume-ground-final-source.json';source=json.loads(sp.read_text())
board=PROJECT/'pcb/PCB1.epcb2';board_sha=hashlib.sha256(board.read_bytes()).hexdigest()
ids={p['id'] for p in source['lines']};extra=[]
for (kind,identity),p in read_native(board).items():
    if kind=='LINE' and p.get('layerId') in [1,2] and identity not in ids:
        extra.append({'id':identity,'net':p['netName'],'layer':p['layerId'],'x1':p['startX'],'y1':p['startY'],'x2':p['endX'],'y2':p['endY'],'width':p['width']})
replace_nets=['DAC_XSMT','I2S_LRCK']
working={**source,'pads':[{**p,'routing_pad_exclude':True} if p['net']=='GND' and (p['ref']!='U12' or p['n']!='24') else dict(p) for p in source['pads']],
         'lines':[p for p in source['lines']+extra if p['net'] not in replace_nets],
         'vias':[p for p in source['vias'] if p['net'] not in replace_nets]}
grid.pad_shape=escape.pad_shape=actual_pad
grid.WIDTH=escape.WIDTH=.1524;grid.GAP=escape.GAP=.17;grid.GRID=escape.GRID=.025
original=grid.raster
def raster(geoms,bounds,inflate,shape):return original(geoms,bounds,inflate+grid.GRID/math.sqrt(2),shape)
grid.raster=escape.raster=raster
base=copy.deepcopy(working)
fans=escape.grid_mux_fanouts(working,['DAC_XSMT','I2S_LRCK','GND'],refs={'U12'})
print('SHARED ESCAPES',fans['new_fanouts'],flush=True)
if len(fans['new_fanouts'])!=3:
    # Staggered escapes derived from the measured pad/via layout. Coordinates
    # are only proposals; all three nets undergo the same continuous checks.
    working=base;fans={'lines':[],'vias':[],'new_fanouts':[]}
    for net,pin,point in [('DAC_XSMT','25',(96.9,53.5)),('I2S_LRCK','23',(97.85,52.9)),('GND','24',(96.7,51.8))]:
        pad=next(p for p in source['pads'] if p['ref']=='U12' and p['n']==pin)
        points=[(pad['x']*.0254,pad['y']*.0254)]+([(97.5,53.5),(97.25,52.9)] if net=='GND' else [])+[point]
        lines=[{'net':net,'layer':1,'x1':a[0]/.0254,'y1':a[1]/.0254,'x2':b[0]/.0254,'y2':b[1]/.0254,'width':6} for a,b in zip(points,points[1:])]
        via={'net':net,'x':point[0]/.0254,'y':point[1]/.0254,'diameter':24,'hole':12,'routing_retained':True}
        fans['lines']+=lines;fans['vias'].append(via);fans['new_fanouts'].append((net,'U12',pin))
        working['lines']+=lines;working['vias'].append(via)
        working['pads']=[{**p,'routing_pad_exclude':True} if p['id']==pad['id'] else p for p in working['pads']]
        working['pads'].append({**pad,'id':'anchor-'+pad['id'],'ref':'FANOUT-U12','x':via['x'],'y':via['y'],'rotation':0,'layer':12,'shape':['ELLIPSE',24,24,0]})
    # Choose the GND hole from BOTH copper layers, rather than only the visible
    # top-side clearance. A final straight leg can move within the package body.
    foreign,pads,keepouts=grid.geometries(working,'GND')
    both=unary_union(foreign[1]+foreign[2]);top=unary_union(foreign[1]);allpads=unary_union(pads)
    via=next(v for v in fans['vias'] if v['net']=='GND')
    last=next(l for l in reversed(fans['lines']) if l['net']=='GND')
    origin=(last['x1']*.0254,last['y1']*.0254)
    candidate=None
    for distance,dx,dy in sorted((math.hypot(dx,dy),dx,dy) for dx in range(-30,31) for dy in range(-30,31)):
        q=Point(96.7+dx*.1,51.8+dy*.1)
        if q.distance(both)<.3048+.17 or q.distance(allpads)<.1524+.25:continue
        if LineString([origin,(q.x,q.y)]).distance(top)<.0762+.17:continue
        if any(q.distance(Point(v['x']*.0254,v['y']*.0254))-(12+v['hole'])*.0254/2<.35 for v in working['vias'] if v is not via):continue
        candidate=q;break
    assert candidate is not None,'No fully checked staggered GND via'
    via['x'],via['y']=candidate.x/.0254,candidate.y/.0254
    last['x2'],last['y2']=via['x'],via['y']
    for p in working['pads']:
        if p['id'].startswith('anchor-') and p['net']=='GND':p['x'],p['y']=via['x'],via['y']
    print('STAGGERED ESCAPES',fans['new_fanouts'],'GND via',candidate.x,candidate.y,flush=True)
start=next(p for p in working['pads'] if p['id'].startswith('anchor-') and p['net']=='GND')
end=next(p for p in source['pads'] if p['ref']=='U12' and p['n']=='27')
ground=None
for margin in [3,6,12]:
    ground=grid.search(working,'GND',start,end,margin)
    if ground:break
assert ground,'Ground escape did not reach existing ground copper'
working['lines']+=ground['lines'];working['vias']+=ground['vias']
replacements={}
for net in replace_nets:
    grid.GRID=.075 if net=='I2S_LRCK' else .025
    r=grid.plan(working,net);replacements[net]=r
    working['lines']+=r['lines'];working['vias']+=r['vias']
g_lines=[p for p in fans['lines'] if p['net']=='GND']+ground['lines']
g_vias=[p for p in fans['vias'] if p['net']=='GND']+ground['vias']
m_lines=[p for p in fans['lines'] if p['net'] in replace_nets]+[p for r in replacements.values() for p in r['lines']]
m_vias=[p for p in fans['vias'] if p['net'] in replace_nets]+[p for r in replacements.values() for p in r['vias']]
assert connected_subset([next(p for p in source['pads'] if p['ref']=='U12' and p['n']=='24'),end],g_lines,g_vias)['complete']
for net in replace_nets:
    assert connected_subset([p for p in source['pads'] if p['net']==net],[p for p in m_lines if p['net']==net],[p for p in m_vias if p['net']==net])['complete']
violations=[];minimum={}
for net in ['GND']+replace_nets:
    lines=g_lines if net=='GND' else [p for p in m_lines if p['net']==net]
    vias=g_vias if net=='GND' else [p for p in m_vias if p['net']==net]
    foreign,pads,keepouts=grid.geometries(working,net)
    copper={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2]);ko=unary_union(keepouts)
    gaps=[]
    for p in lines:
        q=LineString([(p['x1']*grid.MM,p['y1']*grid.MM),(p['x2']*grid.MM,p['y2']*grid.MM)])
        gap=q.distance(copper[p['layer']])-p['width']*grid.MM/2;gaps.append(gap)
        if gap<.158 or q.distance(ko)<p['width']*grid.MM/2+.15:violations.append((net,'line',gap,p))
    for p in vias:
        q=Point(p['x']*grid.MM,p['y']*grid.MM);gap=q.distance(both)-p['diameter']*grid.MM/2;gaps.append(gap)
        if gap<.158 or q.distance(ko)<p['diameter']*grid.MM/2+.15:violations.append((net,'via',gap,p))
    minimum[net]=min(gaps)
old_vias=[v for v in source['vias'] if v['net'] not in replace_nets];all_new=g_vias+m_vias
for i,a in enumerate(all_new):
    for b in old_vias+all_new[:i]:
        gap=math.hypot(a['x']-b['x'],a['y']-b['y'])*grid.MM-(a['hole']+b['hole'])*grid.MM/2
        if gap<.3499:violations.append(('drill',gap))
if violations:
    (ROOT/'resume-dac-ground-repair-rejected.json').write_text(json.dumps({'violations':violations,'native_imported':False},indent=2),encoding='utf-8')
assert not violations,str(violations)
plan={'replace_nets':replace_nets,'additive_net':'GND','lines':m_lines+g_lines,'vias':m_vias+g_vias,
      'source_file':str(sp),'source_sha256':hashlib.sha256(sp.read_bytes()).hexdigest(),
      'native_pcb_sha256':board_sha,'independent_geometry_pass':True,'minimum_copper_gaps_mm':minimum,
      'violations':violations,'native_imported':False,'requires_native_drc':True,'manufacturing_release':False}
(ROOT/'resume-dac-ground-repair-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
assert hashlib.sha256(board.read_bytes()).hexdigest()==board_sha
print('DAC GROUND REPAIR',len(plan['lines']),len(plan['vias']),minimum,flush=True)
