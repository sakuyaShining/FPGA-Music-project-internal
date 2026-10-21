"""One bounded MOSI closure trial after moving the pulldown from its cage."""
from pathlib import Path
import sys,json,copy,re,hashlib
B=Path(__file__).resolve().parent;R=B.parent;O=B/'mosi'
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
import grid_route as g
from four_layer_geometry import copper,connected
from shapely.geometry import LineString,box
read=lambda p:json.loads(p.read_text(encoding='utf8'))
opts=read(O/'placement-options.json');s=read(B/'checkpoint-capture.json');option=int(sys.argv[1]) if len(sys.argv)>1 else -1
work=copy.deepcopy(s);added=dict(lines=[],vias=[])
if option>=0:
 v=opts['candidates'][option]
 work['pads']=[p for p in work['pads'] if p['ref']!='R64']+v['pads'];remove_lines=opts['remove_lines'];remove_vias=opts['remove_vias']
else:
 # Two resistor relocation trials exposed the real obstruction at U8's via:
 # VIS_CS_N cuts inner16 to its east; the new GND stitch occupies the exit.
 # Move that MOSI exit across the existing VIS_CS_N track, preserving R64.
 v=None;remove_lines=[p for p in s['lines'] if p['id']=='3046abffee283114']
 remove_vias=[p for p in s['vias'] if p['id']=='d2cb5aee0e210038' or (p['net']=='GND' and abs(p['x']*.0254-64.023099)<.001 and abs(p['y']*.0254-49.133125)<.001)]
 assert len(remove_lines)==1 and len(remove_vias)==2
 end=(66.45,49.15) if option<=-3 else (64.025,49.15)
 ps=[(remove_lines[0]['x1']*.0254,remove_lines[0]['y1']*.0254),(62.65,48.86),(62.9,49.4),(66.2,49.4),end] if option<=-3 else [(remove_lines[0]['x1']*.0254,remove_lines[0]['y1']*.0254),(62.65,48.86),(62.8,49.15),end]
 added['lines']=[dict(net='BUS_MOSI',layer=1,x1=a[0]/.0254,y1=a[1]/.0254,x2=b[0]/.0254,y2=b[1]/.0254,width=6) for a,b in zip(ps,ps[1:])]
 added['vias']=[dict(id='new-u8-mosi-anchor',net='BUS_MOSI',x=end[0]/.0254,y=end[1]/.0254,diameter=24,hole=12)]
 if option in [-4,-5,-6,-7,-8]:
  v=opts['candidates'][2];work['pads']=[p for p in work['pads'] if p['ref']!='R64']+v['pads'];remove_lines+=opts['remove_lines'];remove_vias+=opts['remove_vias']
 if option in [-5,-8]:
  work['pads']=[p for p in work['pads'] if p['ref']!='TP14'];remove_lines += [p for p in s['lines'] if p['id']=='9a822b0eaad7e351'];remove_vias += [p for p in s['vias'] if p['id']=='75b02ad4b517cfd4']
 if option==-6:
  remove_lines += [p for p in s['lines'] if p['id'] in ['9a822b0eaad7e351','1d8c6af9bf673d26']];remove_vias += [p for p in s['vias'] if p['id'] in ['75b02ad4b517cfd4','4c8de6ab447ab4b8']]
 if option in [-7,-8]:
  remove_lines += [p for p in s['lines'] if p['id']=='1d8c6af9bf673d26'];remove_vias += [p for p in s['vias'] if p['id']=='4c8de6ab447ab4b8']
  added['lines'] += [dict(net='BUS_MOSI',layer=1,x1=3194,y1=1731.3,x2=79.65/.0254,y2=43.45/.0254,width=6)]
  added['vias'] += [dict(id='new-u15-mosi-anchor',net='BUS_MOSI',x=79.65/.0254,y=43.45/.0254,diameter=24,hole=12)]
 if option in [-9,-10]:
  remove_lines += [p for p in s['lines'] if p['net']=='TP_RESET_N' and p['layer']==16]
 if option==-10:
  work['pads']=[p for p in work['pads'] if p['ref'] not in ['R64','TP14']];remove_lines+=opts['remove_lines']+[p for p in s['lines'] if p['id']=='9a822b0eaad7e351'];remove_vias+=opts['remove_vias']+[p for p in s['vias'] if p['id']=='75b02ad4b517cfd4']
 if option==-11:
  remove_lines += [p for p in s['lines'] if p['net']=='BUS_SCK'];remove_vias += [p for p in s['vias'] if p['net']=='BUS_SCK']
  fan=read(B/'bus-escapes.json')
  for k in added:added[k]+=[p for p in fan[k] if p['net']=='BUS_SCK']
