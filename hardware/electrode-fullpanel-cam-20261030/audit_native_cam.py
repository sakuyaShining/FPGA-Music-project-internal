from pathlib import Path
import sys,runpy,json,hashlib,re,collections
D=Path(__file__).resolve().parent
R=D

sys.path.insert(0,str(D/'verification/support'))
from gerber_reader import gerber
from shapely.geometry import Point,box
from shapely.ops import unary_union
from shapely.strtree import STRtree
Q=D/'Electrode84-450-CANDIDATE/pcb/Electrode84-450.epcb2'
sys.argv=['audit_full_panel.py',str(Q),str(D/'FULL84-REOPENED-SOURCE-AUDIT.json')]
s=runpy.run_path(str(D/'audit_full_panel.py'))
assert s['report']['status']=='PASS_FULL84_SOURCE_ELECTRICAL_GEOMETRY'
G=D/'gerber-native-verified-input'
fail=[];layers={};actual_parts=[]
npth_void=unary_union(s['holes'])
def require(ok,issue,**detail):
 if not ok:fail.append(dict(issue=issue,**detail))
for layer,name in [(1,'Gerber_TopLayer.GTL'),(2,'Gerber_BottomLayer.GBL')]:
 raw=gerber(G/name)
 # The editor clamps NPTH pad artwork to 1um. These six source-defined
 # flashes are entirely removed by the six 3.2mm non-plated drills.
 # Model the raw Gerber explicitly before checking the finished board.
 dummy_lands=unary_union([h.centroid.buffer(.0005,quad_segs=512) for h in s['holes']])
 removed=raw.intersection(npth_void)
 require(removed.symmetric_difference(dummy_lands).area<1e-12,'NPTH_RAW_ARTWORK_NOT_EXPECTED_1UM_LANDS',layer=layer)
 a=raw.difference(npth_void);parts=list(a.geoms) if hasattr(a,'geoms') else [a]
 source=[o for o in s['obs'] if o['layer']==layer]
 tree=STRtree([o['g'] for o in source]);labelled=[]
 for part in parts:
  labels={source[int(i)]['net'] for i in tree.query(part) if part.intersection(source[int(i)]['g']).area>1e-6}
  require(len(labels)==1,'ACTUAL_COMPONENT_NET_LABEL',layer=layer,labels=sorted(labels),area=part.area)
  labelled.append((labels,part));actual_parts.append((layer,labels,part))
 actual_tree=STRtree(parts)
 gaps=[(g.distance(labelled[int(j)][1]),sorted(n),sorted(labelled[int(j)][0])) for i,(n,g) in enumerate(labelled) for j in actual_tree.query(g.buffer(.8)) if int(j)>i and n!=labelled[int(j)][0]]
 assert gaps and min(gaps)[0]<.8
 print('Parsed and labelled layer',layer,flush=True)
 smallest=min(gaps)
 require(smallest[0]+1e-7>=.25,'ACTUAL_COPPER_CLEARANCE',layer=layer,gap_mm=smallest[0])
 # Two directional coverage uses 5um only for polygon discretization correspondence.
 src=unary_union([o['g'] for o in source]);lost=src.difference(a.buffer(.005)).area;extra=a.difference(src.buffer(.005)).area
 require(lost<1e-6 and extra<1e-6,'COPPER_SOURCE_EXPORT_MISMATCH',layer=layer,lost_mm2=lost,extra_mm2=extra)
 layers[layer]={'components':len(parts),'minimum_different_net_gap_mm':smallest[0],'minimum_pair':smallest[1:],'source_missing_area_beyond_5um_mm2':lost,'extra_area_beyond_5um_mm2':extra,'source_defined_1um_NPTH_lands_removed_by_drill':6,'removed_raw_copper_area_mm2':removed.area}
parent=list(range(len(actual_parts)))
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
# Join only physically plated source contacts that match actual copper on both faces.
contacts={}
for o in s['obs']:
 if o['kind'] in ['PAD','VIA']:contacts.setdefault(o['id'],o)
for o in contacts.values():
 hits=[i for i,(layer,n,g) in enumerate(actual_parts) if n=={o['net']} and g.intersection(o['g']).area>1e-5]
 require({actual_parts[i][0] for i in hits}=={1,2},'PTH_COPPER_CONTACT_MISSING',id=o['id'])
 for i in hits[1:]:parent[root(i)]=root(hits[0])
netroots=collections.defaultdict(set)
for i,(_,n,g) in enumerate(actual_parts):
 for net in n:netroots[net].add(root(i))
