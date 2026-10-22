"""Finish the saved INV2 transaction; never create native copper here."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import sys,json,hashlib,zipfile,csv,re,math
O=Path(__file__).resolve().parent;B=O.parent;R=B.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path.insert(0,str(R));sys.path.insert(0,str(B))
import native_project as n
from native_review import call
from resume_offline import read_native
from native_plane_geometry import poured_planes
from four_layer_geometry import connected
from physical_geometry import actual_pad
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
import grid_route as g
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
write=lambda p,v:p.write_text(json.dumps(v,indent=2),encoding='utf8')
pcb=n.PROJECT/'pcb/PCB1.epcb2';state=rd(O/'native-state.json');before=rd(O/'native-before.json');plan=rd(O/'validated-copper-plan.json')
assert sha(pcb)==state['pcb_sha256']=='6509803e7afca781b7f71ad69183cc10d8f6413312701eb16a2cdc46dfe83afd'
assert sha(O/'validated-copper-plan.json')==before['plan_sha256']
assert sha(O/'full-preflight.json')==before['preflight_sha256']
if not (O/'reopened-session.json').exists():
 sessions=call('inv2-checkpoint-sessions',['session','list'],45)
 owned=[s for s in sessions if s['sessionId']==n.SESSION and s['status']=='alive']
 if owned:
  assert Path(owned[0]['path']).parent==n.PROJECT
  call('inv2-checkpoint-close-owned',['session','close','--session',n.SESSION],60)
 session=call('inv2-checkpoint-reopen',['open','--path',str(n.PROJECT/(n.PROJECT.name+'.eprj3')),'--headless','true'],120)
 write(O/'reopened-session.json',session);write(B/'native-session.json',session)
n.SESSION=rd(O/'reopened-session.json')['sessionId'];doc=None
for attempt in range(6):
 docs=n.invoke('inv2-ready-'+str(attempt),'await new Promise(r=>setTimeout(r,2500));return await eda.dmt_Pcb.getAllPcbsInfo();',timeout=35)
 if not docs:continue
 n.invoke('inv2-open-saved-'+str(attempt),"return await eda.dmt_EditorControl.openDocument('c3fd8656cf425e9f');",timeout=55)
 doc=n.invoke('inv2-reopened-identity-'+str(attempt),'return await eda.dmt_SelectControl.getCurrentDocumentInfo();',timeout=35)
 if doc and doc.get('documentType')==3:break
assert doc and doc['parentProjectUuid']==n.info['parent_project_uuid']
write(O/'reopened-identity.json',doc)
drc=n.invoke('inv2-reopened-drc','await eda.pcb_Drc.stopRealTimeDrc();return await eda.pcb_Drc.check(true,false,true);',timeout=180)
write(O/'checkpoint-drc.json',drc)
counts={c['name']:sum(len(v.get('list',[])) for v in c.get('list',[])) for c in drc}
assert counts=={'Connection Error':57},counts
assert sha(pcb)==state['pcb_sha256']
print('REOPENED_DRC',counts,flush=True)
g.invoke=n.invoke;cap=g.capture();final=read_native(pcb)
class SourceText:
 def __init__(self,s):self.s=s
 def read_text(self,**kwargs):return self.s
with zipfile.ZipFile(before['source_archive']) as z:
 assert z.testzip() is None
 sourcebytes=z.read('pcb/PCB1.epcb2')
 assert hashlib.sha256(sourcebytes).hexdigest()==before['source_pcb_sha256']
 original=read_native(SourceText(sourcebytes.decode('utf8')))
def lines(raw):
 return [dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
def vias(raw):
 return [dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
cap['lines']=lines(final);cap['vias']=vias(final);write(O/'checkpoint-capture.json',cap)
for k,p in original.items():
 if k[0] not in ['DOCHEAD','LINE','VIA','POURED']:assert final[k]==p,('Non-copper changed',k)
assert {k for k in original if k[0] not in ['DOCHEAD','LINE','VIA','POURED']}=={k for k in final if k[0] not in ['DOCHEAD','LINE','VIA','POURED']}
descriptor_metadata_changes=[]
for rel,h in before['files'].items():
 if rel=='pcb/PCB1.epcb2' or sha(n.PROJECT/rel)==h:continue
 assert rel==n.PROJECT.name+'.eprj3',('Non-PCB file changed',rel)
 with zipfile.ZipFile(before['source_archive']) as z:old_desc=json.loads(z.read(rel))
 new_desc=rd(n.PROJECT/rel)
 def scrub(v,path=''):
  if isinstance(v,dict):
   return {k:scrub(x,path+'/'+k) for k,x in v.items() if not (k in ['version','updateTime'] and path.endswith('/c3fd8656cf425e9f'))}
  if isinstance(v,list):return [scrub(x,path+'/'+str(i)) for i,x in enumerate(v)]
  return v
 assert scrub(old_desc)==scrub(new_desc),('Descriptor design data changed',rel)
 descriptor_metadata_changes.append(dict(file=rel,allowed_fields=['PCB document version','PCB document updateTime']))
def groups(ls):
 d={}
 for p in ls:d.setdefault((p['net'],p['layer']),[]).append(LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,quad_segs=32))
 return {k:unary_union(v) for k,v in d.items()}
removed={p['id'] for p in plan['remove_lines']};expected=groups([p for p in lines(original) if p['id'] not in removed]+plan['lines']);actual=groups(cap['lines'])
assert set(expected)==set(actual)
deviation=max(expected[k].hausdorff_distance(actual[k]) for k in actual);assert deviation<1e-5,deviation
vremoved={p['id'] for p in plan['remove_vias']};ev=[p for p in vias(original) if p['id'] not in vremoved]+plan['vias']
assert len(ev)==len(cap['vias'])==558
for v in ev:
 match=[p for p in cap['vias'] if p['net']==v['net'] and abs(p['diameter']-v['diameter'])<.001 and abs(p['hole']-v['hole'])<.001 and math.dist((p['x'],p['y']),(v['x'],v['y']))*.0254<1e-5];assert len(match)==1,v
affected={'INV2','VIS_DC','3V3_PERIPH','GND'}
for k,p in original.items():
 if k[0] in ['LINE','VIA'] and p.get('netName') not in affected:assert final[k]==p,('Other copper changed',k)
proof={net:connected([p for p in cap['pads'] if p['net']==net],[p for p in cap['lines'] if p['net']==net],[p for p in cap['vias'] if p['net']==net]) for net in ['INV2','VIS_DC','3V3_PERIPH','BUS_SCK','INPUT_LOAD_N','PRESET1','3V3_IO','5V_PERIPH']}
assert all(v['complete'] for k,v in proof.items() if k!='VIS_DC') and proof['VIS_DC']['pad_islands']==2
print('COPPER_RECONCILED',deviation,flush=True)
planes=poured_planes(final);oldplanes=poured_planes(original);groundrefs=[]
for v in cap['vias']:
 if v['net']!='GND':continue
 q=Point(v['x']*.0254,v['y']*.0254);ring=q.buffer(v['diameter']*.0254/2,quad_segs=64).difference(q.buffer(v['hole']*.0254/2,quad_segs=64));areas={str(l):ring.intersection(planes[l]).area for l in [15,2]}
 if min(areas.values())>=.15:groundrefs.append({**v,'contact_mm2':areas})
newg=next(v for v in plan['vias'] if v['net']=='GND');newcontact=next(v for v in groundrefs if math.dist((v['x'],v['y']),(newg['x'],newg['y']))*.0254<1e-5)
returns=[]
for v in plan['vias']:
 if v['net']=='GND':continue
 nearest=min(groundrefs,key=lambda z:math.dist((v['x'],v['y']),(z['x'],z['y'])));dist=math.dist((v['x'],v['y']),(nearest['x'],nearest['y']))*.0254
 returns.append(dict(net=v['net'],xy_mm=[v['x']*.0254,v['y']*.0254],nearest_ground_xy_mm=[nearest['x']*.0254,nearest['y']*.0254],distance_mm=dist,within_project_1p5mm_goal=dist<=1.5))
excluded=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(1) for v in cap['vias'] if v['net']=='INV2']);projection=[]
for layer,ref in [(1,15),(16,2)]:
 traces=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(excluded) for p in cap['lines'] if p['net']=='INV2' and p['layer']==layer]
 length=sum(q.length for q in traces);covered=sum(q.intersection(planes[ref]).length for q in traces);projection.append(dict(layer=layer,reference=ref,length_mm=length,covered_mm=covered,gap_mm=length-covered));assert length-covered<1e-5,(layer,length,covered)
protected=lambda net:bool(net.startswith('I2S_') or re.fullmatch(r'RC[0-5]',net) or re.match(r'L[0-5]_',net))
sens=[]
for net in sorted({p['net'] for p in cap['lines'] if p['layer']==2 and protected(p['net'])}):
 mask=unary_union([Point(v['x']*.0254,v['y']*.0254).buffer(1,quad_segs=64) for v in cap['vias'] if v['net']==net]+[actual_pad(p).buffer(.5) for p in cap['pads'] if p['net']==net and p['layer']==12])
 traces=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).difference(mask) for p in cap['lines'] if p['net']==net and p['layer']==2]
 length=sum(q.length for q in traces);oldcov=sum(q.intersection(oldplanes[16]).length for q in traces);cov=sum(q.intersection(planes[16]).length for q in traces)
 sens.append(dict(net=net,length_mm=length,before_covered_mm=oldcov,after_covered_mm=cov,delta_mm=cov-oldcov))
 assert cov>=oldcov-1e-5,(net,oldcov,cov)
print('REFERENCE_REVIEW_PASS',len(sens),flush=True)
stable=rd(R/'ACTIVE-ROUTING-CANDIDATE.json');assert all(sha(Path(stable['project'])/p)==h for p,h in stable['files'].items())
assert all(sha(Path(n.info['source_project'])/p)==h for p,h in n.info['source_files'].items())
archive=O/'native-inv2-repair-WORK-IN-PROGRESS.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for p in n.PROJECT.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(n.PROJECT))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None;assert hashlib.sha256(z.read('pcb/PCB1.epcb2')).hexdigest()==sha(pcb)
remaining=[dict(net=v['name'],open_objects=len(v['list'])) for c in drc for v in c.get('list',[])]
with (O/'remaining-networks.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=['net','open_objects']);w.writeheader();w.writerows(remaining)
result=dict(updated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),project=str(n.PROJECT),session=n.SESSION,pcb_sha256=sha(pcb),source_pcb_sha256=before['source_pcb_sha256'],native_drc=dict(clearance=0,physical=0,connection=57),remaining_nets=len(remaining),components=230,pads=len(cap['pads']),vias=len(cap['vias']),native_lines=len(cap['lines']),components_rules_stackup_outline_nets_unchanged=True,other_net_copper_unchanged=True,non_PCB_design_files_unchanged=True,descriptor_metadata_changes=descriptor_metadata_changes,source_checkpoint_and_stable_R15_unchanged=True,declared_actual_copper_max_deviation_mm=deviation,continuity=proof,new_ground_contact=newcontact,actual_reference_returns=returns,inv2_reference_projection=projection,sensitive_bottom_reference_projection=sens,reference_distance_goal_not_si_signoff=True,physically_tested=False,archive=str(archive),archive_sha256=sha(archive),manufacturing_release=False)
write(O/'checkpoint-review.json',result)
state.update(phase='saved_reopened_copper_and_actual_reference_verified',session=n.SESSION,checkpoint_review=str(O/'checkpoint-review.json'));write(O/'native-state.json',state)
print('ARCHIVED_VERIFIED',result['pcb_sha256'],len(remaining),'nets',flush=True)
