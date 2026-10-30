from pathlib import Path
import sys,json,math,collections,hashlib,csv
D=Path(__file__).resolve().parent
sys.path.insert(0,str(D/'verification/support'))
from native_documents import documents
from shapely.geometry import Point,LineString,Polygon,box
from shapely.affinity import translate,rotate,scale
from shapely.strtree import STRtree
Q=Path(sys.argv[1]) if len(sys.argv)>1 else D/'Electrode84-450-CANDIDATE/pcb/Electrode84-450.epcb2'
output=D/(sys.argv[2] if len(sys.argv)>2 else 'FULL84-NATIVE-SAVED-SOURCE-AUDIT.json')
def poly(v):
 p=v['path'];p=p[0] if isinstance(p[0],list) else p;assert set(x for x in p if isinstance(x,str))<={'L'}
 coords=[x for x in p if not isinstance(x,str)];assert len(coords)%2==0
 g=Polygon([(x*.0254,y*.0254) for x,y in zip(coords[::2],coords[1::2])]);assert g.is_valid;return g
docs=documents(Q);b=next(d for d in docs if d['head']['docType']=='PCB');libs={d['head']['uuid']:d for d in docs};at=collections.defaultdict(dict);nets={}
for h,v in b['records']:
 if h['type']=='ATTR':at[v['parentId']][v['key']]=v['value']
 elif h['type']=='PAD_NET':_,cid,num,padid=json.loads(h['id']);nets[cid,padid]=v['padNet']
obs=[];headers={};fills={};holes=[];widths=[]
def obj(key,kind,net,layer,g,ref=None):obs.append({'id':key,'kind':kind,'net':net,'layer':layer,'g':g,'ref':ref})
for h,v in b['records']:
 typ=h['type'];key=h.get('id')
 if typ=='COMPONENT':
  assert v['layerId']==2,'All six headers must be on rear'
  ref=at[key]['Designator'];header={};angle=math.radians(v['angle']);co,si=math.cos(angle),math.sin(angle)
  for hh,p in libs[at[key]['Footprint']]['records']:
   if hh['type']!='PAD':continue
   # This verified straight 1x16 footprint has y=0 and isotropic circle/square pads.
   # A front/back reflection therefore leaves its copper centers and shapes identical.
   assert abs(p['centerY'])<1e-9
   x=(v['x']+p['centerX']*co-p['centerY']*si)*.0254;y=(v['y']+p['centerX']*si+p['centerY']*co)*.0254
   s=p['defaultPad'];w=s['width']*.0254;ht=s['height']*.0254;assert abs(w-ht)<1e-6
   g=Point(x,y).buffer(w/2,quad_segs=128) if s['padType']=='ELLIPSE' else box(x-w/2,y-ht/2,x+w/2,y+ht/2)
   net=nets[key,hh['id']];header[int(p['num'])]={'net':net,'xy_mm':[x,y]}
   for layer in [1,2]:obj(key+hh['id'],'PAD',net,layer,g,ref+'.'+p['num'])
  assert len(header)==16;headers[ref]=header
 elif typ=='FILL':
  assert v['layerId']==1;g=poly(v);fills[v['netName']]=g;obj(key,'FILL',v['netName'],1,g)
 elif typ=='VIA':
  g=Point(v['centerX']*.0254,v['centerY']*.0254).buffer(v['viaDiameter']*.0254/2,quad_segs=128)
  for layer in [1,2]:obj(key,'VIA',v['netName'],layer,g)
 elif typ=='LINE':
  assert v['layerId'] in [1,2];widths.append(v['width']*.0254)
  g=LineString([(v['startX']*.0254,v['startY']*.0254),(v['endX']*.0254,v['endY']*.0254)]).buffer(v['width']*.0254/2,quad_segs=64);obj(key,'LINE',v['netName'],v['layerId'],g)
 elif typ=='PAD':
  assert not v['plated'];holes.append(Point(v['centerX']*.0254,v['centerY']*.0254).buffer(v['hole']['width']*.0254/2,quad_segs=128))
