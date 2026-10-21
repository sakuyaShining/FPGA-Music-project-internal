"""Apply verified complete-net routes only to the independent four-layer clone."""
import json,sys,hashlib,zipfile,time
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from native_project import invoke,info,PROJECT
from resume_offline import read_native
import grid_route as g;g.invoke=invoke
qa=json.loads((BASE/'independent-geometry.json').read_text());plan=json.loads((BASE/'fixed-fanout-four-via-bundle-1/plan.json').read_text());source=json.loads(Path(info['source_capture']).read_text());assert qa['combined_geometry_pass'] and qa['plan_sha256']==hashlib.sha256((BASE/'fixed-fanout-four-via-bundle-1/plan.json').read_bytes()).hexdigest()
assert not (BASE/'native-apply-audit.json').exists(),'Never blindly repeat an applied candidate'
canon=lambda d:{k:sorted(d[k],key=lambda p:p['id']) for k in ['pads','lines','vias']};assert canon(g.capture())==canon(source)
selected={r['net'] for r in plan['routes']};raw=read_native(PROJECT/'pcb/PCB1.epcb2');apiids={p['id'] for p in source['lines']}
assert not [(i,p['netName']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2] and p.get('netName') in selected and i not in apiids],'Selected net contains hidden copper; cannot use getAll clear'
identity="return {document:await eda.dmt_SelectControl.getCurrentDocumentInfo(),components:(await eda.pcb_PrimitiveComponent.getAll()).map(c=>[c.getState_PrimitiveId(),c.getState_Designator(),c.getState_X(),c.getState_Y(),c.getState_Rotation()]).sort((a,b)=>a[0].localeCompare(b[0])),rules:(await eda.pcb_Drc.getCurrentRuleConfiguration()).config};"
before=invoke('before-route-identity',identity);assert before['document']['parentProjectUuid']=='9dae993624cc75021973b80ae220b0560cdeb1254a019e569191411feedb7fa6';assert len(before['components'])==230
snap=Path('D:/FPGA-Project/snapshots')/('before-audio-r6-copper-'+datetime.now().strftime('%Y%m%d-%H%M%S'));snap.mkdir();archive=snap/'native-audio-before-routing.zip'
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(PROJECT.rglob('*')):
  if p.is_file():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
payload=dict(nets=sorted(selected),lines=[p for r in plan['routes'] for p in r['lines']],vias=[p for r in plan['routes'] for p in r['vias']],other_line_ids=[p['id'] for p in source['lines'] if p['net'] not in selected],other_via_ids=[p['id'] for p in source['vias'] if p['net'] not in selected])
assert all(p['width']>=5.9999 and p['layer'] in [1,16,2] for p in payload['lines'])
code="const data="+json.dumps(payload)+";"+"""
if((await eda.pcb_Layer.getTheNumberOfCopperLayers())!==4)throw new Error('Not four layers');
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!=='9dae993624cc75021973b80ae220b0560cdeb1254a019e569191411feedb7fa6')throw new Error('Wrong project');
await eda.pcb_Drc.stopRealTimeDrc();const ns=new Set(data.nets);const allL=await eda.pcb_PrimitiveLine.getAll(),allV=await eda.pcb_PrimitiveVia.getAll();
const equal=(a,b)=>a.length===b.length&&a.every(v=>b.includes(v));
if(!equal(allL.filter(p=>!ns.has(p.getState_Net())).map(p=>p.getState_PrimitiveId()),data.other_line_ids)||!equal(allV.filter(p=>!ns.has(p.getState_Net())).map(p=>p.getState_PrimitiveId()),data.other_via_ids))throw new Error('Source changed');
const prior={lines:allL.filter(p=>ns.has(p.getState_Net())).map(p=>({net:p.getState_Net(),layer:p.getState_Layer(),x1:p.getState_StartX(),y1:p.getState_StartY(),x2:p.getState_EndX(),y2:p.getState_EndY(),width:p.getState_LineWidth()})),vias:allV.filter(p=>ns.has(p.getState_Net())).map(p=>({net:p.getState_Net(),x:p.getState_X(),y:p.getState_Y(),hole:p.getState_HoleDiameter(),diameter:p.getState_Diameter()}))};
const clear=async()=>{let a=(await eda.pcb_PrimitiveLine.getAll()).filter(p=>ns.has(p.getState_Net()));let b=(await eda.pcb_PrimitiveVia.getAll()).filter(p=>ns.has(p.getState_Net()));if(a.length&&!await eda.pcb_PrimitiveLine.delete(a.map(p=>p.getState_PrimitiveId())))throw new Error('Clear lines');if(b.length&&!await eda.pcb_PrimitiveVia.delete(b.map(p=>p.getState_PrimitiveId())))throw new Error('Clear vias');};
const create=async p=>{for(const v of p.vias)if(!await eda.pcb_PrimitiveVia.create(v.net,v.x,v.y,v.hole,v.diameter,0,null,null,false))throw new Error('Via');for(const l of p.lines)if(!await eda.pcb_PrimitiveLine.create(l.net,l.layer,l.x1,l.y1,l.x2,l.y2,l.width,false))throw new Error('Line');};
await clear();try{await create(data);}catch(error){await clear();await create(prior);await eda.pcb_Document.save();throw error;}
if(!await eda.pcb_Document.save())throw new Error('Save');return {createdLines:data.lines.length,createdVias:data.vias.length,prior,nets:data.nets};
"""
value=invoke('apply-complete-nets',code,timeout=240)
after=g.capture();ident=invoke('after-route-identity',identity)
unchanged={k:sorted([p for p in source[k] if p['net'] not in selected],key=lambda p:p['id'])==sorted([p for p in after[k] if p['net'] not in selected],key=lambda p:p['id']) for k in ['lines','vias']}
audit=dict(snapshot=str(archive),snapshot_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),plan_sha256=qa['plan_sha256'],nets=sorted(selected),components_unchanged=before['components']==ident['components'],pads_unchanged=canon(source)['pads']==canon(after)['pads'],rules_unchanged=before['rules']==ident['rules'],unselected_copper_unchanged=unchanged,api_counts={k:len(v) for k,v in after.items()},result=value,manufacturing_release=False)
(BASE/'native-apply-audit.json').write_text(json.dumps(audit,indent=2));(BASE/'native-applied-capture.json').write_text(json.dumps(after,indent=2))
assert audit['components_unchanged'] and audit['pads_unchanged'] and audit['rules_unchanged'] and all(unchanged.values())
assert all(hashlib.sha256((Path(info['source_project'])/p).read_bytes()).hexdigest()==h for p,h in info['source_files'].items())
print(json.dumps({k:v for k,v in audit.items() if k!='result'},indent=2),flush=True)
