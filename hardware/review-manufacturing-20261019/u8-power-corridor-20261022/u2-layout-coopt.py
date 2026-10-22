"""Single source-bound U2 relocation and mature-router comparison; no native edit."""
from pathlib import Path
import sys,json,ast,copy,math,heapq,hashlib,importlib.util,re,subprocess
B=Path(__file__).resolve().parent;R=B.parent;right_group='--right-group' in sys.argv;full_bundle='--full-bundle' in sys.argv;O=B/'u2-layout-coopt'/('right-group' if right_group else 'full-bundle' if full_bundle else '');O.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
from physical_geometry import actual_pad
from four_layer_geometry import copper
from shapely.geometry import Point,LineString,box
from shapely.affinity import translate
from shapely.ops import unary_union
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
wr=lambda p,v:p.write_text(json.dumps(v,indent=2),encoding='utf8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp=rd(R/'REGIONAL-WORK-IN-PROGRESS.json');pcb=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(pcb)==cp['pcb_sha256']=='6509803e7afca781b7f71ad69183cc10d8f6413312701eb16a2cdc46dfe83afd'
assert not (O/'attempt.json').exists(),'Inspect the existing job, never duplicate'
s=rd(Path(cp['source_capture']));work=copy.deepcopy(s)
# Reuse the historical pure footprint-box extraction, omitting its old-source
# assertion and all placement/routing trials after the extraction boundary.
prefix=(B/'mosi_prepare.py').read_text(encoding='utf8').split("cid=cid_by_ref['R64']")[0]
tree=ast.parse(prefix);tree.body=[n for n in tree.body if not isinstance(n,ast.Assert)];d={'__file__':str(B/'mosi_prepare.py')};exec(compile(tree,'footprint-boxes-only','exec'),d)
dx=(5 if right_group else 0)/.0254;dy=-2/.0254;group={'U2','C2'} if right_group else {'U2'}
oldpads=[p for p in s['pads'] if p['ref']=='U2'];moved_source=[p for p in s['pads'] if p['ref'] in group];newpads=[{**p,'x':p['x']+dx,'y':p['y']+dy} for p in moved_source]
bbox=translate(d['boxes']['U2'],xoff=dx*.0254,yoff=-2);neighbours=sorted((translate(d['boxes'][g],xoff=dx*.0254,yoff=-2).distance(q),g+':'+ref) for g in group for ref,q in d['boxes'].items() if ref not in group)
report=dict(source_pcb_sha256=cp['pcb_sha256'],component='U2',component_id=d['cid_by_ref']['U2'],group=sorted(group),delta_mm=[dx*.0254,-2],nearest_bodies=neighbours[:8],native_imported=False,manufacturing_release=False)
wr(O/'layout-screen.json',report);print('BODY_SCREEN',neighbours[:5],flush=True)
assert neighbours[0][0]>=.25,'U2 body/courtyard candidate overlaps neighbour; no routing launched'
key=lambda x,y:(round(x,1),round(y,1));remove={};ends={};selected=[];pathwidth={}
for pad in oldpads:
 net=pad['net']
 if net.startswith('ADDR') or net=='MUX_DISABLE' or net in ['GND','3V3_IO']:continue
 ls=[p for p in s['lines'] if p['net']==net and p['layer']==1];adj={}
 for p in ls:
  a,b=key(p['x1'],p['y1']),key(p['x2'],p['y2']);dist=math.dist(a,b)*.0254;adj.setdefault(a,[]).append((b,dist,p));adj.setdefault(b,[]).append((a,dist,p))
 start=min(adj,key=lambda q:math.dist(q,(pad['x'],pad['y'])));assert math.dist(start,(pad['x'],pad['y']))*.0254<.003
 vias={key(p['x'],p['y']):p for p in s['vias'] if p['net']==net};queue=[(0,start,[])];seen=set();found=None
 while queue:
  dist,node,path=heapq.heappop(queue)
  if dist>20:break
  if node in seen:continue
  seen.add(node)
  if node in vias:found=(vias[node],path);break
  if path and not d['boxes']['U2'].buffer(.3).covers(Point(node[0]*.0254,node[1]*.0254)):
   found=(dict(net=net,x=node[0],y=node[1],layer=1,retained_track_endpoint=True),path);break
  for other,length,line in adj.get(node,[]):
   if other not in seen:heapq.heappush(queue,(dist+length,other,path+[line]))
 assert found and found[1],('No bounded source fanout',net)
 via,path=found;ends[net]=via;pathwidth[net]=max(p['width'] for p in path);selected.append(net)
 for p in path:remove[p['id']]=p
# Recover the complete top copper of these 17 affected sensor nets together.
# Keeping only the nearest stub left other branches across the moved pin row.
remove={p['id']:p for p in s['lines'] if p['layer']==1 and p['net'] in selected}
removed_vias=[]
if full_bundle:
 area=d['boxes']['U2'].union(bbox).buffer(.5)
 removed_vias=[v for v in s['vias'] if v['net'].startswith('L1_M') or (v['net']=='RC1' and area.covers(Point(v['x']*.0254,v['y']*.0254)))]
 for p in s['lines']:
  if p['net'].startswith('L1_M') or (p['net']=='RC1' and LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2).intersects(area)):remove[p['id']]=p
