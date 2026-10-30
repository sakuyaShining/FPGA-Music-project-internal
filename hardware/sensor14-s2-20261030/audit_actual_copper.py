from pathlib import Path
import sys,json,hashlib
D=Path(__file__).resolve().parent;Q=D/'Sensor14Bank-S2-CANDIDATE/pcb/PCB2.epcb2'
sys.path.insert(0,str(D/'verification/support'))
import sensor_geometry as geo
from gerber_geometry import gerber_regions as gerber
from shapely.affinity import scale
from shapely.strtree import STRtree
geo.Q=Q;_,b=geo.base.load(Q);obs=geo.objects(b)
results={};failures=[]
for layer,suffix in [(1,'TopLayer.GTL'),(2,'BottomLayer.GBL'),(15,'InnerLayer1.G1'),(16,'InnerLayer2.G2')]:
 actual=gerber(D/'gerber-active-rules'/('Gerber_'+suffix));parts=list(actual.geoms) if hasattr(actual,'geoms') else [actual]
 source=[(o['net'] or 'EXPLICIT_NC:'+o['id'],scale(o['g'],.0254,.0254,origin=(0,0))) for o in obs if o['layer']==layer]
 tree=STRtree([v[1] for v in source]);labelled=[]
 for piece in parts:
  labels={source[int(i)][0] for i in tree.query(piece) if piece.intersection(source[int(i)][1]).area>1e-6}
  if len(labels)!=1:failures.append({'layer':layer,'issue':'ACTUAL_COPPER_LABEL_COUNT','labels':sorted(labels),'area_mm2':piece.area})
  labelled.append((labels,piece))
 gaps=[]
 for i,(labels,g) in enumerate(labelled):
  for other,p in labelled[i+1:]:
   if labels==other:continue
   distance=g.distance(p);gaps.append((distance,sorted(labels),sorted(other)))
   if distance+1e-7<.1651:failures.append({'layer':layer,'issue':'ACTUAL_DIFFERENT_NET_CLEARANCE','gap_mm':distance,'nets':[sorted(labels),sorted(other)]})
 minpair=min(gaps)
 # Net continuity across layers is checked independently using actual source/pour via contacts.
 results[layer]={'actual_copper_components':len(parts),'every_component_one_source_net':all(len(v[0])==1 for v in labelled),'minimum_actual_different_net_clearance_mm':minpair[0],'minimum_pair':minpair[1:]}
report={'schema':1,'source_sha256':hashlib.sha256(Q.read_bytes()).hexdigest(),'Gerber_sha256':hashlib.sha256((D/'Sensor14Bank-S2-Gerber-ACTIVE-RULES-CANDIDATE.zip').read_bytes()).hexdigest(),'retained_gate_mm':.1651,'numerical_epsilon_mm':1e-7,'layers':results,'failures':failures,'status':'PASS_ACTUAL_COPPER_NET_SEPARATION' if not failures else 'FAIL_ACTUAL_COPPER_NET_SEPARATION','manufacturing_release':False}
(D/'S2-ACTUAL-COPPER-NETS.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
print(json.dumps(report,ensure_ascii=True))
