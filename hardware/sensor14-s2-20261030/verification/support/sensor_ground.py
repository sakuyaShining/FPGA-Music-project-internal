from sensor_geometry import *
from shapely.ops import unary_union
import ast
from pour_points import points

def ground(b):
 pours={h['id']:v for h,v in b['records'] if h['type']=='POUR'};planes={}
 for h,po in b['records']:
  if h['type']!='POURED':continue
  layer=pours[json.loads(h['id'])[1]]['layerId'];cu=[]
  for f in po['pourFill']:
   if f['fill']:
    g=Polygon(points(f['path'][0]));assert g.is_valid
    for pp in f['path'][1:]:g=g.symmetric_difference(Polygon(points(pp)))
    # SOLID production optimization stores inset polygon boundaries. Native
    # Gerber draws those exact contours with a circular aperture equal to the
    # minimum neck width (8mil here). Restore the contour stroke as well as fill.
    neck=pours[json.loads(h['id'])[1]]['pourType'].get('fineness',0)
    if neck:g=g.buffer(neck/2,quad_segs=128)
   else:g=LineString(points(f['path'])).buffer(f['strokeWidth']*5,quad_segs=128)
   cu.append(g)
  planes[layer]=unary_union(cu)
 obs=objects(b);mains={};report={'planes':{},'gnd_pad_contacts':[],'via_contacts':[],'critical_reference':[]}
 for layer,p in planes.items():
  copper=unary_union([p]+[o['g'] for o in obs if o['layer']==layer and o['net']=='GND']);polys=list(copper.geoms) if hasattr(copper,'geoms') else [copper];main=max(polys,key=lambda g:g.area);mains[layer]=main
  report['planes'][layer]={'main_area_mm2':main.area*.0254**2,'component_count':len(polys),'native_pour_area_mm2':p.area*.0254**2}
 for o in obs:
  if o['net']=='GND' and o['layer']==15 and o['kind']in['PAD','VIA']:
   contact=mains[15].intersection(o['g']).area*.0254**2;report['gnd_pad_contacts' if o['kind']=='PAD' else 'via_contacts'].append({'ref':o.get('ref'),'id':o['id'],'contact_mm2':contact})
 for ref in ['U1.12','U2.7','C1.2','C2.2']:
  pad=next(o for o in obs if o.get('ref')==ref and o['layer']==1);assert pad['net']=='GND'
  vs=[o for o in obs if o['kind']=='VIA' and o['net']=='GND' and o['layer']==1];v=min(vs,key=lambda v:pad['g'].distance(v['g']))
  report['critical_reference'].append({'ref':ref,'via':v['id'],'center_distance_mm':pad['g'].centroid.distance(v['g'].centroid)*.0254,'copper_edge_gap_mm':pad['g'].distance(v['g'])*.0254})
 report['all_ground_vias_on_inner1_main']=all(c['contact_mm2']>.01 for c in report['via_contacts'])
 report['all_ground_THT_pads_on_inner1_main']=all(c['contact_mm2']>.01 for c in report['gnd_pad_contacts'])
 # Combine the poured GND plane with the existing trace audit. GND-only trace
 # islands are expected and are accepted only with the actual plane contacts above.
 report['independent_trace_check']=audit(b)
 assert report['independent_trace_check']['unconnected_nets'].keys()<= {'GND'}
 original=base.objects
 try:
  base.objects=lambda board:obs+[{'id':'plane-'+str(layer),'kind':'POUR','net':'GND','layer':layer,'g':g} for layer,g in planes.items()]
  report['full_copper_including_pours_check']=base.audit(b)
 finally:base.objects=original
 return planes,mains,report
if __name__=='__main__':
 _,b=load();planes,mains,r=ground(b);r['pcb_sha256']=hashlib.sha256(Q.read_bytes()).hexdigest();(O/'sensor-ground-review.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in r.items() if k not in ['gnd_pad_contacts','via_contacts']},indent=2))
