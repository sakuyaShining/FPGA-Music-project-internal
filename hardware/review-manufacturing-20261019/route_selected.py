"""Route selected nets, importing their copper only; preserve all other routes.

This is a trial, not a signoff. Reopen for topology validation and rebuild the
ground pours after routing mutations. Retain the native zero-clearance checkpoint.
"""
import hashlib
import json
import sys
import time
from native_review import ROOT,PROJECT,invoke
from offline_route import run,POWER
from ses_selected_copper import parse

selected=set(sys.argv[1:] or ['L0_M00'])
if selected & POWER:raise RuntimeError('Power routing requires separate width/load review')
stage='selected-'+str(time.time_ns())

def export_selected():
    return invoke(stage+'-before',"""
const ns=new Set(__CLI__.args.nets);return {
lines:(await eda.pcb_PrimitiveLine.getAll()).filter(p=>ns.has(p.getState_Net())).map(p=>({net:p.getState_Net(),layer:p.getState_Layer(),x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),width:p.getState_LineWidth()})),
vias:(await eda.pcb_PrimitiveVia.getAll()).filter(p=>ns.has(p.getState_Net())).map(p=>({net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),hole:p.getState_HoleDiameter(),diameter:p.getState_Diameter()}))};
""",{'nets':sorted(selected)},180)

def clear():
    return invoke(stage+'-clear',"""
const ns=new Set(__CLI__.args.nets);const ls=(await eda.pcb_PrimitiveLine.getAll()).filter(p=>ns.has(p.getState_Net()));const vs=(await eda.pcb_PrimitiveVia.getAll()).filter(p=>ns.has(p.getState_Net()));
if(ls.length&&!await eda.pcb_PrimitiveLine.delete(ls.map(p=>p.getState_PrimitiveId())))throw new Error('Track clear');
if(vs.length&&!await eda.pcb_PrimitiveVia.delete(vs.map(p=>p.getState_PrimitiveId())))throw new Error('Via clear');
await eda.pcb_Document.save();return {lines:ls.length,vias:vs.length};
""",{'nets':sorted(selected)},180)

def apply(payload,suffix):
    path=PROJECT/'review-exports/v2'/(stage+'-'+suffix+'.json')
    path.write_text(json.dumps(payload),encoding='utf-8')
    return invoke(stage+'-'+suffix,"""
const f=await eda.sys_FileSystem.readFileFromFileSystem(__CLI__.args.path);const p=JSON.parse(await f.text());
const ns=new Set(__CLI__.args.nets);if([...p.lines,...p.vias].some(x=>!ns.has(x.net)))throw new Error('Foreign net payload');
const identity=()=>eda.pcb_PrimitiveComponent.getAll().then(cs=>cs.map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]));
const before=await identity();for(const v of p.vias)if(!await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false))throw new Error('Via create');
for(const l of p.lines)if(!await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false))throw new Error('Track create');
if(JSON.stringify(before)!==JSON.stringify(await identity()))throw new Error('Component identity/placement changed');
await eda.pcb_Document.save();return {created_lines:p.lines.length,created_vias:p.vias.length,device_identity_and_placement_unchanged:true};
""",{'path':path.as_posix(),'nets':sorted(selected)},240)

before=export_selected()
journal={'nets':sorted(selected),'before':before,'state':'prepared','requires_ground_rebuild':True,'fabrication_release':False}
jpath=ROOT/(stage+'-journal.json')
def save():jpath.write_text(json.dumps(journal,indent=2),encoding='utf-8')
save()
try:
    journal['removed']=clear();journal['state']='cleared';save()
    out=run(stage,selected);journal['routing_directory']=str(out);save()
    candidate=parse((out/'result.ses').read_text(encoding='utf-8'),selected)
    if not candidate['lines']:raise RuntimeError('No selected-net paths in result')
    (out/'selected-copper.json').write_text(json.dumps(candidate,indent=2),encoding='utf-8')
    journal['applied']=apply(candidate,'apply');journal['state']='applied_pending_native_reopen_drc';save()
    print({'journal':str(jpath),'nets':sorted(selected),'state':journal['state'],'lines':len(candidate['lines']),'vias':len(candidate['vias'])},flush=True)
except Exception as e:
    journal['error']=str(e);journal['state']='rolling_back';save()
    clear();journal['rollback']=apply(before,'rollback');journal['state']='rolled_back_needs_reopen_check';save()
    raise
