"""Apply the checked local power/BUS/GND exchange through normal editor APIs.

No extension identity switch or external file API is used. A recoverable native
snapshot precedes every mutation. This does not run or certify final DRC.
"""
import hashlib,json,sys,zipfile
from datetime import datetime
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');sys.path.insert(0,str(ROOT))
import shapely
import grid_route as grid
from native_review import PROJECT,invoke
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
path=OUT/'local-power-bus-with-return-plan.json';plan=read(path)
assert plan['independent_geometry_pass'] and plan['both_nets_complete']
assert len(plan['remove_line_ids'])==5 and len(plan['removed_redundant_supply_link_ids'])==3
assert plan['new_bus_via_to_ground_stitch_mm']<=1.2
PCB=PROJECT/'pcb/PCB1.epcb2';assert sha(PCB)==plan['native_pcb_sha256']
source=read(Path(plan['source_file']));assert sha(Path(plan['source_file']))==plan['source_sha256']
for rel,h in plan['dependency_sha256'].items():assert sha(OUT/rel)==h
canonical=lambda d:{k:sorted(d[k],key=lambda p:p['id']) for k in ['pads','lines','vias']}
fresh=grid.capture();assert canonical(fresh)==canonical(source),'Fresh editor view changed; do not apply stale proposal'
checkpoint=read(ROOT/'route-checkpoint-0clear-78open-quality-r1-20261021.json')
assert all(sha(PROJECT/rel)==h for rel,h in checkpoint['files'].items())
stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
snapshot=Path('D:/FPGA-Project/snapshots')/('before-local-power-bus-exchange-'+stamp)
snapshot.mkdir(exist_ok=False)
archive=snapshot/'native-quality-r1-before-local-exchange.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
    for rel in checkpoint['files']:z.write(PROJECT/rel,rel)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(hashlib.sha256(z.read(rel)).hexdigest()==h for rel,h in checkpoint['files'].items())
(snapshot/'snapshot-manifest.json').write_text(json.dumps(dict(native_files=checkpoint['files'],
    archive_sha256=sha(archive),plan_sha256=sha(path),purpose='Before local power/BUS/GND exchange; recover in a separate directory'),indent=2),encoding='utf-8')
print('SNAPSHOT',snapshot,flush=True)
payload=dict(remove_line_ids=plan['remove_line_ids'],removed_lines=plan['removed_lines'],
    lines=plan['additive_power_lines']+plan['bus_lines']+plan['ground_lines'],
    vias=plan['additive_power_vias']+plan['bus_vias']+plan['ground_vias'])
assert len(payload['vias'])==4 and all(p['width']>=5.9999 for p in payload['lines'])
code='const data='+json.dumps(payload,ensure_ascii=True)+';'+"""
if((await eda.dmt_SelectControl.getCurrentDocumentInfo())?.uuid!=='c3fd8656cf425e9f')throw new Error('Wrong PCB');
const state=async()=>({components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:(await eda.pcb_Drc.getCurrentRuleConfiguration()).config});
const before=await state();if(before.components.length!==230)throw new Error('Wrong component count');
const all=await eda.pcb_PrimitiveLine.getAll();const wanted=new Set(data.remove_line_ids);
if(all.filter(p=>wanted.has(p.getState_PrimitiveId())).length!==wanted.size)throw new Error('Missing old segment');
for(const expected of data.removed_lines){const p=all.find(q=>q.getState_PrimitiveId()===expected.id);if(p.getState_Net()!==expected.net||p.getState_Layer()!==expected.layer||Math.abs(p.getState_StartX()-expected.x1)>.00011||Math.abs(p.getState_StartY()-expected.y1)>.00011||Math.abs(p.getState_EndX()-expected.x2)>.00011||Math.abs(p.getState_EndY()-expected.y2)>.00011||Math.abs(p.getState_LineWidth()-expected.width)>.00011)throw new Error('Old segment changed');}
await eda.pcb_Drc.stopRealTimeDrc();const madeLines=[],madeVias=[];
if(!await eda.pcb_PrimitiveLine.delete(data.remove_line_ids))throw new Error('Cannot remove old local segments');
try{
 for(const v of data.vias){const p=await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false);if(!p)throw new Error('Via create failed');madeVias.push(p.getState_PrimitiveId());}
 for(const l of data.lines){const p=await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false);if(!p)throw new Error('Track create failed');madeLines.push(p.getState_PrimitiveId());}
 if(JSON.stringify(before)!==JSON.stringify(await state()))throw new Error('Components or rules changed');
 if(!await eda.pcb_Document.save())throw new Error('Native save failed');
}catch(e){
 if(madeLines.length)await eda.pcb_PrimitiveLine.delete(madeLines);
 if(madeVias.length)await eda.pcb_PrimitiveVia.delete(madeVias);
 for(const l of data.removed_lines)await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false);
 await eda.pcb_Document.save();throw e;
}
return {saved:true,created_line_ids:madeLines,created_via_ids:madeVias,removed_line_ids:data.remove_line_ids,components_placement_and_rules_unchanged:true};
"""
result=invoke('r3-local-power-bus-apply',code,timeout=180)
after=grid.capture();(OUT/'applied-source.json').write_text(json.dumps(after,indent=2),encoding='utf-8')
selected={'BUS_RETURN','5V_PERIPH','GND'}
untouched={k:sorted([p for p in source[k] if p['net'] not in selected],key=lambda p:p['id'])==sorted([p for p in after[k] if p['net'] not in selected],key=lambda p:p['id']) for k in ['lines','vias']}
after_ids={p['id'] for p in after['lines']}
retained_old=set(p['id'] for p in source['lines'])-set(plan['remove_line_ids'])
audit=dict(snapshot=str(snapshot),snapshot_zip_sha256=sha(archive),plan_sha256=sha(path),
    source_pcb_sha256=plan['native_pcb_sha256'],applied_pcb_sha256=sha(PCB),
    result=result,all_pads_unchanged=canonical(source)['pads']==canonical(after)['pads'],
    unselected_copper_unchanged=untouched,all_other_api_line_ids_preserved=retained_old<=after_ids,
    original_via_ids_preserved={p['id'] for p in source['vias']}<={p['id'] for p in after['vias']},
    api_counts={k:len(after[k]) for k in ['pads','lines','vias']},
    requires_ground_rebuild_and_native_drc=True,manufacturing_release=False)
(OUT/'apply-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
assert audit['all_pads_unchanged'] and all(untouched.values()) and audit['original_via_ids_preserved']
# Native creation can split an existing same-net track at a new junction.
# verify_native_exchange.py must prove exact copper coverage before DRC.
assert all(sha(PROJECT/rel)==h for rel,h in checkpoint['files'].items() if rel!='pcb/PCB1.epcb2')
print(json.dumps({k:v for k,v in audit.items() if k!='result'},indent=2),flush=True)
