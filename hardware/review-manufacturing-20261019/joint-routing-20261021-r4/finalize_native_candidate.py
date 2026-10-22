"""Audit complete native copper and archive the independent 62-open branch."""
import sys,json,hashlib,zipfile,math,collections
from pathlib import Path
from datetime import datetime,timezone
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
from shapely.geometry import LineString
from shapely.ops import unary_union
sys.path.insert(0,str(BASE));sys.path.insert(0,str(ROOT))
from candidate_native import PROJECT,info,SESSION
from resume_offline import read_native
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'));save=lambda p,o:p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf-8')
old=read_native(Path(info['source_project'])/'pcb/PCB1.epcb2');PCB=PROJECT/'pcb/PCB1.epcb2';new=read_native(PCB)
plan=read(BASE/'four-layer-mixed/plan.json');qa=read(BASE/'four-layer-mixed/independent-geometry.json');audit=read(BASE/'native-apply-audit.json');drc=read(BASE/'native-drc.json');meta=read(BASE/'native-drc-meta.json');capture=read(BASE/'native-verified-capture.json')
assert meta['source_stable'] and sha(PCB)==meta['pcb_sha256_after'];assert qa['combined_geometry_pass']
counts={c['name']:c.get('count',0) for c in drc};assert counts.get('Clearance Error',0)==0 and counts.get('Physics Error',0)==0 and counts['Connection Error']==62
selected={r['net'] for r in plan['routes']}
for kind in ['COMPONENT','ATTR','PAD','REGION','STRING','NET','PAD_NET','RULE','RULE_SELECTOR']:
 assert {i:p for (k,i),p in old.items() if k==kind}=={i:p for (k,i),p in new.items() if k==kind},kind
for kind,field in [('LINE','netName'),('VIA','netName')]:
 a={i:p for (k,i),p in old.items() if k==kind and p.get(field) not in selected};b={i:p for (k,i),p in new.items() if k==kind and p.get(field) not in selected};assert a==b,kind
lines=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in new.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]]
shape=lambda ls:unary_union([LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2,resolution=32) for p in ls])
geometry=[]
for r in plan['routes']:
 n=r['net']
 for l in [1,16,2]:
  a=shape([p for p in r['lines'] if p['layer']==l]);b=shape([p for p in lines if p['net']==n and p['layer']==l]);missing=a.difference(b.buffer(.000005));extra=b.difference(a.buffer(.000005));assert missing.is_empty and extra.is_empty,(n,l,missing.area,extra.area)
  geometry.append(dict(net=n,layer=l,equivalent=True))
 expected=sorted((round(p['x'],5),round(p['y'],5),round(p['diameter'],5),round(p['hole'],5)) for p in r['vias']);actual=sorted((round(p['centerX'],5),round(p['centerY'],5),round(p['viaDiameter'],5),round(p['holeDiameter'],5)) for (k,i),p in new.items() if k=='VIA' and p['netName']==n)
 assert len(expected)==len(actual) and all(abs(a-b)<=.000051 for ea,aa in zip(expected,actual) for a,b in zip(ea,aa)),(n,expected,actual) # Native save quantizes mil fields to 4 decimal places (<=1.3 nm).
assert not [p for p in lines if p['layer']==15],'L2 intended as ground reference only'
for k,i in old:
 if k=='POUR':assert old[k,i]==new[k,i]
assert collections.Counter(p['layerId'] for (k,i),p in new.items() if k=='POUR')=={1:1,2:1,15:1,16:1}
assert all(sha(Path(info['source_project'])/p)==h for p,h in info['source_files'].items()),'Original two-layer source changed'
for rel,h in info['source_files'].items():
 if rel.endswith('.eprj3') or rel=='pcb/PCB1.epcb2':continue
 assert sha(PROJECT/rel)==h,rel
pending=[n['name'] for c in drc if c['name']=='Connection Error' for n in c['list']];closed=sorted(set(read(ROOT/'route-checkpoint-0clear-74open-local-power-bus-r3-20261021.json')['pending_nets'])-set(pending));assert set(closed)=={'I2C_SCL','DISP_RESET_N','DISP_VIS_DC','DISP_VIS_CS_N'}
files={p.relative_to(PROJECT).as_posix():sha(p) for p in PROJECT.rglob('*') if p.is_file()};assert len(files)==19
D=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2');archive=D/'native-4L-230-0clear-62open-routing-r4-20261021-CANDIDATE.zip';assert not archive.exists()
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for p in files:z.write(PROJECT/p,p)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None and all(hashlib.sha256(z.read(p)).hexdigest()==h for p,h in files.items())
working=dict(updated_utc=datetime.now(timezone.utc).isoformat(),role='active routing alternative; manufacturing and procurement baseline remains r3 until stackup/return/sensor review',project=str(PROJECT),session=SESSION,checkpoint='joint-routing-20261021-r4/native-candidate-checkpoint.json',source_capture='joint-routing-20261021-r4/native-verified-capture.json',source_capture_sha256=sha(BASE/'native-verified-capture.json'),pcb_sha256=sha(PCB),layers=4,components=230,pads=len(capture['pads']),api_lines=len(capture['lines']),native_copper_line_records=len(lines),native_microtracks=len(lines)-len(capture['lines']),vias=len(capture['vias']),pours=4,clearance_errors=0,physical_errors=0,unconnected_errors=62,pending_nets=pending,closed_pending_nets=closed,native_zip=str(archive),native_zip_sha256=sha(archive),files=files,manufacturing_release=False,stackup_factory_qualified=False,sensor_plane_capacitance_qualified=False,i2s_return_signoff=False,original_r3_source_files_unchanged=True,original_connected_net_via_reduction=sum(r['metrics']['before_vias']-r['metrics']['after_vias'] for r in plan['routes'] if r['metrics']['before_vias']),original_connected_net_length_reduction_mm=sum(r['metrics']['before_length_mm']-r['metrics']['after_length_mm'] for r in plan['routes'] if r['metrics']['before_vias']))
save(BASE/'native-candidate-checkpoint.json',working);save(ROOT/'ACTIVE-ROUTING-CANDIDATE.json',working);save(D/'ACTIVE-ROUTING-CANDIDATE.json',working)
save(BASE/'native-geometry-reconciliation.json',dict(checks=geometry,unselected_copper_components_pads_nets_rules_unchanged=True,other_17_files_unchanged=True,archive_crc_and_19_hashes_verified=True,manufacturing_release=False))
print(json.dumps({k:v for k,v in working.items() if k!='files'},ensure_ascii=False,indent=2))
