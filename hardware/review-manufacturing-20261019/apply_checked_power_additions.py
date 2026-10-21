"""Independently audit and apply additive 5V copper; retain original supply necks."""
import hashlib,json,math,sys,time,zipfile
from pathlib import Path
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString,Point
from shapely.ops import unary_union
import grid_route as grid
from physical_geometry import actual_pad,connected_subset
from native_review import ROOT,PROJECT,invoke
from resume_offline import read_native

path=ROOT/'periph-power-after-rcdrive-plan.json';plan=json.loads(path.read_text(encoding='utf-8'))
assert plan['net']=='5V_PERIPH' and plan['additive'] and plan['lines']
sp=Path(plan['source_file']);source=json.loads(sp.read_text(encoding='utf-8'))
assert hashlib.sha256(sp.read_bytes()).hexdigest()==plan['source_sha256']
board=PROJECT/'pcb/PCB1.epcb2';assert hashlib.sha256(board.read_bytes()).hexdigest()==plan['native_pcb_sha256']
canonical=lambda d:{k:sorted(d[k],key=lambda p:p['id']) for k in ['pads','lines','vias']}
assert canonical(grid.capture())==canonical(source),'Native geometry changed since power planning'
ids={p['id'] for p in source['lines']};extra=[]
for (kind,identity),p in read_native(board).items():
    if kind=='LINE' and p.get('layerId') in [1,2] and identity not in ids:
        extra.append({'id':identity,'net':p['netName'],'layer':p['layerId'],'x1':p['startX'],'y1':p['startY'],'x2':p['endX'],'y2':p['endY'],'width':p['width']})
grid.pad_shape=actual_pad
working={**source,'lines':source['lines']+extra}
foreign,pads,keepouts=grid.geometries(working,'5V_PERIPH')
copper={l:unary_union(foreign[l]) for l in [1,2]};both=unary_union(foreign[1]+foreign[2]);ko=unary_union(keepouts);allpads=unary_union(pads)
gaps=[]
for route in plan['routes']:
    for p in route['lines']:
        width=p['width']*.0254
        if route.get('kind')=='ic_supply_escape':
            assert route['pad'][0] in ['U17','U18','U13'] and width>=.4999
            assert math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254<=2.5
        else:assert width>=.9999,'Main power trunk narrowed'
        q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)])
        gap=q.distance(copper[p['layer']])-width/2;gaps.append(gap)
        assert gap>=.158 and q.distance(ko)>=width/2+.15
for i,p in enumerate(plan['vias']):
    assert p['diameter']*.0254>=1.1999 and p['hole']*.0254>=.5999
    q=Point(p['x']*.0254,p['y']*.0254)
    gap=q.distance(both)-p['diameter']*.0254/2;gaps.append(gap)
    assert gap>=.158 and q.distance(ko)>=p['diameter']*.0254/2+.15
    assert q.distance(allpads)>=p['hole']*.0254/2+.25
    for previous in source['vias']+plan['vias'][:i]:
        assert math.hypot(p['x']-previous['x'],p['y']-previous['y'])*.0254-(p['hole']+previous['hole'])*.0254/2>=.3499
power_pads=[p for p in source['pads'] if p['net']=='5V_PERIPH']
old_lines=[p for p in source['lines'] if p['net']=='5V_PERIPH'];old_vias=[p for p in source['vias'] if p['net']=='5V_PERIPH']
old=connected_subset(power_pads,old_lines,old_vias);new=connected_subset(power_pads,old_lines+plan['lines'],old_vias+plan['vias'])
old_islands=1 if old['complete'] else old['pad_islands'];new_islands=1 if new['complete'] else new['pad_islands']
assert new_islands<old_islands,'No independent reduction in disconnected power pad groups'
audit={'plan_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'independent_geometry_pass':True,
       'minimum_copper_gap_mm':min(gaps),'pad_islands_before':old_islands,'pad_islands_after':new_islands,
       'all_power_pads_connected':new_islands==1,'native_drc_required':True,'manufacturing_release':False}
(ROOT/'periph-power-geometry-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
backup=ROOT/'offline-resume-20261020'/('before-periph-power-'+str(time.time_ns())+'-CANDIDATE.zip')
with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(PROJECT.rglob('*')):
        if p.is_file() and 'review-exports' not in p.relative_to(PROJECT).parts:archive.write(p,p.relative_to(PROJECT))
data={'lines':plan['lines'],'vias':plan['vias']}
result=invoke('apply-periph-power-'+str(time.time_ns()),'const data='+json.dumps(data)+';'+"""
const state=async()=>({components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:(await eda.pcb_Drc.getCurrentRuleConfiguration()).config});const before=await state();if(before.components.length!==230)throw new Error('Wrong project');const ls=[],vs=[];
try{for(const v of data.vias){const p=await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false);if(!p)throw new Error('Create power via');vs.push(p.getState_PrimitiveId());}for(const l of data.lines){const p=await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false);if(!p)throw new Error('Create power track');ls.push(p.getState_PrimitiveId());}if(JSON.stringify(before)!==JSON.stringify(await state()))throw new Error('Placement or rules changed');if(!await eda.pcb_Document.save())throw new Error('Save power additions');}catch(e){if(ls.length)await eda.pcb_PrimitiveLine.delete(ls);if(vs.length)await eda.pcb_PrimitiveVia.delete(vs);await eda.pcb_Document.save();throw e;}return {new_tracks:ls.length,new_vias:vs.length,component_identity_placement_and_rules_unchanged:true,saved:true};
""",timeout=150)
after=grid.capture();(ROOT/'periph-power-applied-source.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
untouched={kind:sorted([p for p in source[kind] if p['net']!='5V_PERIPH'],key=lambda p:p['id'])==sorted([p for p in after[kind] if p['net']!='5V_PERIPH'],key=lambda p:p['id']) for kind in ['lines','vias']}
preserved={}
for layer in [1,2]:
    shapes=[unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]) for p in ds['lines'] if p['net']=='5V_PERIPH' and p['layer']==layer]) for ds in [source,after]]
    preserved[str(layer)]=shapes[0].difference(shapes[1].buffer(.000005)).is_empty
result.update({'backup':str(backup),'geometry_audit':audit,'all_pads_unchanged':canonical(source)['pads']==canonical(after)['pads'],
               'unselected_copper_unchanged':untouched,'existing_power_tracks_preserved':preserved,
               'requires_ground_rebuild_and_native_drc':True,'manufacturing_release':False})
(ROOT/'periph-power-native-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
assert result['all_pads_unchanged'] and all(untouched.values()) and all(preserved.values())
