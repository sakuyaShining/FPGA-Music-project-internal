import json,hashlib
from sensor_ground import *
from shapely.geometry import Point
from gerber_geometry import gerber_regions
_,b=load();planes,_,_=ground(b)
export=gerber_regions(O/'gerber-inspection/Gerber_BottomLayer.GBL')
export_main=max(export.geoms,key=lambda p:p.area) if hasattr(export,'geoms') else export
obs=objects(b);checks=[]
for pad in obs:
 if pad['kind']=='PAD' and pad['layer']==2 and pad.get('net') and pad['net']!='GND':
  gap=pad['g'].distance(planes[2])*.0254
  actual_gap=scale(pad['g'],.0254,.0254,origin=(0,0)).distance(export_main)
  checks.append({'pad':pad.get('ref'),'net':pad['net'],'bottom_ground_gap_mm':gap,'actual_Gerber_main_ground_gap_mm':actual_gap,'retained_gate_mm':.1651,'passes_retained_gate':gap+1e-7>=.1651 and actual_gap+1e-7>=.1651})
out={'pcb_sha256':hashlib.sha256(Q.read_bytes()).hexdigest(),'retained_gate_mm':.1651,'generic_audit_gate_mm':5.98*.0254,'generic_audit_query_buffer_mm':6.3*.0254,'measure':'Exact frozen source pad geometry to actual production-optimized bottom ground copper reconstructed in sensor_ground.py; actual Gerber was separately proven bidirectionally equivalent within5um.','checks':checks,'retained_gate_failures':[p for p in checks if not p['passes_retained_gate']],'min_gap_mm':min(p['bottom_ground_gap_mm'] for p in checks)}
out['actual_Gerber_main_ground_min_gap_mm']=min(p['actual_Gerber_main_ground_gap_mm'] for p in checks)
(O/'retained-clearance-gate-audit.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='checks'},indent=2))