assert len(headers)==6 and len(fills)==84 and len(holes)==6
rows=list(csv.DictReader((D/'ELECTRODE-HARNESS-84-VERIFIED.csv').open(encoding='utf-8-sig')))
for r in rows:
 raw=int(r['raw_index']);assert headers['JB'+r['bank']][int(r['pin'])]['net']==f'E{raw:03d}'
 assert raw==int(r['channel'])*6+int(r['bank'])
for bank in range(6):assert headers[f'JB{bank}'][15]['net']==headers[f'JB{bank}'][16]['net']==f'GND_B{bank}'
assert len([r for r in rows if r['pitch']=='C5' and r['channel']=='12' and r['bank'] in ['0','1','2']])==3
parent=list(range(len(obs)))
def root(i):
 while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
 return i
byid={}
for i,o in enumerate(obs):
 if o['id'] in byid:parent[root(i)]=root(byid[o['id']])
 else:byid[o['id']]=i
violations=[];minimum=float('inf');minpair=None
for layer in [1,2]:
 ids=[i for i,o in enumerate(obs) if o['layer']==layer];tree=STRtree([obs[i]['g'] for i in ids])
 for local,i in enumerate(ids):
  a=obs[i]
  for v in tree.query(a['g'].buffer(.8)):
   j=ids[int(v)]
   if j<=i:continue
   c=obs[j];gap=a['g'].distance(c['g'])
   if a['net']==c['net']:
    if gap<=1e-6:parent[root(i)]=root(j)
   else:
    if gap<minimum:minimum=gap;minpair=[a.get('ref') or a['id'],c.get('ref') or c['id']]
    if gap+1e-7<.25:violations.append({'layer':layer,'a':a.get('ref') or a['id'],'b':c.get('ref') or c['id'],'nets':[a['net'],c['net']],'gap_mm':gap})
netroots=collections.defaultdict(set)
for i,o in enumerate(obs):netroots[o['net']].add(root(i))
unconnected={net:len(v) for net,v in netroots.items() if len(v)!=1}
edge=min(o['g'].distance(box(0,0,236,156).boundary) for o in obs);holeclear=min(o['g'].distance(h) for o in obs for h in holes)
original_vias={v['via_id'] for v in json.loads((D/'FULL-PANEL-SOURCE-PLAN.json').read_text(encoding='utf-8'))['electrode_endpoints']}
newids={h['id'] for h,v in b['records'] if h['type']=='LINE' or (h['type']=='VIA' and h['id'] not in original_vias)};touching=[]
for o in obs:
 if o['layer']!=1 or o['id'] not in newids:continue
 for net,g in fills.items():
  if o['g'].intersects(g):touching.append({'id':o['id'],'net':o['net'],'active':net})
report={'schema':1,'status':'PASS_FULL84_SOURCE_ELECTRICAL_GEOMETRY' if not violations and not unconnected and not touching and edge>=.5 and holeclear>=.3 else 'FAIL_FULL84_SOURCE_ELECTRICAL_GEOMETRY','source_sha256':hashlib.sha256(Q.read_bytes()).hexdigest(),'headers_bottom':len(headers),'physical_header_pads':96,'electrode_polygons':84,'signal_nets':84,'local_ground_pair_nets':6,'all90_nets_connected':not unconnected,'unconnected_nets':unconnected,'different_net_clearance_gate_mm':.25,'minimum_source_different_net_gap_mm':minimum,'minimum_pair':minpair,'clearance_violations':violations,'minimum_copper_to_board_edge_mm':edge,'minimum_copper_to_NPTH_hole_edge_mm':holeclear,'NPTH_mounting_holes':len(holes),'minimum_trace_width_mm':min(widths),'existing_source_min_width_mm':6.0039*.0254,'source_min_width_pass':min(widths)>=6.0039*.0254,'additional_top_routes_touching_active_electrodes':touching,'mapping_all84_preserved':True,'C5_B0_B1_B2_CH12':True,'native_DRC':'SOURCE_ONLY_CHECK_SEE_05_LIVE_RESULT','manufacturing_release':False}
output.write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode('utf-8'));print(json.dumps(report,ensure_ascii=True))
