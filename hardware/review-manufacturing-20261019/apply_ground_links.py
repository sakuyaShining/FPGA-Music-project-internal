"""Apply only checked additive ground copper, with no rip-up or placement edits."""
import hashlib
import argparse
import json
from pathlib import Path
import sys
import time
import zipfile

sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString
from shapely.ops import unary_union
import grid_route as grid
from native_review import ROOT,PROJECT,invoke

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--plan',default='resume-ground-additive-plan.json')
parser.add_argument('--audit',default='resume-native-ground-audit.json')
options=parser.parse_args()
plan_path=ROOT/options.plan
plan=json.loads(plan_path.read_text(encoding='utf-8'))
assert plan['additive'] and plan['net']=='GND' and plan['routes']
assert all(r['independent_geometry_pass'] for r in plan['routes'])
assert all(p['net']=='GND' and p['width']>=7.9999 for p in plan['lines'])
assert all(p['net']=='GND' for p in plan['vias'])
board=PROJECT/'pcb/PCB1.epcb2'
assert hashlib.sha256(board.read_bytes()).hexdigest()==plan['native_pcb_sha256']
source_path=Path(plan['source_file'])
assert hashlib.sha256(source_path.read_bytes()).hexdigest()==plan['source_sha256']
source=json.loads(source_path.read_text(encoding='utf-8'))
canonical=lambda d:{k:sorted(d[k],key=lambda p:p['id']) for k in ['pads','lines','vias']}
assert canonical(grid.capture())==canonical(source),'Live copper changed during ground planning'
backup=ROOT/'offline-resume-20261020'/('before-native-ground-'+str(time.time_ns())+'-CANDIDATE.zip')
with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(PROJECT.rglob('*')):
        if p.is_file() and 'review-exports' not in p.relative_to(PROJECT).parts:
            archive.write(p,p.relative_to(PROJECT))
data={'lines':plan['lines'],'vias':plan['vias']}
result=invoke('resume-apply-ground-links-'+str(time.time_ns()),'const data='+json.dumps(data)+';'+"""
const identities=async()=>({components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:(await eda.pcb_Drc.getCurrentRuleConfiguration()).config});
const before=await identities();if(before.components.length!==230)throw new Error('Wrong project');
const createdLines=[],createdVias=[];try{for(const v of data.vias){const p=await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false);if(!p)throw new Error('Create GND via');createdVias.push(p.getState_PrimitiveId());}for(const l of data.lines){const p=await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false);if(!p)throw new Error('Create GND link');createdLines.push(p.getState_PrimitiveId());}if(JSON.stringify(before)!==JSON.stringify(await identities()))throw new Error('Identity or rules changed');if(!await eda.pcb_Document.save())throw new Error('Save additive GND links');}catch(e){if(createdLines.length)await eda.pcb_PrimitiveLine.delete(createdLines);if(createdVias.length)await eda.pcb_PrimitiveVia.delete(createdVias);await eda.pcb_Document.save();throw e;}
return {createdLines,createdVias,component_identity_placement_and_rules_unchanged:true,saved:true};
""",timeout=180)
after=grid.capture()
(ROOT/'resume-ground-applied-source.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
same_other={kind:sorted([p for p in source[kind] if p['net']!='GND'],key=lambda p:p['id'])==sorted([p for p in after[kind] if p['net']!='GND'],key=lambda p:p['id']) for kind in ['lines','vias']}
old_ground={layer:unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]) for p in source['lines'] if p['net']=='GND' and p['layer']==layer]) for layer in [1,2]}
new_ground={layer:unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]) for p in after['lines'] if p['net']=='GND' and p['layer']==layer]) for layer in [1,2]}
preserved={str(layer):old_ground[layer].difference(new_ground[layer].buffer(.000005)).is_empty for layer in [1,2]}
result.update({'plan_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),'backup':str(backup),
               'all_pads_unchanged':canonical(source)['pads']==canonical(after)['pads'],
               'non_ground_copper_unchanged':same_other,'old_ground_line_geometry_preserved':preserved,
               'planned_links':len(plan['routes']),'pending_planning':plan['failed_planning'],
               'requires_ground_rebuild_and_native_drc':True,'manufacturing_release':False})
(ROOT/options.audit).write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ['createdLines','createdVias']},indent=2),flush=True)
assert all(same_other.values()) and all(preserved.values()) and result['all_pads_unchanged']
