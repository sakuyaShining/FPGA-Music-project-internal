"""Apply the two independently checked vias to the existing isolated project."""
from pathlib import Path
import sys,json,hashlib,zipfile
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent;BASE=ROOT/'regional-recovery-20261021-r21'
sys.path.insert(0,str(BASE));from native_project import invoke,PROJECT,info
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=json.loads((OUT/'plan.json').read_text());assert plan['geometric_pass'] and sha(PROJECT/'pcb/PCB1.epcb2')==plan['source_pcb_sha256']
assert not (OUT/'native-apply.json').exists(),'Do not replay mutation'
with zipfile.ZipFile(OUT/'before-repair.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in PROJECT.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(OUT/'before-repair.zip') as z:assert z.testzip() is None
doc=invoke('bus-return-identity','await eda.pcb_Drc.stopRealTimeDrc();return await eda.dmt_SelectControl.getCurrentDocumentInfo();')
assert doc['documentType']==3 and doc['parentProjectUuid']==info['parent_project_uuid']
code="""
const d=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==d.project)throw new Error('Wrong project');let createdV=[];
try{for(const p of d.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via');createdV.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {createdV};
}catch(e){if(createdV.length)await eda.pcb_PrimitiveVia.delete(createdV);await eda.pcb_Document.save();throw e;}
"""
result=invoke('bus-return-apply',code,dict(project=doc['parentProjectUuid'],vias=plan['vias']))
(OUT/'native-apply.json').write_text(json.dumps(dict(source_pcb_sha256=plan['source_pcb_sha256'],result=result,manufacturing_release=False),indent=2))
print('CREATED',result,flush=True)
for layer in [1,15,16,2]:
 print('REBUILD',layer,invoke('bus-return-rebuild-'+str(layer),"const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer);if(ps.length!==1||!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');return await eda.pcb_Document.save();",{'layer':layer},180),flush=True)
drc=invoke('bus-return-full-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=180)
(OUT/'after-save-drc.json').write_text(json.dumps(drc,indent=2));(OUT/'after-save-meta.json').write_text(json.dumps(dict(pcb_sha256=sha(PROJECT/'pcb/PCB1.epcb2')),indent=2))
print('DRC',[(c['name'],c.get('count'),sum(len(n['list']) for n in c.get('list',[]))) for c in drc],flush=True)
