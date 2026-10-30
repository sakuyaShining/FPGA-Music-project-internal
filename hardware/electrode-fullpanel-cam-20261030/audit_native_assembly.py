from pathlib import Path
import json,csv,re,hashlib,sys,math,collections
D=Path(__file__).resolve().parent
R=D
sys.path.insert(0,str(D/'verification/support'))
from native_documents import documents
Q=D/'Electrode84-450-CANDIDATE/pcb/Electrode84-450.epcb2'
b=next(d for d in documents(Q) if d['head']['docType']=='PCB')
attrs=collections.defaultdict(dict)
for h,v in b['records']:
 if h['type']=='ATTR':attrs[v['parentId']][v['key']]=v['value']
components={attrs[h['id']]['Designator']:(v,attrs[h['id']]) for h,v in b['records'] if h['type']=='COMPONENT'}
names={f'JB{i}' for i in range(6)};assert set(components)==names
bom=list(csv.DictReader((D/'Electrode84-NATIVE-BOM.csv').open(encoding='utf-16'),delimiter='\t'))
assert len(bom)==1 and int(bom[0]['Quantity'])==6 and set(bom[0]['Designator'].split(','))==names
assert bom[0]['Manufacturer Part']=='PZ254V-11-16P' and bom[0]['Supplier Part']=='C22465876'
cpl=list(csv.DictReader((D/'Electrode84-NATIVE-CPL.csv').open(encoding='utf-16'),delimiter='\t'))
assert len(cpl)==6 and {r['Designator'] for r in cpl}==names
for r in cpl:
 v,a=components[r['Designator']]
 assert r['Layer']=='B' and r['SMD']=='No' and int(r['Pins'])==16 and v['layerId']==2
 assert abs(float(r['Mid X'].removesuffix('mm'))-v['x']*.0254)<.00002
 assert abs(float(r['Mid Y'].removesuffix('mm'))-v['y']*.0254)<.00002
 assert abs(float(r['Rotation'])-v['angle'])<1e-6
ipc=(D/'Electrode84-NATIVE-IPC356.ipc').read_text();lines=ipc.splitlines()
counts=collections.Counter(l[:3] for l in lines)
assert counts['317']==198 and counts['367']==6
expected_nets={f'E{i:03d}' for i in range(84)}|{f'GND_B{i}' for i in range(6)}
ipc_nets={l[3:17].strip() for l in lines if l.startswith('317')}
assert ipc_nets==expected_nets,(ipc_nets-expected_nets,expected_nets-ipc_nets)
# Compare every exported header pin/net and coordinate with the native footprint transformation.
lib={d['head']['uuid']:d for d in documents(Q)};padnets={}
for h,v in b['records']:
 if h['type']=='PAD_NET':_,cid,num,padid=json.loads(h['id']);padnets[cid,padid]=v['padNet']
seen=set()
for l in lines:
 if not l.startswith('317') or not l[20:25].strip().startswith('JB'):continue
 ref=l[20:25].strip();pin=l[26:31].strip().removeprefix('-');net=l[3:17].strip()
 m=re.search(r'X\s*(-?\d+)Y\s*(-?\d+)',l);assert m,l
 v,a=components[ref];cid=next(h['id'] for h,w in b['records'] if h['type']=='COMPONENT' and attrs[h['id']]['Designator']==ref)
 pads=[(h,p) for h,p in lib[a['Footprint']]['records'] if h['type']=='PAD' and p['num']==pin];assert len(pads)==1
 h,p=pads[0];theta=math.radians(v['angle']);x=(v['x']+p['centerX']*math.cos(theta)-p['centerY']*math.sin(theta))*.0254;y=(v['y']+p['centerX']*math.sin(theta)+p['centerY']*math.cos(theta))*.0254
 assert net==padnets[cid,h['id']]
 assert abs(int(m[1])/1000-x)<.0011 and abs(int(m[2])/1000-y)<.0011
 assert (ref,pin) not in seen;seen.add((ref,pin))
assert len(seen)==96,len(seen)
report={'schema':1,'status':'PASS_FULL84_NATIVE_ASSEMBLY_EXPORTS','source_sha256':hashlib.sha256(Q.read_bytes()).hexdigest(),'BOM_quantity':6,'BOM_SKU':'C22465876','CPL_bottom_TH_headers':6,'IPC_PTH_records':counts['317'],'IPC_NPTH_records':counts['367'],'IPC_header_pin_net_coordinate_matches':len(seen),'IPC_net_set':len(ipc_nets),'manufacturing_release':False,'pin1_mating_harness_physical_check':'PENDING'}
(D/'FULL84-NATIVE-ASSEMBLY-AUDIT.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps(report))
