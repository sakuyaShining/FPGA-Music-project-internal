from pathlib import Path
import sys,json,hashlib,math,csv,re,io,shutil
D=Path(__file__).resolve().parent;E=D/'verification/reference';S=E/'sensor14-final-20261029/Sensor14Bank-FINAL-REVIEW';Q=D/'Sensor14Bank-S2-CANDIDATE/pcb/PCB2.epcb2';G=D/'gerber-active-rules'
sys.path.insert(0,str(D/'verification/support'))
import sensor_geometry as geo
import gerber_geometry as gerber
from gerber_reader import gerber as read_mask
geo.Q=Q
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,v):p.write_bytes((json.dumps(v,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
docs,b=geo.base.load(Q);old_docs,old=geo.base.load(S/'pcb/PCB2.epcb2')
byuuid={d['head']['uuid']:d for d in old_docs}
for d in docs:
 if d['head']['docType']=='PCB':continue
 a={ (h['type'],h.get('id')):v for h,v in d['records'] if h['type']!='DOCHEAD'}
 z={ (h['type'],h.get('id')):v for h,v in byuuid[d['head']['uuid']]['records'] if h['type']!='DOCHEAD'}
 assert a==z,'Embedded library changed: '+d['head']['uuid']
libs={d['head']['uuid']:d for d in docs};attrs={}
for h,v in b['records']:
 if h['type']=='ATTR':attrs.setdefault(v['parentId'],{})[v['key']]=v['value']
components={attrs[h['id']]['Designator']:v for h,v in b['records'] if h['type']=='COMPONENT'}
assert len(components)==28
expected=[]
for h,c in b['records']:
 if h['type']=='VIA':expected.append((c['centerX']*.0254,c['centerY']*.0254,c['holeDiameter']*.0254));continue
 if h['type']!='COMPONENT':continue
 theta=math.radians(c['angle']);co,si=math.cos(theta),math.sin(theta)
 for hh,p in libs[attrs[h['id']]['Footprint']]['records']:
  if hh['type']!='PAD' or not p.get('hole') or p['hole']['width']<=0:continue
  assert p['hole']['holeType']=='ROUND';pa=math.radians(p['padAngle']);ox=p.get('padOffsetX',0) or 0;oy=p.get('padOffsetY',0) or 0;x=p['centerX']+ox*math.cos(pa)-oy*math.sin(pa);y=p['centerY']+ox*math.sin(pa)+oy*math.cos(pa)
  expected.append(((c['x']+x*co-y*si)*.0254,(c['y']+x*si+y*co)*.0254,p['hole']['width']*.0254))
txt=(G/'Drill_PTH_Through.DRL').read_text();tools={int(n):float(d) for n,d in re.findall(r'^T(\d+)C([\d.]+)$',txt,re.M)};actual=[];tool=None
for line in txt.splitlines():
 t=re.fullmatch(r'T(\d+)',line)
 if t:tool=int(t[1]);continue
 m=re.fullmatch(r'X(-?[\d.]+)Y(-?[\d.]+)',line)
 if m:actual.append((float(m[1]),float(m[2]),tools[tool]))
assert len(expected)==len(actual)==83
remain=actual.copy();maxerror=0
for a in expected:
 q=min(remain,key=lambda x:math.dist(a,x));err=math.dist(a,q);assert err<.00003,(a,q,err);maxerror=max(maxerror,err);remain.remove(q)
def nativecsv(path):return list(csv.DictReader(io.StringIO(path.read_bytes().decode('utf-16')),delimiter='\t'))
cpl=nativecsv(D/'Sensor14Bank-S2-CPL-NATIVE.csv');assert len(cpl)==28
assert {r['Designator'] for r in cpl}==set(components)
smt=[]
for row in cpl:
 c=components[row['Designator']]
 assert abs(float(row['Ref X'].removesuffix('mm'))-c['x']*.0254)<.00001
 assert abs(float(row['Ref Y'].removesuffix('mm'))-c['y']*.0254)<.00001
 assert float(row['Rotation'])==c['angle'] and row['Layer']=='T'
 if row['SMD']=='Yes':smt.append({'Designator':row['Designator'],'Mid X':row['Mid X'],'Mid Y':row['Mid Y'],'Layer':'Top','Rotation':row['Rotation']})
assert len(smt)==26
with (D/'Sensor14Bank-S2-CPL-SMT-FACTORY.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(smt[0]));w.writeheader();w.writerows(smt)
oldbom=list(csv.DictReader((E/'sensor14-final-20261029/Sensor14Bank-BOM-VERIFIED.csv').open(encoding='utf-8-sig')));expectedbom={r['Designator']:(r['MPN'],r['LCSC']) for r in oldbom}
bom=nativecsv(D/'Sensor14Bank-S2-BOM-NATIVE.csv');actualbom={}
factory=[]
for r in bom:
 refs=r['Designator'].split(',');assert len(refs)==int(r['Quantity'])
 for ref in refs:assert ref not in actualbom;actualbom[ref]=(r['Manufacturer Part'],r['Supplier Part'])
 factory.append({'Comment':r['Manufacturer Part'],'Designator':r['Designator'],'Footprint':r['Footprint'],'LCSC Part #':r['Supplier Part']})
assert actualbom==expectedbom
with (D/'Sensor14Bank-S2-BOM-FACTORY.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(factory[0]));w.writeheader();w.writerows(factory)
mask={}
def commands(path):return '\n'.join(line for line in path.read_text().splitlines() if not line.startswith('G04'))
for suffix in ['TopSolderMaskLayer.GTS','BottomSolderMaskLayer.GBS']:
 fresh=read_mask(G/('Gerber_'+suffix));previous=read_mask(E/'sensor14-final-20261029/gerber-inspection'/('Gerber_'+suffix));difference=fresh.symmetric_difference(previous).area
 assert difference<1e-8,('Mask actual geometry differs',suffix,difference)
 mask[suffix]={'actual_geometry_difference_to_S1_mm2':difference,'aperture_macro':'Exact RoundRect macro verified by independent parser; unused apertures and D-number reindexing do not imply copper/mask geometry changes'}
outline=read_mask(G/'Gerber_BoardOutlineLayer.GKO');oldoutline=read_mask(E/'sensor14-final-20261029/gerber-inspection/Gerber_BoardOutlineLayer.GKO')
assert outline.symmetric_difference(oldoutline).area<1e-8 and outline.hausdorff_distance(oldoutline)<1e-8
schematics=[]
for p in S.rglob('*.esch2'):
 target=Q.parents[1]/p.relative_to(S);assert sha(target)==sha(p);schematics.append({'path':p.relative_to(S).as_posix(),'sha256':sha(p)})
assert schematics
report={'schema':1,'status':'PASS_DECLARED_SOURCE_MANUFACTURING_CORRESPONDENCE_CHECKS','source_sha256':sha(Q),'Gerber_sha256':sha(D/'Sensor14Bank-S2-Gerber-ACTIVE-RULES-CANDIDATE.zip'),'native_DRC_reopen_result':'10-reopen-active-rules-drc.result.json','embedded_library_metadata_unchanged':True,'schematic_unchanged':schematics,'all83_PTH_positions_and_diameters_match':True,'max_PTH_position_diameter_error_mm':maxerror,'native_CPL_placements_checked':28,'SMT_components':26,'TH_components':2,'native_BOM_all28_MPN_and_LCSC_match_verified_source':True,'mask_geometry':mask,'board_outline_actual_geometry_unchanged_55x45mm':True,'original_84_mapping_and_all_pin_nets':'Existing COMPONENT/ATTR/PAD_NET/LINE/VIA unchanged by independent audit; both six-board control harness and84-row electrode mapping remain applicable','physical_function_noise_current_and_factory_DFM':'NOT_ACCEPTED_BY_THIS_GEOMETRY_CHECK','manufacturing_release':False}
put(D/'S2-MANUFACTURING-CORRESPONDENCE.json',report)
print(json.dumps(report,ensure_ascii=True))