work['lines']=[p for p in work['lines'] if p not in remove_lines]+added['lines'];work['vias']=[p for p in work['vias'] if p not in remove_vias]+added['vias']
g.GRID=.05;g.SEARCH_MARGINS=[4,10]
quiet=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in work['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))]
mount=[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]
def geometry(data,net):
 f,pads=copper(data,net);data['routing_extra_via_obstacles']=f[15]+f[2]+quiet
 return {1:f[1],2:f[16]+quiet},pads,mount
g.geometries=geometry
target=copy.deepcopy(work);net='BUS_MOSI'
for p in target['vias']:
 if p['net']==net:p['routing_retained']=True
refs=['R64','U15','TP14'] if option==-6 else ['R64']
target['pads']=[{**p,'routing_pad_exclude':p['net']==net and (v is None or p['ref'] not in refs)} for p in target['pads']]
pad=next(p for p in s['pads'] if p['net']==net and p['ref']=='J6')
anchors=[{**pad,'id':'anchor-host-mosi','ref':'HOST','layer':12,'shape':['ELLIPSE',24,24,0],'routing_pad_exclude':False}]
for i,p in enumerate([p for p in work['vias'] if p['net']==net]):anchors.append({**pad,'id':'anchor-mosi'+str(i),'ref':'VIA'+str(i),'x':p['x'],'y':p['y'],'rotation':0,'layer':12,'shape':['ELLIPSE',24,24,0],'routing_pad_exclude':False})
target['pads']+=anchors
print('R64',v['midpoint_mm'] if v else 'UNCHANGED; U8 MOSI via moved across VIS_CS_N',flush=True)
search=g.search
def trace_search(data,net,a,b,margin):
 print('EDGE',a['ref'],[round(a[k]*.0254,3) for k in ['x','y']],b['ref'],[round(b[k]*.0254,3) for k in ['x','y']],flush=True)
 return search(data,net,a,b,margin)
g.search=trace_search
try:
 route=g.plan(target,net)
 for p in route['lines']:
  if p['layer']==2:p['layer']=16
 for k in ['lines','vias']:work[k]+=route[k]
 proof=connected([p for p in work['pads'] if p['net']==net],[p for p in work['lines'] if p['net']==net],[p for p in work['vias'] if p['net']==net]);assert proof['complete'],proof
 if option in [-9,-10,-11]:
  # Both nets must be complete before a native candidate can be accepted.
  (O/'mosi-before-reset-recovery.json').write_text(json.dumps(route,indent=2),encoding='utf8')
  reset='BUS_SCK' if option==-11 else 'TP_RESET_N';t=copy.deepcopy(work);t['pads']=[{**p,'routing_pad_exclude':p['net']==reset} for p in t['pads']]
  seed=next(p for p in s['pads'] if p['net']==reset)
  for i,p in enumerate([p for p in work['vias'] if p['net']==reset]):
   p['routing_retained']=True;t['pads'].append({**seed,'id':'anchor-reset-'+str(i),'ref':'RESETV'+str(i),'x':p['x'],'y':p['y'],'rotation':0,'layer':12,'shape':['ELLIPSE',24,24,0],'routing_pad_exclude':False})
  for p in s['pads']:
   if p['net']==reset and p['layer']==12:t['pads'].append({**p,'id':'anchor-reset-host-'+p['id'],'ref':'RESETHOST','shape':['ELLIPSE',24,24,0],'routing_pad_exclude':False})
  rr=g.plan(t,reset)
  for p in rr['lines']:
   if p['layer']==2:p['layer']=16
  for k in ['lines','vias']:work[k]+=rr[k];route[k]+=rr[k]
  assert connected([p for p in work['pads'] if p['net']==reset],[p for p in work['lines'] if p['net']==reset],[p for p in work['vias'] if p['net']==reset])['complete']
 for k in added:route[k]+=added[k]
 result=dict(source_pcb_sha256=opts['source_pcb_sha256'],component=opts['component'],placement=v,remove_lines=remove_lines,remove_vias=remove_vias,**route,continuity=proof,layout_incomplete=option==-10,manufacturing_release=False)
 (O/'route.json').write_text(json.dumps(result,indent=2),encoding='utf8');(O/'planned-capture.json').write_text(json.dumps(work),encoding='utf8');print('COMPLETE',len(route['lines']),len(route['vias']),proof,flush=True)
except Exception as e:
 (O/'route-failure.json').write_text(json.dumps(dict(option=option,placement=v,error=str(e)),indent=2),encoding='utf8');raise