unconnected={n:len(v) for n,v in netroots.items() if len(v)!=1}
require(len(netroots)==90 and not unconnected,'ACTUAL_NET_CONTINUITY',nets=len(netroots),unconnected=unconnected)
mask={1:gerber(G/'Gerber_TopSolderMaskLayer.GTS'),2:gerber(G/'Gerber_BottomSolderMaskLayer.GBS')}
maskresults={}
for layer,m in mask.items():
 opened=[net for net,g in s['fills'].items() if m.intersection(g).area>1e-8] if layer==1 else []
 vias=[o['id'] for o in s['obs'] if o['kind']=='VIA' and o['layer']==layer and m.intersection(o['g']).area>1e-8]
 pads=[o for o in s['obs'] if o['kind']=='PAD' and o['layer']==layer]
 closed=[o['ref'] for o in pads if o['g'].difference(m.buffer(.001)).area>1e-6]
 require(not opened,'ACTIVE_ELECTRODE_MASK_OPENING',nets=opened)
 require(not vias,'VIAS_NOT_TENTED',layer=layer,ids=vias)
 require(len(pads)==96 and not closed,'HEADER_MASK_NOT_OPEN',layer=layer,pads=closed)
 expected=unary_union([o['g'].buffer(.051) for o in pads]+s['holes'])
 extra=m.difference(expected).area
 require(extra<1e-6,'UNEXPECTED_MASK_OPENINGS',layer=layer,area_mm2=extra)
 maskresults[layer]={'active_electrode_openings':opened,'untented_vias':vias,'header_pad_openings':len(pads)-len(closed),'unexplained_opening_area_mm2':extra}
def drill(path):
 text=path.read_text();assert 'METRIC' in text
 tools={int(a):float(b) for a,b in re.findall(r'^T(\d+)C([0-9.]+)',text,re.M)}
 result=[];tool=None
 for line in text.splitlines():
  m=re.fullmatch(r'T(\d+)',line)
  if m:tool=int(m[1])
  m=re.fullmatch(r'X(-?[0-9.]+)Y(-?[0-9.]+)',line)
  if m:result.append((float(m[1]),float(m[2]),tools[tool]))
 return result
pth=drill(G/'Drill_PTH_Through.DRL');npth=drill(G/'Drill_NPTH_Through.DRL');via=drill(G/'Drill_PTH_Through_Via.DRL')
expected_pth=[];expected_npth=[]
for h,v in s['b']['records']:
 if h['type']=='VIA':expected_pth.append((v['centerX']*.0254,v['centerY']*.0254,v['holeDiameter']*.0254))
 elif h['type']=='PAD':expected_npth.append((v['centerX']*.0254,v['centerY']*.0254,v['hole']['width']*.0254))
for h,v in s['b']['records']:
 if h['type']!='COMPONENT':continue
 attr=s['at'][h['id']];ref=attr['Designator']
 for hh,p in s['libs'][attr['Footprint']]['records']:
  if hh['type']=='PAD':expected_pth.append((*s['headers'][ref][int(p['num'])]['xy_mm'],p['hole']['width']*.0254))
def match_all(actual,expected,label):
 unmatched=list(actual)
 for exp in expected:
  # Generator internal mil rounding produces up to 0.000081mm coordinate
  # shifts. A 0.0001mm correspondence bound remains below the separately
  # declared 0.005mm outline/copper tolerance and never relaxes .25mm spacing.
  matches=[i for i,a in enumerate(unmatched) if max(abs(x-y) for x,y in zip(a,exp))<.0001]
  require(len(matches)==1,'DRILL_SOURCE_MISMATCH',kind=label,expected=exp,matches=len(matches))
  if matches:unmatched.pop(matches[0])
 require(not unmatched,'UNEXPECTED_DRILLS',kind=label,extra=unmatched)
match_all(pth,expected_pth,'PTH');match_all(npth,expected_npth,'NPTH');match_all(via,[p for p in expected_pth if p[2]<.5],'VIA_SUBSET')
require(len(pth)==198 and len(npth)==6 and len(via)==102,'DRILL_COUNTS')
# Outline centerline extent must be exact, ignoring aperture stroke width.
outline=(G/'Gerber_BoardOutlineLayer.GKO').read_text();coords=[(float(x)/1e5,float(y)/1e5) for x,y in re.findall(r'X(-?\d+)Y(-?\d+)D0[12]',outline)]
require(bool(coords) and [min(x for x,y in coords),min(y for x,y in coords),max(x for x,y in coords),max(y for x,y in coords)]==[0,0,236,156],'OUTLINE_EXTENTS',coords=coords)
drc=json.loads((D/'05-save-close-reopen-drc.live-result.json').read_text())['result']
require(drc['saved'] is True and drc['closed'] is True and drc['violations']==[],'NATIVE_DRC_REOPEN')
report={'schema':1,'status':'PASS_FULL84_NATIVE_CAM' if not fail else 'FAIL_FULL84_NATIVE_CAM','source_sha256':hashlib.sha256(Q.read_bytes()).hexdigest(),'gerber_sha256':hashlib.sha256((D/'Electrode84-450-Gerber-NATIVE-CANDIDATE.zip').read_bytes()).hexdigest(),'native_save_close_reopen_DRC_violations':drc['violations'],'layers':layers,'actual_nets':len(netroots),'unconnected_actual_nets':unconnected,'masks':maskresults,'PTH':len(pth),'NPTH':len(npth),'via_PTH_subset':len(via),'clearance_gate_mm':.25,'geometry_correspondence_tolerance_mm':.005,'failures':fail,'manufacturing_release':False,'physical_touch_and_mechanical_fit':'NOT_VALIDATED'}
(D/'FULL84-NATIVE-CAM-AUDIT.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode())
print(json.dumps(report,ensure_ascii=True));sys.exit(bool(fail))