if right_group or full_bundle:
 movedshape=unary_union([actual_pad(p).buffer(.16) for p in newpads])
 crossing=[p for p in s['lines'] if p['layer']==1 and p['net']=='RC_DRIVE' and LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2).intersects(movedshape)]
 assert crossing
 for p in crossing:remove[p['id']]=p
 selected.append('RC_DRIVE');pathwidth['RC_DRIVE']=max(p['width'] for p in crossing)
work['lines']=[p for p in s['lines'] if p['id'] not in remove];work['pads']=[p for p in s['pads'] if p['ref'] not in group]+newpads
work['vias']=[p for p in s['vias'] if p not in removed_vias]
bridges=[]
for pad in moved_source:
 if pad['net'] not in ['GND','3V3_IO']:continue
 widths=[p['width'] for p in s['lines'] if p['net']==pad['net'] and min(math.dist((p['x1'],p['y1']),(pad['x'],pad['y'])),math.dist((p['x2'],p['y2']),(pad['x'],pad['y'])))*.0254<.003]
 assert widths
 if right_group:
  import grid_route as grid
  grid.WIDTH=max(widths)*.0254;grid.GAP=.18
  def geom(data,net):
   f,ps=copper(data,net)
   return {1:f[1],2:f[16]},ps,[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]
  grid.geometries=geom;work['routing_allow_new_vias']=False
  route=grid.search(work,pad['net'],{**pad,'x':pad['x']+dx,'y':pad['y']+dy},{**pad,'layer':1},5)
  assert route and not route['vias'],'Power/ground recovery failed'
  for p in route['lines']:assert p['layer']==1
  bridges+=route['lines'];work['lines']+=route['lines']
 else:bridges.append(dict(net=pad['net'],layer=1,x1=pad['x'],y1=pad['y']+dy,x2=pad['x'],y2=pad['y'],width=max(widths)))
if not right_group:work['lines']+=bridges
fail=[]
for p in newpads:
 f,_=copper(work,p['net']);gap=actual_pad(p).distance(unary_union(f[1]));
 if gap<.1524-1e-6:fail.append(dict(kind='moved_pad_foreign_copper',pin=p['n'],net=p['net'],gap_mm=gap))
for p in bridges:
 f,_=copper(work,p['net']);q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);gap=q.distance(unary_union(f[1]))-p['width']*.0254/2
 if gap<.158:fail.append(dict(kind='power_ground_bridge',net=p['net'],gap_mm=gap))
report.update(removed_source_fanouts=len(remove),removed_vias=removed_vias,routing_nets=selected,power_ground_bridges=bridges,failures=fail);wr(O/'layout-screen.json',report)
assert not fail,fail
# Only validated source pad/via identities are reused; old candidate copper
# still requires full independent validation before any native adoption.
oldesc=rd(B/'address-extended-escapes.json');work['lines']+=[p for p in oldesc['lines'] if p['net']=='ADDR0'];work['vias']+=[p for p in oldesc['vias'] if p['net']=='ADDR0']
work['lines']=[{**p,'id':p.get('id','fixed-coopt-'+str(i))} for i,p in enumerate(work['lines'])];work['vias']=[{**p,'id':p.get('id','fixed-coopt-via-'+str(i))} for i,p in enumerate(work['vias'])]
if full_bundle:
 pad=next(p for p in newpads if p['n']=='10' and p['ref']=='U2');work['vias'].append(dict(id='trial-addr0-u2',net='ADDR0',x=pad['x'],y=pad['y']-1.375/.0254,diameter=24,hole=12));work['lines'].append(dict(id='trial-addr0-u2-line',net='ADDR0',layer=1,x1=pad['x'],y1=pad['y'],x2=pad['x'],y2=pad['y']-1.375/.0254,width=6))
