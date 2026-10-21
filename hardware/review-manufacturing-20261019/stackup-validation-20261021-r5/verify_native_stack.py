"""Verify native load/save/reopen preserves a real ordered four-copper stack."""
import json,sys,hashlib,math
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from native_project import invoke,PROJECT,info
from resume_offline import read_native
import grid_route as g;g.invoke=invoke
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();PCB=PROJECT/'pcb/PCB1.epcb2';old=read_native(BASE/'before-native.epcb2')
assert not (BASE/'native-full-drc.json').exists(),'Do not repeat completed verification without a new source change'
v=invoke('save-and-reopen',"""const tab=await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');if(!tab)throw new Error('Open');await new Promise(r=>setTimeout(r,1800));let d=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(d?.parentProjectUuid==='dbcb11b6e1bcc817f595b7053414e8dc88b8aec2cb33fa4f75e16a6f290dab6b')throw new Error('Wrong r4 project');if((await eda.pcb_PrimitiveComponent.getAll()).length!==230)throw new Error('Components');if((await eda.pcb_Layer.getTheNumberOfCopperLayers())!==4)throw new Error('Layer count');if(!await eda.pcb_Document.save())throw new Error('Save');if(!await eda.dmt_EditorControl.closeDocument(d.tabId))throw new Error('Close');if(!await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f'))throw new Error('Reopen');await eda.pcb_Drc.stopRealTimeDrc();return {document:await eda.dmt_SelectControl.getCurrentDocumentInfo(),layers:await eda.pcb_Layer.getTheNumberOfCopperLayers(),components:(await eda.pcb_PrimitiveComponent.getAll()).length};""",timeout=150)
(BASE/'native-open-save-reopen.json').write_text(json.dumps(v,indent=2));print('REOPEN',v,flush=True)
new=read_native(PCB)
unchanged={}
for kind in {k for k,i in old}-{'LAYER','LAYER_PHYS','DOCHEAD'}:
 same={i:p for (k,i),p in old.items() if k==kind}=={i:p for (k,i),p in new.items() if k==kind};unchanged[kind]=same;assert same,kind
physical={json.loads(i)[1]:p for (k,i),p in new.items() if k=='LAYER_PHYS'};wire={p['layerId']:p for (k,i),p in new.items() if k=='LAYER'}
order=sorted([i for i in physical if i in [1,15,16,2] or wire.get(i,{}).get('layerType')=='SUBSTRATE'],key=lambda i:physical[i]['zIndex']);assert order==[1,361,15,362,16,363,2],order
rows=[]
for expected in info['physical_stack_spec']:
 i=expected['layer'];p=physical[i];assert abs(p['thickness']-expected['native_mil'])<.000001,(i,p['thickness'],expected['native_mil']);assert p['zIndex']==expected['zIndex'];rows.append(dict(layer=i,material=p['material'],native_mil=p['thickness'],millimetres=p['thickness']*.0254,zIndex=p['zIndex'],loss_tangent_value=p.get('lossTangent'),loss_tangent_qualified=False))
assert all(sha(Path(info['source_project'])/p)==h for p,h in info['source_files'].items()),'r4 source changed'
pre=sha(PCB);drc=invoke('full-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=300);post=sha(PCB);assert pre==post
(BASE/'native-full-drc.json').write_text(json.dumps(drc,ensure_ascii=False,indent=2),encoding='utf-8');counts={p['name']:p.get('count',0) for p in drc};assert counts=={'Connection Error':62},counts
capture=g.capture();(BASE/'native-verified-capture.json').write_text(json.dumps(capture,indent=2))
report=dict(utc=datetime.now(timezone.utc).isoformat(),pcb_sha256=post,source_stable_during_drc=True,full_native_drc=counts,physical_order=order,physical_stack=rows,copper_and_dielectric_mm=sum(p['millimetres'] for p in rows),finished_with_preserved_mask_mm=sum(p['millimetres'] for p in rows)+sum(physical[i]['thickness']*.0254 for i in [5,6]),all_other_native_record_groups_unchanged=unchanged,all_17_supporting_files_unchanged=True,physical_stack_structure_verified=True,dielectric_loss_properties_qualified=False,factory_process_approved=False,sensor_capacitance_qualified=False,i2s_signoff=False,manufacturing_release=False)
for rel,h in info['source_files'].items():
 if rel=='pcb/PCB1.epcb2' or rel.endswith('.eprj3'):continue
 assert sha(PROJECT/rel)==h,rel
(BASE/'native-stack-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='all_other_native_record_groups_unchanged'},ensure_ascii=False,indent=2),flush=True)
