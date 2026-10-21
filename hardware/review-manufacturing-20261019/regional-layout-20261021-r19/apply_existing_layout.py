"""Resume only the existing, verified, previously opened isolated layout project."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,hashlib,math
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(ROOT/'inv2-comparison-20261021-r16'));from exchange import read
sys.path.insert(0,str(BASE));from native_project import invoke
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp,pcb,s=read();plan=json.loads((BASE/'regional-edit-plan.json').read_text(encoding='utf8'));info=json.loads((BASE/'native-candidate-source.json').read_text(encoding='utf8'));session=json.loads((BASE/'native-session.json').read_text(encoding='utf8'))
new=Path(info['candidate_project']);old=Path(info['source_project'])
assert not (BASE/'native-apply-audit.json').exists()
assert sha(new/'pcb/PCB1.epcb2')==plan['source_pcb_sha256']==cp['pcb_sha256']
doc=invoke('identity-before-resume','return await eda.dmt_SelectControl.getCurrentDocumentInfo();')
assert doc and doc['documentType']==3
info['parent_project_uuid']=doc['parentProjectUuid'];(BASE/'native-candidate-source.json').write_text(json.dumps(info,indent=2),encoding='utf8')
removeL={p['id']:p for p in plan['remove_lines']};removeV={p['id']:p for p in plan['remove_vias']};additional=set(plan['additional_signal_nets']);powers=set(plan['affected_power_nets'])
code="""
const data=__CLI__.args;
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.parentProjectUuid!==data.project)throw new Error('Wrong project');
if(data.remove_lines.length&&!await eda.pcb_PrimitiveLine.delete(data.remove_lines.map(p=>p.id)))throw new Error('Remove line failed');
if(data.remove_vias.length&&!await eda.pcb_PrimitiveVia.delete(data.remove_vias.map(p=>p.id)))throw new Error('Remove via failed');
const changes=[];
for(const m of data.changes){
 if(m.type==='free_pad'){
  if(!await eda.pcb_PrimitivePad.modify(m.id,{x:m.pad_midpoint_mm[0]/.0254,y:m.pad_midpoint_mm[1]/.0254,rotation:m.rotation}))throw new Error('Test pad move failed');
 }else{
  let c=(await eda.pcb_PrimitiveComponent.getAll()).find(c=>c.getState_PrimitiveId()===m.id);
  if(!c)throw new Error('Component absent '+m.ref);
  if(!await eda.pcb_PrimitiveComponent.modify(m.id,{rotation:m.rotation}))throw new Error('Rotate failed');
  c=(await eda.pcb_PrimitiveComponent.getAll()).find(c=>c.getState_PrimitiveId()===m.id);
  const ps=await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(m.id);
  const x=ps.reduce((a,p)=>a+p.getState_X(),0)/ps.length,y=ps.reduce((a,p)=>a+p.getState_Y(),0)/ps.length;
  if(!await eda.pcb_PrimitiveComponent.modify(m.id,{x:c.getState_X()+m.pad_midpoint_mm[0]/.0254-x,y:c.getState_Y()+m.pad_midpoint_mm[1]/.0254-y}))throw new Error('Translate failed');
 }
 changes.push({ref:m.ref,type:m.type,id:m.id});
}
if(!await eda.pcb_Document.save())throw new Error('Save failed');
return {changes,removed_lines:data.remove_lines.map(p=>p.id),removed_vias:data.remove_vias.map(p=>p.id),saved:true};
"""
result=invoke('apply-layout',code,{**plan,'project':info['parent_project_uuid']},180)
import grid_route as g;g.invoke=invoke;capture=g.capture()
def canonical(q):return sorted(q,key=lambda p:p['id'])
movedrefs={m['ref'] for m in plan['changes']}
assert canonical([p for p in s['pads'] if p['ref'] not in movedrefs])==canonical([p for p in capture['pads'] if p['ref'] not in movedrefs])
for m in plan['changes']:
    ps=[p for p in capture['pads'] if p['ref']==m['ref']]
    for p in m['expected_pads']:
        q=next(v for v in ps if v['n']==p['n'])
        assert q['net']==p['net'] and math.dist((p['x'],p['y']),(q['x'],q['y']))*.0254<.003,(m['ref'],p,q)
audit=dict(utc=datetime.now(timezone.utc).isoformat(),result=result,pcb_sha256_after_layout=sha(new/'pcb/PCB1.epcb2'),unchanged_other_pads=True,status='layout_applied_rerouting_required',manufacturing_release=False)
(BASE/'native-apply-audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf8')
(BASE/'native-layout-capture.json').write_text(json.dumps(capture),encoding='utf8')
assert all(sha(old/p)==h for p,h in cp['files'].items())
print(json.dumps(dict(project=str(new),session=session,changed=result['changes'],removed_lines=len(removeL),removed_vias=len(removeV),additional_signal_nets=sorted(additional),affected_power_nets=sorted(powers),status=audit['status']),indent=2),flush=True)
