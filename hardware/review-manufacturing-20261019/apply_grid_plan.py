"""Apply an already checked local route plan through native APIs, with rollback."""
import json
import hashlib
import sys
import time
from pathlib import Path
from native_review import ROOT,PROJECT,invoke

plan_path=Path(sys.argv[1])
if not plan_path.is_absolute():plan_path=ROOT/plan_path
plan=json.loads(plan_path.read_text(encoding='utf-8'))
source_path=ROOT/plan.get('source_file','grid-route-source.json')
source=json.loads(source_path.read_text(encoding='utf-8'))
if 'source_sha256' in plan:assert hashlib.sha256(source_path.read_bytes()).hexdigest()==plan['source_sha256'],'Stale route plan'
nets=set(plan['nets'])
assert all(p['net'] in nets for p in plan['lines']+plan['vias'])
assert all(p['width']>=5.9999 for p in plan['lines']),'Track narrower than unchanged native 6 mil minimum'
assert all(e['min_foreign_copper_gap_mm']>=.158 for r in plan['routes'] for e in r['edges'])
plan['other_line_ids']=[p['id'] for p in source['lines'] if p['net'] not in nets]
plan['other_via_ids']=[p['id'] for p in source['vias'] if p['net'] not in nets]
name='grid-apply-'+str(time.time_ns());payload=PROJECT/'review-exports/v2'/(name+'.json')
payload.write_text(json.dumps(plan),encoding='utf-8')
value=invoke(name,'const data='+json.dumps(plan,ensure_ascii=True)+';'+"""
const ns=new Set(data.nets);
let allLines=await eda.pcb_PrimitiveLine.getAll(),allVias=await eda.pcb_PrimitiveVia.getAll();
const equalSet=(actual,expected)=>{const a=new Set(actual),b=new Set(expected);return a.size===b.size&&[...a].every(v=>b.has(v));};
if(!equalSet(allLines.filter(p=>!ns.has(p.getState_Net())).map(p=>p.getState_PrimitiveId()),data.other_line_ids)||!equalSet(allVias.filter(p=>!ns.has(p.getState_Net())).map(p=>p.getState_PrimitiveId()),data.other_via_ids))throw new Error('Native copper changed since planning; recapture before applying');
const before={lines:allLines.filter(p=>ns.has(p.getState_Net())).map(p=>({net:p.getState_Net(),layer:p.getState_Layer(),x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),width:p.getState_LineWidth()})),vias:allVias.filter(p=>ns.has(p.getState_Net())).map(p=>({net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),hole:p.getState_HoleDiameter(),diameter:p.getState_Diameter()}))};
const identities=()=>eda.pcb_PrimitiveComponent.getAll().then(cs=>cs.map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]));const components=await identities();if(components.length!==230)throw new Error('Wrong component count');
const clear=async()=>{const ls=(await eda.pcb_PrimitiveLine.getAll()).filter(p=>ns.has(p.getState_Net()));const vs=(await eda.pcb_PrimitiveVia.getAll()).filter(p=>ns.has(p.getState_Net()));if(ls.length&&!await eda.pcb_PrimitiveLine.delete(ls.map(p=>p.getState_PrimitiveId())))throw new Error('Clear tracks');if(vs.length&&!await eda.pcb_PrimitiveVia.delete(vs.map(p=>p.getState_PrimitiveId())))throw new Error('Clear vias');};
const create=async p=>{for(const v of p.vias)if(!await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false))throw new Error('Via create');for(const l of p.lines)if(!await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false))throw new Error('Track create');};
await clear();try{await create(data);if(JSON.stringify(components)!==JSON.stringify(await identities()))throw new Error('Device identity or placement changed');}catch(error){await clear();await create(before);await eda.pcb_Document.save();throw error;}
if(!await eda.pcb_Document.save())throw new Error('Native document save failed');return {nets:data.nets,before,created_lines:data.lines.length,created_vias:data.vias.length,device_identity_and_placement_unchanged:true,requires_ground_rebuild_and_fresh_drc:true};
""",{},240)
(ROOT/(name+'-audit.json')).write_text(json.dumps(value,indent=2),encoding='utf-8')
print({k:v for k,v in value.items() if k!='before'},flush=True)
