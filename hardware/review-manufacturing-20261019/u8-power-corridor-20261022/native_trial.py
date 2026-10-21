"""One isolated native-router trial after the verified joint corridor change."""
from pathlib import Path
import sys,json,hashlib,shutil
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(ROOT));from native_review import call
read=lambda p:json.loads(p.read_text(encoding='utf8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(OUT/'plan.json');audit=read(OUT/'native-trial-preflight.json');route=read(OUT/'native-trial-copper.json')
assert audit['geometric_pass'] and not (OUT/'native-trial-apply.json').exists()
source=Path(plan['project']);assert sha(source/'pcb/PCB1.epcb2')==plan['source_pcb_sha256']
project=source.parent/'FPGA-Music-Dualscreen-U8BusWork-20261022'
if (OUT/'native-candidate-source.json').exists():
 info=read(OUT/'native-candidate-source.json');files=info['source_files'];session=read(OUT/'native-session.json')
 assert sha(project/'pcb/PCB1.epcb2')==plan['source_pcb_sha256'],'Do not replay a mutated trial'
else:
 assert not project.exists();files={}
 for p in source.rglob('*'):
  if not p.is_file():continue
  rel=p.relative_to(source);files[rel.as_posix()]=sha(p);dest=project/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 old=project/(source.name+'.eprj3');desc=read(old);desc['name']=project.name;desc['content']='Coordinated U8 supply corridor and bus fanout, with INPUT_LOAD_N recovery required. Isolated construction trial, NOT FOR FABRICATION.'
 descriptor=project/(project.name+'.eprj3');descriptor.write_text(json.dumps(desc,ensure_ascii=False,indent=2),encoding='utf8');old.unlink()
 info=dict(source_project=str(source),source_files=files,source_pcb_sha256=plan['source_pcb_sha256'],candidate_project=str(project),candidate_descriptor=str(descriptor),manufacturing_release=False)
 (OUT/'native-candidate-source.json').write_text(json.dumps(info,indent=2))
 session=call('u8-native-open-trial',['open','--path',str(descriptor),'--headless','true'],120);(OUT/'native-session.json').write_text(json.dumps(session,indent=2))
wrapper=(ROOT/'regional-recovery-20261021-r21/native_project.py').read_text().replace("'r21-'","'u8-native-'")
(OUT/'native_project.py').write_text(wrapper);sys.path.insert(0,str(OUT));from native_project import invoke
doc=None
for i in range(4):
 docs=invoke('trial-pcb-list-'+str(i),'await new Promise(r=>setTimeout(r,1800));return await eda.dmt_Pcb.getAllPcbsInfo();',timeout=35)
 if not docs:continue
 assert docs[0]['uuid']=='c3fd8656cf425e9f'
 try:tab=invoke('trial-open-pcb-'+str(i),"await new Promise(r=>setTimeout(r,1800));return await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');",timeout=45)
 except RuntimeError as e:
  print('OPEN_WAIT',str(e)[:180],flush=True);continue
 doc=invoke('trial-identity-'+str(i),'return await eda.dmt_SelectControl.getCurrentDocumentInfo();',timeout=35)
 if doc and doc.get('documentType')==3:break
assert doc and doc['documentType']==3;info['parent_project_uuid']=doc['parentProjectUuid'];(OUT/'native-candidate-source.json').write_text(json.dumps(info,indent=2))
code="""
const d=__CLI__.args;const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(doc?.parentProjectUuid!==d.project)throw new Error('Wrong project');await eda.pcb_Drc.stopRealTimeDrc();
if(!await eda.pcb_PrimitiveLine.delete(d.remove_lines.map(p=>p.id)))throw new Error('Delete line');if(!await eda.pcb_PrimitiveVia.delete(d.remove_vias.map(p=>p.id)))throw new Error('Delete via');let createdL=[],createdV=[];
for(const p of d.vias){const q=await eda.pcb_PrimitiveVia.create(p.net,p.x,p.y,p.hole,p.diameter);if(!q)throw new Error('Via');createdV.push(q.getState_PrimitiveId());}
for(const p of d.lines){const q=await eda.pcb_PrimitiveLine.create(p.net,p.layer,p.x1,p.y1,p.x2,p.y2,p.width,false);if(!q)throw new Error('Line');createdL.push(q.getState_PrimitiveId());}
if(!await eda.pcb_Document.save())throw new Error('Save');return {createdL,createdV,removedL:d.remove_lines.map(p=>p.id),removedV:d.remove_vias.map(p=>p.id)};
"""
result=invoke('trial-apply-corridor',code,dict(project=doc['parentProjectUuid'],**route),180)
(OUT/'native-trial-apply.json').write_text(json.dumps(result,indent=2));print('APPLIED',len(result['createdL']),len(result['createdV']),flush=True)
for layer in [1,15,16,2]:
 print('REBUILD',layer,invoke('trial-rebuild-'+str(layer),"const ps=(await eda.pcb_PrimitivePour.getAll()).filter(p=>p.getState_Layer()===__CLI__.args.layer);if(ps.length!==1||!await ps[0].rebuildCopperRegion())throw new Error('Rebuild');return await eda.pcb_Document.save();",dict(layer=layer),180),flush=True)
drc=invoke('trial-pre-route-drc','return await eda.pcb_Drc.check(true,false,true);',timeout=180);(OUT/'native-pre-route-drc.json').write_text(json.dumps(drc,indent=2))
print('PRE_DRC',[(c['name'],c.get('count')) for c in drc],flush=True)
assert all(c['name']=='Connection Error' or not c.get('count') for c in drc)
(OUT/'native-router-state.json').write_text(json.dumps(dict(state='requested',session=session['sessionId'],project=str(project),nets=['BUS_MOSI','BUS_SCK','INPUT_LOAD_N']),indent=2))
try:
 routed=invoke('trial-route-three-nets',"const result=await eda.pcb_Document.autoRouting({RoutingNets:['BUS_MOSI','BUS_SCK','INPUT_LOAD_N'],layers:[1,16],existingPrimitiveMode:'keep',optimization:1});await eda.pcb_Document.save();return result;",timeout=300)
 (OUT/'native-router-result.json').write_text(json.dumps(routed,indent=2));print('ROUTER',json.dumps(routed),flush=True)
 (OUT/'native-router-state.json').write_text(json.dumps(dict(state='returned',result=routed),indent=2))
except Exception as e:
 (OUT/'native-router-state.json').write_text(json.dumps(dict(state='observation_failed_not_terminal',error=str(e),session=session['sessionId']),indent=2));raise
assert all(sha(source/p)==h for p,h in files.items()),'Original checkpoint changed'
