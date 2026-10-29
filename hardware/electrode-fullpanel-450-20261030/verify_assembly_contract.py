from pathlib import Path
import json,csv,hashlib,xml.etree.ElementTree as ET
D=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8'))
plan=read(D/'FULL-PANEL-SOURCE-PLAN.json');g=read(D/'assembly/MECHANICAL-CANDIDATE.json')
with (D/'assembly/HARNESS-96-PINS.csv').open(encoding='utf-8',newline='') as f:h=list(csv.DictReader(f))
with (D/'ELECTRODE-HARNESS-84-VERIFIED.csv').open(encoding='utf-8-sig',newline='') as f:m=list(csv.DictReader(f))
assert len(h)==96 and len(m)==84
byraw={int(v['raw_index']):v for v in m};assert set(byraw)==set(range(84))
connections=set()
for v in h:
 b,p=int(v['bank']),int(v['pin']);assert v['end_A']==f'EP84.JB{b}.{p}' and v['end_B']==f'SensorS2.B{b}.J1.{p}'
 assert (b,p) not in connections;connections.add((b,p))
 if p>=15:assert v['function']=='GND' and v['raw_index']==''
 else:
  r=byraw[int(v['raw_index'])];assert int(r['bank'])==b and int(r['pin'])==p and int(r['channel'])==int(v['channel'])
  assert int(r['raw_index'])==int(r['channel'])*6+b
assert connections=={(b,p) for b in range(6) for p in range(1,17)}
for e in plan['electrode_endpoints']:
 r=byraw[e['raw_index']];assert e['bank']==int(r['bank']) and e['channel']==int(r['channel']) and e['header_pin']==int(r['pin'])
assert len([e for e in plan['electrode_endpoints'] if e['kind']=='pitch'])==75
assert len([e for e in plan['electrode_endpoints'] if e['kind']=='octave'])==5
assert len([e for e in plan['electrode_endpoints'] if e['kind']=='spare'])==4
assert {(e['bank'],e['channel']) for e in plan['electrode_endpoints'] if e['pitch']=='C5'}=={(0,12),(1,12),(2,12)}
def overlap(a,b):return min(a[2],b[2])>max(a[0],b[0]) and min(a[3],b[3])>max(a[1],b[1])
for i,a in enumerate(g['sensors']):
 for b in g['sensors'][i+1:]:assert not overlap(a['outline_global_mm'],b['outline_global_mm'])
 for x,y in g['mount_centers_global_mm']:
  a0,a1,a2,a3=a['outline_global_mm'];assert not (a0-3.5<x<a2+3.5 and a1-3.5<y<a3+3.5)
for rect in [g['left_panel_rect_mm'],g['screen_reserved_rect_mm'],g['control88_rect_candidate_mm']]:assert 0<=rect[0]<rect[2]<=450 and 0<=rect[1]<rect[3]<=190
assert not overlap(g['left_panel_rect_mm'],g['screen_reserved_rect_mm'])
svg=ET.parse(D/'assembly/overlay-cut-candidate-1to1.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
assert svg.attrib['width']=='236mm' and svg.attrib['height']=='156mm'
assert len(svg.findall('.//s:rect',ns))==1 and len(svg.findall('.//s:circle',ns))==6
holes={(float(c.attrib['cx']),156-float(c.attrib['cy'])) for c in svg.findall('.//s:circle',ns)}
assert holes=={tuple(h['xy_mm']) for h in plan['mounting_holes']}
q=D/'candidate/Electrode84-450-CANDIDATE/pcb/Electrode84-450.epcb2';assert hashlib.sha256(q.read_bytes()).hexdigest()==read(D/'CHECKPOINT.json')['source_sha256']
report={'schema':1,'status':'PASS_DECLARED_MAPPING_OVERLAY_AND_NOMINAL_ENVELOPES','signals':84,'ground_conductors':12,'all96_pin_connections_1to1':True,'C5_mapping_preserved':True,'overlay_outer_mm':[236,156],'overlay_holes':6,'sensor_nominal_outline_overlap':False,'nominal_screen_gap_mm':10,'actual_screen_cover_connector_depth_and_cutout_verified':False,'prewired_harness_SKU_length_and_fit_confirmed':False,'physical_touch_verified':False,'manufacturing_release':False}
(D/'ASSEMBLY-CONTRACT-AUDIT.json').write_bytes((json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report))
