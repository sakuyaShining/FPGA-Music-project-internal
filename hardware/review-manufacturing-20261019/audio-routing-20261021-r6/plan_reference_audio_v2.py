"""Source-bound top-only I2S trial. No native edits or new vias."""
import sys,json,math,hashlib,copy,gc,time
from pathlib import Path
BASE=Path(__file__).resolve().parent;ROOT=BASE.parent;OUT=BASE/'reference-guided-v2';OUT.mkdir(exist_ok=False)
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
from shapely.geometry import LineString,box
from shapely.ops import unary_union
sys.path.insert(0,str(ROOT));import grid_route as g
from physical_geometry import actual_pad,connected_subset
from resume_offline import read_native
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();cp=json.loads((ROOT/'ACTIVE-ROUTING-CANDIDATE.json').read_text());SRC=ROOT/cp['source_capture'];PCB=Path(cp['project'])/'pcb/PCB1.epcb2';assert sha(PCB)==cp['pcb_sha256']
s=json.loads(SRC.read_text());raw=read_native(PCB);s['lines']=[dict(id=i,net=p['netName'],layer=p['layerId'],x1=p['startX'],y1=p['startY'],x2=p['endX'],y2=p['endY'],width=p['width']) for (k,i),p in raw.items() if k=='LINE' and p.get('layerId') in [1,15,16,2]];s['vias']=[dict(id=i,net=p['netName'],x=p['centerX'],y=p['centerY'],diameter=p['viaDiameter'],hole=p['holeDiameter']) for (k,i),p in raw.items() if k=='VIA']
nets=['I2S_LRCK','I2S_DIN','I2S_BCK'];w={**s,'lines':[p for p in s['lines'] if p['net'] not in nets],'vias':[p for p in s['vias'] if p['net'] not in nets]}
g.pad_shape=actual_pad;g.GRID=.05;g.GAP=.165;g.WIDTH=.1524;g.VIA_COST_MM=60;g.SEARCH_MARGINS=[8,22,50]
# The legacy conservative copper raster intentionally fills polygon holes.
# A reference-plane complement is a polygon with a large *free* hole, so it
# requires correct hole handling. Inflation plus continuous geometry checks
# retain the clearance margin.
from PIL import ImageChops
def holes_raster(geoms,bounds,inflate,shape):
 x0,y0,_,_=bounds;ny,nx=shape;image=g.Image.new('1',(nx,ny),0);draw=g.ImageDraw.Draw(image)
 for geom in geoms:
  if geom.is_empty:continue
  if geom.bounds[2]<bounds[0]-inflate or geom.bounds[0]>bounds[2]+inflate or geom.bounds[3]<bounds[1]-inflate or geom.bounds[1]>bounds[3]+inflate:continue
  for poly in g.pieces(geom.buffer(inflate,resolution=12)):
   if not hasattr(poly,'exterior'):continue
   pts=[((x-x0)/g.GRID,(y-y0)/g.GRID) for x,y in poly.exterior.coords]
   if not poly.interiors:draw.polygon(pts,fill=1);continue
   mask=g.Image.new('1',(nx,ny),0);md=g.ImageDraw.Draw(mask);md.polygon(pts,fill=1)
   for ring in poly.interiors:md.polygon([((x-x0)/g.GRID,(y-y0)/g.GRID) for x,y in ring.coords],fill=0)
   image=ImageChops.logical_or(image,mask);draw=g.ImageDraw.Draw(image)
 return g.np.asarray(image,dtype=g.np.bool_).copy()
g.raster=lambda gs,b,i,shape:holes_raster(gs,b,i+g.GRID/math.sqrt(2),shape)
probe=holes_raster([box(0,0,10,10).difference(box(2,2,8,8))],(0,0,10,10),.2,(201,201));assert not probe[100,100] and probe[20,20]
guards=[]
for p in s['pads']:
 if p['net'] not in cp['pending_nets'] or p['layer']!=1 or min(p['shape'][1:3])*.0254>.65:continue
 angle=math.radians(p['rotation']);axis=(math.cos(angle),math.sin(angle)) if p['shape'][1]>=p['shape'][2] else (-math.sin(angle),math.cos(angle));x,y=p['x']*.0254,p['y']*.0254
 guards.append(LineString([(x-axis[0]*1.7,y-axis[1]*1.7),(x+axis[0]*1.7,y+axis[1]*1.7)]).buffer(.0762))
# Actual saved reference-plane geometry from r4 is unchanged in the r5
# metadata-only checkpoint. Repair only isolated voids due entirely to the
# removed I2S vias; never fill a void containing another retained signal.
from shapely import wkb
from shapely.geometry import Point,Polygon
oldreference=ROOT/'joint-routing-20261021-r4/visual-native'
board=box(.5,.5,139.5,99.5)
removed=[Point(p['x']*.0254,p['y']*.0254) for p in s['vias'] if p['net'] in nets]
retained_centers=[Point(p['x']*.0254,p['y']*.0254) for p in s['vias'] if p['net'] not in nets and p['net']!='GND']+[Point(p['x']*.0254,p['y']*.0254) for p in s['pads'] if p['layer']==12 and p['net']!='GND']
inner_objects=[(p['net'],LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2)) for p in s['lines'] if p['layer'] in [15,16] and p['net']!='GND']
w['inner_copper']=inner_objects
references={};repairs=[]
for layer in [15,16]:
 ref=wkb.loads((oldreference/('plane-'+str(layer)+'.wkb')).read_bytes());polygons=list(ref.geoms) if hasattr(ref,'geoms') else [ref];fill=[]
 for po in polygons:
  if po.geom_type!='Polygon':continue
  for ring in po.interiors:
   hole=Polygon(ring)
   if not any(hole.contains(q) for q in removed):continue
   if any(hole.intersects(q) for q in retained_centers):continue
   if layer==16 and any(hole.intersects(q) for n,q in inner_objects):continue
   fill.append(hole)
 references[layer]=unary_union([ref,*fill]);repairs.append(dict(layer=layer,isolated_removed_via_voids_filled=len(fill),filled_mm2=sum(p.area for p in fill)))
