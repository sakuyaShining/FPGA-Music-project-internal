"""Apply only independently planned ground stitches to the isolated R15 PCB."""
from pathlib import Path
import sys,json,hashlib,zipfile
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE))
from native_project import invoke,PROJECT,info
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pcb=PROJECT/'pcb/PCB1.epcb2';plan=read(BASE/'ground-stitch-plan.json')
assert sha(pcb)==plan['source_pcb_sha256']
assert not (BASE/'ground-stitch-apply-audit.json').exists()
snapshot=BASE/'pre-ground-native-source.zip'
assert not snapshot.exists()
with zipfile.ZipFile(snapshot,'w',zipfile.ZIP_DEFLATED) as z:
    for p in PROJECT.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(PROJECT))
with zipfile.ZipFile(snapshot) as z:assert z.testzip() is None
for name in ['native-drc.json','native-drc-meta.json','native-verified-capture.json','actual-layout-review.json']:
    p=BASE/name;dest=BASE/('pre-ground-'+name)
    assert p.exists() and not dest.exists()
    p.rename(dest)
code="""
const data=__CLI__.args;
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc?.parentProjectUuid!==data.project)throw new Error('Wrong project');
const ids=[];
try {
 for(const v of data.vias){
  const q=await eda.pcb_PrimitiveVia.create('GND',v.x,v.y,v.hole,v.diameter);
  if(!q)throw new Error('Via creation failed');
  ids.push(q.getState_PrimitiveId());
 }
 if(!await eda.pcb_Document.save())throw new Error('Save failed');
 return {createdV:ids,document:doc,saved:true};
}catch(e){
 for(const id of ids)await eda.pcb_PrimitiveVia.delete(id);
 await eda.pcb_Document.save();throw e;
}
"""
result=invoke('apply-ground-stitches',code,dict(project=info['parent_project_uuid'],vias=plan['vias']),180)
assert len(result['createdV'])==5 and len(set(result['createdV']))==5
audit=dict(utc=datetime.now(timezone.utc).isoformat(),source_pcb_sha256=plan['source_pcb_sha256'],snapshot=str(snapshot),snapshot_sha256=sha(snapshot),result=result,pcb_sha256_after_save=sha(pcb),status='applied_pending_rebuild_and_drc',manufacturing_release=False)
(BASE/'ground-stitch-apply-audit.json').write_text(json.dumps(audit,indent=2)+'\n',encoding='utf-8')
print(json.dumps(audit,indent=2),flush=True)
