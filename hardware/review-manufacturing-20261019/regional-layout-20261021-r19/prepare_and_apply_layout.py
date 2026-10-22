"""Apply one coordinated regional layout in a source-verified isolated native project."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json,hashlib,shutil,math
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,str(ROOT));from native_review import call
sys.path.insert(0,str(ROOT/'inv2-comparison-20261021-r16'));from exchange import read
from physical_geometry import actual_pad
from shapely.geometry import LineString,Point,box
cp,pcb,s=read();layout=json.loads((BASE/'selected-layout.json').read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert cp['pcb_sha256']==layout['source_pcb_sha256']
assert not layout['selected_variant']['bbox_conflicts']
assert all(sha(Path(cp['project'])/p)==h for p,h in cp['files'].items())
assert not (BASE/'native-apply-audit.json').exists(),'Do not replay mutation'
window=box(*layout['routing_window_mm']);selected=set(layout['signal_nets']);removeL={};removeV={}
for p in s['lines']:
    if p['net'] in selected and LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).intersects(window):removeL[p['id']]=p
for p in s['vias']:
    if p['net'] in selected and window.covers(Point(p['x']*.0254,p['y']*.0254)):removeV[p['id']]=p
additional=set();powers=set();movedpads=[p for c in layout['selected_variant']['changes'] for p in c['expected_pads']]
for p in movedpads:
    q=actual_pad(p)
    for v in s['lines']:
        if v['layer']!=p['layer'] or v['net']==p['net']:continue
        shape=LineString([(v['x1']*.0254,v['y1']*.0254),(v['x2']*.0254,v['y2']*.0254)]).buffer(v['width']*.0254/2,quad_segs=32)
        if shape.distance(q)<.165:
            removeL[v['id']]=v
            (powers if v['net'] in ['GND','3V3_IO','3V3_PERIPH'] else additional).add(v['net'])
    for v in s['vias']:
        pt=Point(v['x']*.0254,v['y']*.0254)
        if (v['net']!=p['net'] and pt.distance(q)-v['diameter']*.0254/2<.165) or pt.distance(q)-v['hole']*.0254/2<.25:
            assert not v['net'].startswith('I2S_'),'Do not disturb audio via to fit a candidate'
            removeV[v['id']]=v
            (powers if v['net'] in ['GND','3V3_IO','3V3_PERIPH'] else additional).add(v['net'])
assert not {v['net'] for v in removeL.values() if v['net'].startswith('I2S_')},'Candidate overlaps fixed audio geometry'
plan=dict(source_pcb_sha256=cp['pcb_sha256'],changes=layout['selected_variant']['changes'],remove_lines=list(removeL.values()),remove_vias=list(removeV.values()),original_signal_nets=sorted(selected),additional_signal_nets=sorted(additional),affected_power_nets=sorted(powers|{'3V3_IO','3V3_PERIPH','GND'}),routing_nets=sorted(selected|additional|{'3V3_IO','3V3_PERIPH'}),manufacturing_release=False)
(BASE/'regional-edit-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf8')
old=Path(cp['project']);new=old.parent/'FPGA-Music-Dualscreen-RegionalLayout-20261021-r19'
assert not new.exists(),'Do not overwrite a native working project'
new.mkdir()
for rel in cp['files']:
    dest=new/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(old/rel,dest)
descriptor=new/(old.name+'.eprj3');data=json.loads(descriptor.read_text(encoding='utf8'));data['name']=new.name;data['content']='Coordinated U15 control/display corridor layout and local rerouting. Experimental, NOT FOR FABRICATION.'
renamed=new/(new.name+'.eprj3');renamed.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8');descriptor.unlink()
info=dict(created_utc=datetime.now(timezone.utc).isoformat(),source_project=str(old),source_files=cp['files'],source_pcb_sha256=cp['pcb_sha256'],source_capture=cp['source_capture'],candidate_project=str(new),candidate_descriptor=str(renamed),source_snapshot=str(BASE/'source-before-regional-layout.zip'),source_snapshot_sha256=sha(BASE/'source-before-regional-layout.zip'),manufacturing_release=False)
(BASE/'native-candidate-source.json').write_text(json.dumps(info,indent=2),encoding='utf8')
session=call('r19-open-isolated',['open','--path',renamed.as_posix(),'--headless','true'],120)
(BASE/'native-session.json').write_text(json.dumps(session,indent=2),encoding='utf8')
wrapper=(ROOT/'harm-closure-20261021-r15/native_project.py').read_text(encoding='utf8').replace('r15-harm-','r19-region-').replace('r15 HARM candidate','r19 regional candidate')
(BASE/'native_project.py').write_text(wrapper,encoding='utf8')
sys.path.insert(0,str(BASE));from native_project import invoke
invoke('openpcb',"return await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');",timeout=120)
doc=invoke('identity','await eda.pcb_Drc.stopRealTimeDrc();return await eda.dmt_SelectControl.getCurrentDocumentInfo();')
assert doc['documentType']==3;info['parent_project_uuid']=doc['parentProjectUuid']
(BASE/'native-candidate-source.json').write_text(json.dumps(info,indent=2),encoding='utf8')
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