else:selected.append('ADDR0')
wr(O/'working-capture.json',work);wr(O/'regional-edit-plan.json',dict(routing_nets=selected,remove_lines=list(remove.values()),remove_vias=removed_vias,component=report['component'],delta_mm=report['delta_mm']))
spec=importlib.util.spec_from_file_location('coopt_exchange',B/'exchange.py');e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e);e.OUT=O;e.read=lambda:(cp,pcb,work);e.build()
text=(O/'input.dsn').read_text(encoding='utf8')
for net in selected:
 if net in ['ADDR0','RC_DRIVE']:continue
 # The sensor stub recovery stays on top, retaining the full existing
 # bottom trunks and both original vias. No extra sensor capacitance via.
 pattern=r'\(class '+re.escape(e.atom(net))+r' '+re.escape(e.atom(net))+r' \(circuit \(use_via ([^)]+)\)\) \(rule \(width [^)]+\)'
 text,count=re.subn(pattern,lambda m:'(class '+e.atom(net)+' '+e.atom(net)+' (circuit (use_layer '+('TopLayer BottomLayer' if full_bundle else 'TopLayer')+') (use_via '+m.group(1)+')) (rule (width '+str(pathwidth[net])+')',text);assert count==1,net
if full_bundle:
 guards=[]
 for i,v in enumerate([v for v in work['vias'] if v['net']=='ADDR0']):
  q=Point(v['x'],v['y']).buffer(v['diameter']/2+.5/.0254,quad_segs=16)
  guards+=['(keepout '+e.atom('addr0-sensor-bottom-'+str(i))+' '+e.polygon('BottomLayer',q)+')','(via_keepout '+e.atom('addr0-sensor-hole-'+str(i))+' '+e.polygon('TopLayer',q)+')']
 marker='(rule (width 6) (clearance 6))'
 text=text.replace(marker,marker+'\n'+'\n'.join(guards)+'\n',1)
(O/'input.dsn').write_text(text,encoding='utf8');audit=rd(O/'exchange-audit.json');audit['dsn_sha256']=sha(O/'input.dsn');audit['component_delta_mm']=report['delta_mm'];audit['routable_layers']=[1,2] if full_bundle else [1,16];wr(O/'exchange-audit.json',audit)
args=['C:/Program Files/Java/bin/java.exe','-Xmx1g','-jar','D:/FPGA-Project/codex-tools/freerouting/freerouting-2.5.0.jar','-de',str(O/'input.dsn'),'-do',str(O/'result.ses'),'--router.autorouter.max_passes=6','--router.optimizer.enabled=true','--router.max_threads=2','--router.fanout.enabled=false','--router.layers.routable='+('true,false,false,true' if full_bundle else 'true,false,true,false'),'--router.automatic_neckdown=false','--router.strict_drc=true','--router.job_timeout=00:02:00','--router.autorouter.ignore_net_classes='+','.join(n for n in audit['allnets'] if n not in selected),'--router.result_json='+str(O/'result.json'),'-da','--gui.enabled=false','--api_server.enabled=false','--logging.file.enabled=false','--user_data_path='+str(O/'runtime-route')]
assert sha(Path(args[3]))=='f6f51bb02245e8e717f9359bd260cc9c5c0b1bc0acc8b7cb2cd5b8ffeb5de3c7'
attempt=dict(source_pcb_sha256=cp['pcb_sha256'],state='starting',args=args,native_imported=False,selected=selected);wr(O/'attempt.json',attempt)
with (O/'run.log').open('w',encoding='utf8') as log:
 process=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT);attempt.update(state='running',pid=process.pid);wr(O/'attempt.json',attempt);print('RUNNING',process.pid,flush=True)
 try:code=process.wait(timeout=170)
 except subprocess.TimeoutExpired:process.terminate();code=process.wait(timeout=15);attempt['watchdog_terminated']=True
attempt.update(state='terminal',exit_code=code,ses_exists=(O/'result.ses').exists(),source_unchanged=sha(pcb)==cp['pcb_sha256']);wr(O/'attempt.json',attempt);print('TERMINAL',code,attempt['ses_exists'],flush=True)
