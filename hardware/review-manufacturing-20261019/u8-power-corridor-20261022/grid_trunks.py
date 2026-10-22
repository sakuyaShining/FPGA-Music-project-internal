"""Reuse existing search for inner16 trunks between the now-reserved physical vias."""
from pathlib import Path
import json,copy,re
from exchange import read,OUT,sha
import grid_route as g
from four_layer_geometry import copper,connected
from shapely.geometry import LineString,box
cp,pcb,work=read();fan=json.loads((OUT/'bus-escapes.json').read_text())
g.GRID=.05;g.SEARCH_MARGINS=[4,10]
quiet=[LineString([(p['x1']*.0254,p['y1']*.0254),(p['x2']*.0254,p['y2']*.0254)]).buffer(p['width']*.0254/2+(.6 if p['net'].startswith('I2S_') else .5),quad_segs=32) for p in work['lines'] if p['layer']==2 and (p['net'].startswith('I2S_') or re.fullmatch(r'RC[0-5]',p['net']) or re.match(r'L[0-5]_',p['net']))]
mount=[box(x-1.75,y-1.75,x+1.75,y+1.75) for x,y in [(3,18),(137,16.5),(3,82),(137,88)]]
def geometry(data,net):
 f,pads=copper(data,net)
 data['routing_extra_via_obstacles']=f[15]+f[2]+quiet
 return {1:f[1],2:f[16]+quiet},pads,mount
g.geometries=geometry
allroutes=dict(lines=[],vias=[],nets=[],failed=[])
for net in ['INPUT_LOAD_N','BUS_MOSI','BUS_SCK']:
 g.SEARCH_MARGINS=[4,10,22] if net=='BUS_MOSI' else [4,10]
 target=copy.deepcopy(work);target['routing_allow_new_vias']=True
 for v in target['vias']:
  if v['net']==net:v['routing_retained']=True
 target['pads']=[{**p,'routing_pad_exclude':p['net']==net} for p in target['pads']]
 pad=next(p for p in work['pads'] if p['net']==net and p['ref']=='J6')
 anchors=[{**pad,'id':'anchor-host-'+net,'ref':'HOST','layer':12,'shape':['ELLIPSE',24,24,0],'routing_pad_exclude':False}]
 if net=='INPUT_LOAD_N':
  v=next(v for v in work['vias'] if v.get('id')=='b0ffac95fd927fde') if any(v.get('id')=='b0ffac95fd927fde' for v in work['vias']) else min([v for v in work['vias'] if v['net']==net],key=lambda v:(v['x']*.0254-64.575)**2+(v['y']*.0254-62.525)**2)
  assert abs(v['x']*.0254-64.575)<.01 and abs(v['y']*.0254-62.525)<.01
  nodes=[v]
 else:nodes=[v for v in fan['vias'] if v['net']==net]
 for i,v in enumerate(nodes):anchors.append({**pad,'id':'anchor-trunk-'+net+str(i),'ref':'VIA'+str(i),'x':v['x'],'y':v['y'],'rotation':0,'layer':12,'shape':['ELLIPSE',24,24,0],'routing_pad_exclude':False})
 target['pads']+=anchors
 try:
  route=g.plan(target,net)
 except Exception as e:
  allroutes['failed'].append(dict(net=net,error=str(e)));print('FAILED',net,str(e),flush=True);continue
 for p in route['lines']:
  assert p['layer'] in [1,2]
  if p['layer']==2:p['layer']=16
 work['lines']+=route['lines'];work['vias']+=route['vias'];proof=connected([p for p in work['pads'] if p['net']==net],[p for p in work['lines'] if p['net']==net],[p for p in work['vias'] if p['net']==net])
 assert proof['complete'],(net,proof)
 allroutes['lines']+=route['lines'];allroutes['vias']+=route['vias'];allroutes['nets'].append(dict(net=net,continuity=proof,segments=len(route['lines']),vias=len(route['vias']),length_mm=sum(((p['x1']-p['x2'])**2+(p['y1']-p['y2'])**2)**.5*.0254 for p in route['lines'])))
 (OUT/'grid-trunks.json').write_text(json.dumps(allroutes,indent=2));print('COMPLETE',net,allroutes['nets'][-1],flush=True)
allroutes.update(source_pcb_sha256=cp['pcb_sha256'],plan_sha256=sha(OUT/'plan.json'),fanout_sha256=sha(OUT/'bus-escapes.json'),native_imported=False,manufacturing_release=False)
(OUT/'grid-trunks.json').write_text(json.dumps(allroutes,indent=2));assert sha(pcb)==cp['pcb_sha256']
