"""Build a separate r5 project with verified native-unit physical stack records."""
import json,sys,hashlib,copy,shutil
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'joint-routing-20261021-r4'))
from resume_offline import read_native
from candidate_native import call
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
cp=read(ROOT/'ACTIVE-ROUTING-CANDIDATE.json');OLD=Path(cp['project']);NEW=OLD.parent/'FPGA-Music-Dualscreen-4L-Stackup-20261021-r5'
assert cp['pcb_sha256']=='97a837d8411cef56633792edbb716451a4f6806a66dba659a91058e0c69c2515'
assert all(sha(OLD/p)==h for p,h in cp['files'].items())
if NEW.exists():
 assert '--repair-unopened' in sys.argv and not (BASE/'native-session.json').exists(),'Never overwrite an opened r5 project'
 assert NEW.resolve()==(OLD.parent/'FPGA-Music-Dualscreen-4L-Stackup-20261021-r5').resolve()
 for rel,h in cp['files'].items():
  if rel=='pcb/PCB1.epcb2' or rel.endswith('.eprj3'):continue
  assert sha(NEW/rel)==h,rel
else:NEW.mkdir()
for rel in cp['files']:
 q=NEW/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OLD/rel,q)
old_desc=NEW/(OLD.name+'.eprj3');desc=NEW/(NEW.name+'.eprj3');d=read(old_desc);d['name']=NEW.name;d['content']='R5 physical-stack metadata candidate from r4. Not released for fabrication; material loss, touch capacitance, return and final routing remain unqualified.';desc.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');old_desc.unlink()
PCB=NEW/'pcb/PCB1.epcb2';raw=PCB.read_text(encoding='utf-8');before=read_native(PCB)
# Installed encoder/decoder and its UI confirm raw thickness is mil:
# model = raw/10; UI_mm = mil2mm(model*10). Online format comment is inaccurate.
spec=[(1,.035,None,None,1000),(361,.2104,'7628',4.6,1001),(15,.0152,None,None,1002),(362,1.065,'FR4',4.6,1003),(16,.0152,None,None,1004),(363,.2104,'7628',4.6,1005),(2,.035,None,None,9000)]
phys={i:dict(material=material,thickness=round(mm/.0254,3),permittivity=dk,lossTangent=None if material else None,isKeepIsland=True,zIndex=z) for i,mm,material,dk,z in spec}
# Loss tangent is not given in the selected primary table. Null is explicit in
# source; the editor may normalize it to 0. No lossy SI model is claimed.
substrate=copy.deepcopy(next(v for (k,i),v in before.items() if k=='LAYER' and v['layerId']==361))
newlayers={i:{**substrate,'layerId':i,'layerName':'Dielectric'+str(i-360)} for i in [362,363]}
lines=raw.splitlines(keepends=True);headers=[]
for line in lines:
 if line.startswith('{') and '||' in line:headers.append(json.loads(line.split('||',1)[0]))
ticket=max(h.get('ticket',0) for h in headers);active=False;seen=set();last=None;result=[]
for line in lines:
 if not line.startswith('{') or '||' not in line:result.append(line);continue
 h,b=line.split('||',1);header=json.loads(h);body=json.loads(b.rstrip('\r\n|')) if b.rstrip('\r\n|').strip() else None
 if header['type']=='DOCHEAD':active=body is not None and body.get('docType')=='PCB'
 if active:
  last=len(result)
  if header['type']=='LAYER_PHYS':
   layer=json.loads(header['id'])[1]
   if layer in phys:
    line=h+'||'+json.dumps(phys[layer],ensure_ascii=False,separators=(',',':'))+'|\n';seen.add(layer)
 result.append(line)
assert last is not None and seen=={1,361,2}
extra=[]
for typ,layer,body in [('LAYER',i,p) for i,p in newlayers.items()]+[('LAYER_PHYS',i,p) for i,p in phys.items() if i not in seen]:
 ticket+=1;head=dict(type=typ,ticket=ticket,id=json.dumps([typ,layer],separators=(',',':')));extra.append(json.dumps(head,separators=(',',':'))+'||'+json.dumps(body,ensure_ascii=False,separators=(',',':'))+'|\n')
if not result[last].endswith(('\n','\r')):result[last]+='\n'
result[last+1:last+1]=extra;PCB.write_text(''.join(result),encoding='utf-8')
after=read_native(PCB)
for kind in {k for k,i in before}-{'LAYER','LAYER_PHYS'}:
 assert {i:p for (k,i),p in before.items() if k==kind}=={i:p for (k,i),p in after.items() if k==kind},kind
for (k,i),p in before.items():
 if k=='LAYER':assert after[k,i]==p
assert len([p for (k,i),p in after.items() if k=='LAYER_PHYS'])==13
record=dict(utc=datetime.now(timezone.utc).isoformat(),source_project=str(OLD),source_files=cp['files'],source_pcb_sha256=cp['pcb_sha256'],candidate_project=str(NEW),candidate_descriptor=str(desc),modified_raw_pcb_sha256=sha(PCB),changed_record_types=['LAYER_PHYS','LAYER'],all_copper_pads_components_nets_rules_pours_unchanged=True,new_substrate_layer_ids=[362,363],physical_stack_spec=[dict(layer=i,nominal_thickness_mm=mm,native_mil=phys[i]['thickness'],zIndex=z) for i,mm,m,dk,z in spec],copper_plus_dielectric_nominal_mm=sum(mm for i,mm,m,dk,z in spec),nominal_finished_board_mm=1.6,dielectric_loss_tangent='UNKNOWN; null may normalize to editor zero default; not a loss model',factory_stack_reference_only=True,manufacturing_release=False)
(BASE/'source-and-stack-edit.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');(BASE/'before-native.epcb2').write_bytes((OLD/'pcb/PCB1.epcb2').read_bytes());(BASE/'edited-before-open.epcb2').write_bytes(PCB.read_bytes())
v=call('r5-stackup-open',['open','--path',desc.as_posix(),'--headless','true'],120);(BASE/'native-session.json').write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(session=v,nominal_stack_sum_mm=record['copper_plus_dielectric_nominal_mm'],native_pcb_sha256=sha(PCB)),ensure_ascii=False,indent=2))
assert all(sha(OLD/p)==h for p,h in cp['files'].items())
