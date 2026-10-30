from pathlib import Path
import sys,json,collections,hashlib
D=Path(__file__).resolve().parent
sys.path.insert(0,str(D/'verification/support'))
from native_documents import documents
from shapely.geometry import Point,LineString
from shapely.ops import unary_union
def copper(p):
 b=next(d for d in documents(p) if d['head']['docType']=='PCB');groups=collections.defaultdict(list);counts=collections.Counter()
 for h,v in b['records']:
  if h['type']=='LINE':
   counts['LINE']+=1;groups[v['netName'],v['layerId']].append(LineString([(v['startX']*.0254,v['startY']*.0254),(v['endX']*.0254,v['endY']*.0254)]).buffer(v['width']*.0254/2,quad_segs=128))
  elif h['type']=='VIA':
   counts['VIA']+=1
   for layer in [1,2]:groups[v['netName'],layer].append(Point(v['centerX']*.0254,v['centerY']*.0254).buffer(v['viaDiameter']*.0254/2,quad_segs=128))
 return {k:unary_union(gs) for k,gs in groups.items()},dict(counts)
a=D/'verification/reference/router-imported.epcb2';b=D/'candidate/Electrode84-450-CANDIDATE/pcb/Electrode84-450.epcb2';aa,ac=copper(a);bb,bc=copper(b);assert aa.keys()==bb.keys()
differences=[];maxgap=0
for k,g in aa.items():
 h=bb[k];gap=g.hausdorff_distance(h);maxgap=max(maxgap,gap)
 if not g.difference(h.buffer(.0001)).is_empty or not h.difference(g.buffer(.0001)).is_empty:differences.append({'net_layer':k,'hausdorff_mm':gap})
assert not differences,differences
report={'schema':1,'status':'PASS_NATIVE_API_SAVED_ROUTING_MATCHES_IMPORTED_SESSION','native_saved_source_sha256':hashlib.sha256(b.read_bytes()).hexdigest(),'imported_source_sha256':hashlib.sha256(a.read_bytes()).hexdigest(),'imported_counts':ac,'native_counts':bc,'native_line_coalescing_note':'Native editor coalesced six redundant/collinear line records. All route and via copper unions match within0.1um. No route missing.','comparison_tolerance_mm':.0001,'maximum_hausdorff_mm':maxgap,'different_net_clearance_gate_mm':.25,'clearance_tolerance_separate':True,'failures':differences,'native_DRC':'NOT_RUN_CLIENT_DISCONNECTED','manufacturing_release':False}
(D/'NATIVE-SAVED-ROUTING-CORRESPONDENCE.json').write_bytes((json.dumps(report,indent=2)+'\n').encode());print(json.dumps(report))
