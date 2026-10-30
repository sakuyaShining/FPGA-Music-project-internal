"""Bind every source reader to S2 and compare same-source actual native Gerber."""
from pathlib import Path
import sys,json,hashlib,zipfile,collections,math,re
D=Path(__file__).resolve().parent;E=D/'verification/reference';S=E/'sensor14-final-20261029/Sensor14Bank-FINAL-REVIEW';Q=D/'Sensor14Bank-S2-CANDIDATE/pcb/PCB2.epcb2'
sys.path.insert(0,str(D/'verification/support'))
import sensor_geometry as geo
import sensor_ground as ground
import gerber_geometry as gerber
from shapely.affinity import scale
from shapely.ops import unary_union
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
geo.Q=Q;ground.Q=Q
docs,b=geo.base.load(Q);old_docs,old=geo.base.load(S/'pcb/PCB2.epcb2')
assert b['head']['docType']=='PCB' and b['head']['uuid']=='f52674d6627fca6f'
assert sha(S/'pcb/PCB2.epcb2')=='2184d027643f52ff50a7bca4bf9c717ae805a099043d300855f3348be5b5b7e3'
oldmap={(h['type'],h.get('id')):v for h,v in old['records']};newmap={(h['type'],h.get('id')):v for h,v in b['records']}
added=sorted(str(k) for k in newmap.keys()-oldmap.keys());removed=sorted(str(k) for k in oldmap.keys()-newmap.keys());modified=[k for k in oldmap.keys()&newmap.keys() if oldmap[k]!=newmap[k]]
unallowed=[k for k in modified if k[0] not in ['POURED','DOCHEAD','CANVAS']]
assert not unallowed,unallowed
assert all(k[0]=='REGION' for k in newmap.keys()-oldmap.keys())
assert not removed
regions=[v for h,v in b['records'] if h['type']=='REGION'];assert len(regions)==22 and all(v['layerId']==2 and v['prohibitType']==['COPPER'] and v['regionType']=='PROHIBIT' for v in regions)
export_zip=D/'Sensor14Bank-S2-Gerber-ACTIVE-RULES-CANDIDATE.zip'
G=D/'gerber-active-rules'
if not G.exists():
 G.mkdir()
 with zipfile.ZipFile(export_zip) as z:
  for n in z.namelist():
   assert not n.startswith(('/','\\')) and '..' not in Path(n).parts
  z.extractall(G)
obs=geo.objects(b);planes,mains,gr=ground.ground(b)
exports={};equivalence={}
for layer,name in [(1,'TopLayer.GTL'),(2,'BottomLayer.GBL'),(15,'InnerLayer1.G1'),(16,'InnerLayer2.G2')]:
 file=G/('Gerber_'+name);text=file.read_text();assert '%FSLAX45Y45' in text and '%MOMM' in text
 actual=gerber.gerber_regions(file);exports[layer]=actual
 native=scale(unary_union(([planes[layer]] if layer in planes else [])+[o['g'] for o in obs if o['layer']==layer]),.0254,.0254,origin=(0,0))
 missing=native.difference(actual.buffer(.005)).area;extra=actual.difference(native.buffer(.005)).area
 equivalence[layer]={'missing_mm2_at_5um':missing,'extra_mm2_at_5um':extra}
 assert missing<.001 and extra<.001,(layer,equivalence[layer])
checks=[]
for layer in [2,15,16]:
 actual=exports[layer];parts=list(actual.geoms) if hasattr(actual,'geoms') else [actual];main=max(parts,key=lambda p:p.area)
 for o in obs:
  if o['layer']!=layer or not o.get('net') or o['net']=='GND':continue
  gap=scale(o['g'],.0254,.0254,origin=(0,0)).distance(main)
  checks.append({'layer':layer,'kind':o['kind'],'ref':o.get('ref',o['id']),'net':o['net'],'actual_Gerber_main_GND_clearance_mm':gap,'passes_retained_0p1651_mm':gap+1e-7>=.1651})
original=json.loads((E/'sensor14-final-20261029/retained-clearance-gate-audit.json').read_bytes());refs={v['pad'] for v in original['retained_gate_failures']}
fixed=[v for v in checks if v['layer']==2 and v['kind']=='PAD' and v['ref'] in refs];assert len(fixed)==22
failures=[v for v in checks if not v['passes_retained_0p1651_mm']]
report={'schema':1,'scope':'S2 actual native re-pour and same-source Gerber; evidence does not authorize manufacturing','source_sha256':sha(Q),'gerber_sha256':sha(export_zip),'S1_unchanged':sha(S/'pcb/PCB2.epcb2')==original['pcb_sha256'],'record_changes':{'added':added,'removed':removed,'modified':[list(k) for k in modified]},'all_existing_primitives_nets_and_rules_unchanged':True,'native_reopen_DRC':json.loads((D/'10-reopen-active-rules-drc.result.json').read_bytes()),'source_export_equivalence':equivalence,'actual_clearance_checks':checks,'original_22_min_clearance_mm':min(v['actual_Gerber_main_GND_clearance_mm'] for v in fixed),'all_bottom_inner_main_GND_min_clearance_mm':min(v['actual_Gerber_main_GND_clearance_mm'] for v in checks),'retained_clearance_failures':failures,'ground_connectivity':gr,'manufacturing_release':False}
put(D/'S2-INDEPENDENT-AUDIT.json',report)
print(json.dumps({'source_sha256':report['source_sha256'],'Gerber_sha256':report['gerber_sha256'],'record_modified':report['record_changes']['modified'],'original_22_min_mm':report['original_22_min_clearance_mm'],'overall_min_mm':report['all_bottom_inner_main_GND_min_clearance_mm'],'failures':failures[:12],'failure_count':len(failures),'native_clearance_errors':gr['full_copper_including_pours_check']['clearance_errors'],'unconnected_nets':gr['full_copper_including_pours_check']['unconnected_nets']},ensure_ascii=True))
