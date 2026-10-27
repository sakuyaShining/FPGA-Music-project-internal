from pathlib import Path
import json,sys,math,datetime,hashlib
sys.path.insert(0,r'D:\FPGA-Project\codex-tools\shapely')
from shapely.geometry import Point,LineString,box
from shapely.affinity import rotate
E=Path(__file__).parent;J=lambda f:json.loads((E/f).read_text(encoding='utf-8-sig'));a=J('sensor-fourlayer-reinforcement-reopened-DRC-current.json')['value'];pads=J('sensor-fourlayer-exact-source-pads-current.json')['pads'];h=hashlib.sha256((E/'sensor-fourlayer-native-current.epcb2').read_bytes()).hexdigest();assert h=='a7c49b416680494c72ebff390abb6064235e52158cabb86b620a1b7468a2ec3b';by={(p['ref'],p['pin']):p for p in pads};oldids={x['primitiveId'] for x in J('sensor-today-PCB-sync-preflight-current.json')['value']['lines']}
delete=['9fcecc4174c2ec59','4a92b37d9e8a57bd','6349ce55facdfd45','3f62c54ba9582af7','2760db3397b30710','965f0af07ba337f9'];assert not set(delete)&oldids;actual={x['primitiveId']:x for x in a['lines']};assert all(x in actual for x in delete)
p=by[('J1','14')];t=by[('D4','9')];src=by[('U1','14')];routes=[{'net':'L0_E13','layer':2,'points':[[p['x_mm'],p['y_mm']],[7.0,7.4],[10.4,7.4],[10.5,10.35]],'width_mm':.1651,'role':'BottomE13avoidsneighborJ1.13antipad; throughheaderstart'}, {'net':'L0_E13','layer':1,'points':[[10.5,10.35],[10.2,10.59987272]],'width_mm':.1651,'role':'TopjoinexistingE13inputnetbefore1kseriesR; existingESDbridge/fanoutretained'}, {'net':'ADDR2','layer':1,'points':[[src['x_mm'],src['y_mm']],[30.4,19.65],[28.8,19.65],[28.0,20.0]],'width_mm':.1651,'role':'AboveactualADDR3signalviaantipad'}];vs=[{'net':'L0_E13','xy':[10.5,10.35],'OD':.7112,'drill':.36068,'role':'NewE13signalvia'}, {'net':'GND','xy':[11.5,9.6],'OD':.7112,'drill':.36068,'role':'E13return_pair_distance1.25mm'}, {'net':'GND','xy':[51.45,41.55],'OD':.7112,'drill':.36068,'role':'3V3headerreturn_pair_distance1.45mm'}]
def shape(p):
 q=p['shape'];w=q['width']*.0254;hh=q['height']*.0254
 return Point(p['x_mm'],p['y_mm']).buffer(w/2,quad_segs=256) if q['padType']=='ELLIPSE' and abs(w-hh)<1e-6 else rotate(box(p['x_mm']-w/2,p['y_mm']-hh/2,p['x_mm']+w/2,p['y_mm']+hh/2),p['angle'],origin=(p['x_mm'],p['y_mm']))
obs=[(p['id'],p['net'],shape(p),.1651,{1,2,15,16} if p['layer']==12 else {p['layer']}) for p in pads]
for x in a['lines']:
 if x['primitiveId'] not in delete:obs.append((x['primitiveId'],x['net'],LineString([(x['startX']*.0254,x['startY']*.0254),(x['endX']*.0254,x['endY']*.0254)]).buffer(x['lineWidth']*.0254/2,quad_segs=256),.1651,{x['layer']}))
for x in a['vias']:obs.append((x['primitiveId'],x['net'],Point(x['x']*.0254,x['y']*.0254).buffer(x['diameter']*.0254/2,quad_segs=256),.2501011,{1,2,15,16}))
for i,r in enumerate(routes):obs.append(('newroute'+str(i),r['net'],LineString(r['points']).buffer(r['width_mm']/2,quad_segs=256),.1651,{r['layer']}))
for i,v in enumerate(vs):obs.append(('newvia'+str(i),v['net'],Point(v['xy']).buffer(v['OD']/2,quad_segs=256),.2501011,{1,2,15,16}))
bad=[]
for nm,n,g,cl,ls in obs:
 if not nm.startswith(('newroute','newvia')):continue
 for on,net,q,clear,layer in obs:
  if n==net or not ls&layer:continue
  d=g.distance(q);req=max(cl,clear)
  if d<req-1e-8:bad.append({'own':nm,'other':on,'actual':d,'required':req})
holes=[{'id':x['primitiveId'],'xy':[x['x']*.0254,x['y']*.0254],'drill':x['holeDiameter']*.0254} for x in a['vias']]+[{'id':x['id'],'xy':[x['hole_x_mm'],x['hole_y_mm']],'drill':x['hole']['width']*.0254} for x in pads if x['hole']]
for i,v in enumerate(vs):
 for o in holes:
  gap=math.dist(v['xy'],o['xy'])-(v['drill']+o['drill'])/2
  if gap<.2999994-1e-8:bad.append({'newvia':i,'otherhole':o['id'],'edgegap':gap})
 holes.append({'id':'newvia'+str(i),'xy':v['xy'],'drill':v['drill']})
r={'at':datetime.datetime.now().astimezone().isoformat(),'source_sha256':h,'method':'Newactual reference-driven localrepair; not replay old fullnetjobs; only6owncandidate segments removed. Original91seedCu and all otherold301sourceCu preserved.','delete_own_candidate_lines':[actual[x] for x in delete],'routes':routes,'new_vias':vs,'physical_pass':not bad,'violations':bad,'native_applied':False,'signal_reference_acceptance':False,'terminal_exception_unchanged':True,'accepted':False};(E/'sensor-fourlayer-signal-reference-repair-plan-current.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k not in ['delete_own_candidate_lines','routes']},ensure_ascii=True));assert not bad
