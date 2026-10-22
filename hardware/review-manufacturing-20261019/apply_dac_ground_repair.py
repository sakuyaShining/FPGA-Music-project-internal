"""Apply the jointly checked DAC mute/LRCK replacement and additive GND link."""
import hashlib,json,sys,time,zipfile
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020')
import shapely
from shapely.geometry import LineString
from shapely.ops import unary_union
import grid_route as grid
from native_review import ROOT,PROJECT,invoke

path=ROOT/'resume-dac-ground-repair-plan.json'
plan=json.loads(path.read_text(encoding='utf-8'))
assert plan['independent_geometry_pass'] and not plan['violations']
replace=set(plan['replace_nets']);assert replace=={'DAC_XSMT','I2S_LRCK'}
assert all(p['net'] in replace|{'GND'} for p in plan['lines']+plan['vias'])
assert all(p['width']>=5.9999 for p in plan['lines'])
board=PROJECT/'pcb/PCB1.epcb2'
assert hashlib.sha256(board.read_bytes()).hexdigest()==plan['native_pcb_sha256']
from pathlib import Path
sp=Path(plan['source_file']);assert hashlib.sha256(sp.read_bytes()).hexdigest()==plan['source_sha256']
source=json.loads(sp.read_text(encoding='utf-8'))
canonical=lambda d:{k:sorted(d[k],key=lambda p:p['id']) for k in ['pads','lines','vias']}
assert canonical(grid.capture())==canonical(source),'Native geometry changed since joint plan'
backup=ROOT/'offline-resume-20261020'/('before-dac-ground-repair-'+str(time.time_ns())+'-CANDIDATE.zip')
with zipfile.ZipFile(backup,'x',zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(PROJECT.rglob('*')):
        if p.is_file() and 'review-exports' not in p.relative_to(PROJECT).parts:
            archive.write(p,p.relative_to(PROJECT))
data={'replace_nets':sorted(replace),'lines':plan['lines'],'vias':plan['vias']}
result=invoke('resume-apply-dac-ground-'+str(time.time_ns()),'const data='+json.dumps(data)+';'+"""
const ns=new Set(data.replace_nets);const identities=async()=>({components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:(await eda.pcb_Drc.getCurrentRuleConfiguration()).config});
const before=await identities();if(before.components.length!==230)throw new Error('Wrong project');const oldLines=(await eda.pcb_PrimitiveLine.getAll()).filter(p=>ns.has(p.getState_Net()));const oldVias=(await eda.pcb_PrimitiveVia.getAll()).filter(p=>ns.has(p.getState_Net()));
const old={lines:oldLines.map(p=>({net:p.getState_Net(),layer:p.getState_Layer(),x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),width:p.getState_LineWidth()})),vias:oldVias.map(p=>({net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),hole:p.getState_HoleDiameter(),diameter:p.getState_Diameter()}))};
const newLines=[],newVias=[];const create=async(d,record)=>{for(const v of d.vias){const p=await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false);if(!p)throw new Error('Create via');if(record)newVias.push(p.getState_PrimitiveId());}for(const l of d.lines){const p=await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false);if(!p)throw new Error('Create line');if(record)newLines.push(p.getState_PrimitiveId());}};
try{if(oldLines.length&&!await eda.pcb_PrimitiveLine.delete(oldLines.map(p=>p.getState_PrimitiveId())))throw new Error('Clear selected tracks');if(oldVias.length&&!await eda.pcb_PrimitiveVia.delete(oldVias.map(p=>p.getState_PrimitiveId())))throw new Error('Clear selected vias');await create(data,true);if(JSON.stringify(before)!==JSON.stringify(await identities()))throw new Error('Identity or rules changed');if(!await eda.pcb_Document.save())throw new Error('Save repair');}catch(e){const rollbackLines=(await eda.pcb_PrimitiveLine.getAll()).filter(p=>ns.has(p.getState_Net())||newLines.includes(p.getState_PrimitiveId())).map(p=>p.getState_PrimitiveId());const rollbackVias=(await eda.pcb_PrimitiveVia.getAll()).filter(p=>ns.has(p.getState_Net())||newVias.includes(p.getState_PrimitiveId())).map(p=>p.getState_PrimitiveId());if(rollbackLines.length)await eda.pcb_PrimitiveLine.delete(rollbackLines);if(rollbackVias.length)await eda.pcb_PrimitiveVia.delete(rollbackVias);await create(old,false);await eda.pcb_Document.save();throw e;}
return {created_tracks:data.lines.length,created_vias:data.vias.length,component_identity_placement_and_rules_unchanged:true,saved:true};
""",timeout=180)
after=grid.capture();(ROOT/'resume-dac-ground-repaired-source.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
other={kind:sorted([p for p in source[kind] if p['net'] not in replace|{'GND'}],key=lambda p:p['id'])==sorted([p for p in after[kind] if p['net'] not in replace|{'GND'}],key=lambda p:p['id']) for kind in ['lines','vias']}
preserved={}
for layer in [1,2]:
    paths=[]
    for s in [source,after]:paths.append(unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]) for p in s['lines'] if p['net']=='GND' and p['layer']==layer]))
    preserved[str(layer)]=paths[0].difference(paths[1].buffer(.000005)).is_empty
result.update({'backup':str(backup),'plan_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
               'all_pads_unchanged':canonical(source)['pads']==canonical(after)['pads'],
               'unselected_copper_unchanged':other,'existing_ground_lines_preserved':preserved,
               'requires_native_drc_and_ground_rebuild':True,'manufacturing_release':False})
(ROOT/'resume-native-dac-ground-repair-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2),flush=True)
assert all(other.values()) and all(preserved.values()) and result['all_pads_unchanged']
