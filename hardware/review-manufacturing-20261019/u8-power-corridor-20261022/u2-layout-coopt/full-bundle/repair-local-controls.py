"""Retain the recovered 16-sensor bundle; recover local RC controls on top."""
from pathlib import Path
import json,sys,copy,math
P=Path(__file__).resolve().parent;O=P/'parser-repair';B=P.parent.parent;R=B.parent;inner='--inner-rc1' in sys.argv
sys.path.insert(0,'D:/FPGA-Project/codex-tools/pcb-resume-20261020');import shapely
sys.path[:0]=[str(R),str(B)]
import grid_route as g
from four_layer_geometry import copper,connected
from resume_offline import read_native
from native_plane_geometry import poured_planes
from shapely.geometry import Point,LineString,box
from shapely.ops import unary_union
rd=lambda p:json.loads(p.read_text(encoding='utf8'))
write=lambda p,v:p.write_text(json.dumps(v,indent=2),encoding='utf8')
base=rd(P/'working-capture.json');source=rd(B/'inv2-coupled/checkpoint-capture.json');q=rd(O/'new-copper.json');w=copy.deepcopy(base);plan=rd(P/'regional-edit-plan.json')
new=[p for p in q['lines'] if p['net']!='RC_DRIVE'];newvias=[]
for v in [v for v in q['vias'] if v['net']!='RC_DRIVE']:
 if not any(v['net']==z['net'] and math.dist((v['x'],v['y']),(z['x'],z['y']))*.0254<.0001 for z in w['vias']):newvias.append(v)
w['lines']+=new;w['vias']+=newvias
area=box(65.9350091,16.15197538,74.4821091,25.84718478).buffer(.5)
restored=[]
for p in plan['remove_lines']:
 if p['net']=='RC1' and p['layer']==1 and not LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2).intersects(area):restored.append(p)
w['lines']+=restored
extra_id='9ddcebbcb246460b';extra=next(p for p in source['lines'] if p['id']==extra_id);w['lines']=[p for p in w['lines'] if p.get('id')!=extra_id]
g.GAP=.18;w['routing_allow_new_vias']=False
def geom(data,net):
 f,ps=copper(data,net)
 return {1:f[1],2:f[16]},ps,[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]
g.geometries=geom;repairs=[];failure=None
try:
 for net in ['RC1','RC_DRIVE']:
  g.WIDTH=(8 if net=='RC1' else 6)*.0254
  if net=='RC1':
   if inner:
    a={**min([v for v in w['vias'] if v['net']=='RC1'],key=lambda v:math.dist((v['x'],v['y']),(2852.3622,1080.7087))),'layer':1};b={**min([v for v in w['vias'] if v['net']=='RC1'],key=lambda v:math.dist((v['x'],v['y']),(3187.0079,914.3701))),'layer':1}
    guards=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+.5,quad_segs=16) for p in w['lines'] if p['layer']==2 and p['net']!=net and (p['net'].startswith('L') or p['net'].startswith('RC') or p['net'].startswith('I2S_'))]
    def innergeom(data,net):
     f,ps=copper(data,net)
     return {1:f[16]+guards,2:f[1]},ps,[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]
    g.geometries=innergeom
   else:a=next(p for p in w['pads'] if p['ref']=='U2' and p['n']=='1');b=next(p for p in w['pads'] if p['ref']=='R2' and p['n']=='2')
  else:a=dict(x=2630.9055,y=817.9134,layer=1);b=dict(x=2917.3228,y=941.9291,layer=1)
  if net!='RC1':g.geometries=geom
  route=g.search(w,net,a,b,5);assert route and not route['vias'];assert all(p['layer']==1 for p in route['lines'])
  if net=='RC1' and inner:route['lines']=[{**p,'layer':16} for p in route['lines']]
  repairs+=route['lines'];w['lines']+=route['lines']
  c=connected([p for p in w['pads'] if p['net']==net],[p for p in w['lines'] if p['net']==net],[p for p in w['vias'] if p['net']==net]);print('REPAIRED',net,c,flush=True);assert c['complete']
except Exception as e:failure=repr(e);print('STOP',failure,flush=True)
proof={net:connected([p for p in w['pads'] if p['net']==net],[p for p in w['lines'] if p['net']==net],[p for p in w['vias'] if p['net']==net]) for net in rd(O/'attempt.json')['selected']}
result=dict(source_pcb_sha256=rd(O/'attempt.json')['source_pcb_sha256'],method='Restore original RC1 top copper outside U2; discard all mature RC_DRIVE output; recover its two affected local segments and RC1 branch with existing planner, top only, unchanged native widths, no new control vias',restored_source_lines=restored,extra_remove_lines=[extra],new_sensor_lines=new,new_vias=newvias,local_control_repairs=repairs,continuity=proof,complete_recovery=all(p['complete'] for p in proof.values()),failure=failure,native_imported=False,manufacturing_release=False)
suffix='-inner' if inner else '';write(P/('recovered-controls'+suffix+'.json'),result);write(P/('recovered-controls'+suffix+'-capture.json'),w)
print('COMPLETE_RECOVERY',result['complete_recovery'],flush=True)