(OUT/'predicted-reference-repairs.json').write_text(json.dumps(dict(repairs=repairs,not_actual_rebuilt_ground=True,source_pcb_sha256=cp['pcb_sha256']),indent=2))
orig=g.geometries
def geom(data,net):
 f,ps,ko=orig(data,net);f[1]+=guards
 ends=unary_union([actual_pad(p).buffer(.6) for p in s['pads'] if p['net']==net])
 for outer,ref in [(1,15),(2,16)]:
  void=board.difference(references[ref]).difference(ends);f[outer].append(void)
  for v in data['vias']:
   if v['net'] in nets and v['net']!=net:f[outer].append(Point(v['x']*.0254,v['y']*.0254).buffer(v['diameter']*.0254/2+.35))
 return f,ps,ko
g.geometries=geom
# Every new through via must also clear actual foreign copper on the inner
# signal layer. The old outer-only router did not include that condition.
import inspect
code=inspect.getsource(g.search).replace('def search(','def search4(');pos=code.index('    own_drills=')
code=code[:pos]+"    via_block|=raster([q for n,q in data.get('inner_copper',[]) if n!=net],bounds,VIA_D/2+GAP,shape)\n"+code[pos:]
exec(code,g.__dict__);g.search=g.search4
routes=[];failed=[]
def length(ls):return sum(math.hypot(p['x2']-p['x1'],p['y2']-p['y1'])*.0254 for p in ls)
def validate(data,net,lines,vias):
 f,ps,ko=g.geometries(data,net);cu={l:unary_union(f[l]) for l in [1,2]};mount=unary_union(ko);minimum=99.
 for p in lines:
  assert p['layer'] in [1,2];q=LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]);gap=q.distance(cu[p['layer']])-p['width']*.0254/2;minimum=min(gap,minimum);assert gap>=.158,(net,gap);assert q.distance(mount)>=p['width']*.0254/2+.15
 both=unary_union(f[1]+f[2]+[q for n,q in inner_objects if n!=net]);pad_union=unary_union(ps)
 assert len({(round(p['x'],5),round(p['y'],5)) for p in vias})==len(vias)
 for i,p in enumerate(vias):
  q=Point(p['x']*.0254,p['y']*.0254);gap=q.distance(both)-p['diameter']*.0254/2;minimum=min(minimum,gap);assert gap>=.158,(net,'via',gap);assert q.distance(pad_union)-p['hole']*.0254/2>=.25
  for v in data['vias']+vias[:i]:
   if v is p or v==p:continue
   assert q.distance(Point(v['x']*.0254,v['y']*.0254))-(p['hole']+v['hole'])*.0254/2>=.3499,(net,'drill')
 return minimum
def save():
 (OUT/'plan.json').write_text(json.dumps(dict(source_file=str(SRC),source_sha256=sha(SRC),native_pcb_sha256=cp['pcb_sha256'],project=cp['project'],routes=routes,failed=failed,protection='Both 1.7mm fine-pitch escape axes reserved for every remaining pending pin',reserved_pin_corridors=len(guards),native_imported=False,manufacturing_release=False,requires_actual_rebuilt_ground_reference_check=True),indent=2))
for net in nets:
 print('START',net,flush=True)
 try:
  rt=g.plan(w,net);assert len(rt['vias'])<=3,'Audio via budget <=3';assert connected_subset([p for p in s['pads'] if p['net']==net],rt['lines'],rt['vias'])['complete']
  gap=validate(w,net,rt['lines'],rt['vias']);oldlen=length([p for p in s['lines'] if p['net']==net]);newlen=length(rt['lines']);assert newlen<=oldlen,'Audio length increase'
  rt['quality']=dict(before_length_mm=oldlen,after_length_mm=newlen,before_vias=sum(p['net']==net for p in s['vias']),after_vias=len(rt['vias']),min_foreign_gap_mm=gap)
  routes.append(rt);w['lines']+=rt['lines'];w['vias']+=rt['vias'];print('REFERENCE_CANDIDATE',net,rt['quality'],flush=True)
 except Exception as e:
  failed.append(dict(net=net,error=repr(e)));w['lines'] +=[p for p in s['lines'] if p['net']==net];w['vias'] +=[p for p in s['vias'] if p['net']==net];print('REJECTED',net,repr(e),flush=True)
 save();gc.collect()
# Restore rejected copper before accepting any subset; repeat pruning to a fixed point.
pruned=[]
while True:
 bad=[]
 for rt in routes:
  try:validate(w,rt['net'],rt['lines'],rt['vias'])
  except Exception as e:bad.append((rt,repr(e)))
 if not bad:break
 for rt,err in bad:
  pruned.append(dict(net=rt['net'],reason=err));routes.remove(rt);w['lines']=[p for p in w['lines'] if p['net']!=rt['net']]+[p for p in s['lines'] if p['net']==rt['net']];w['vias']=[p for p in w['vias'] if p['net']!=rt['net']]+[p for p in s['vias'] if p['net']==rt['net']]
save();v=json.loads((OUT/'plan.json').read_text());v['pruned']=pruned;v['batch_final_geometry_pass']=bool(routes);(OUT/'plan.json').write_text(json.dumps(v,indent=2));assert sha(PCB)==cp['pcb_sha256'];print('DONE',len(routes),'safe offline candidates; native unchanged',flush=True)
