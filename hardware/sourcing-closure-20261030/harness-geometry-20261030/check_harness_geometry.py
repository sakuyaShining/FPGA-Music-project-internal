from pathlib import Path
import json,csv,math,sys,hashlib
R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[3];D=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'hardware/electrode-fullpanel-cam-20261030/verification/support'))
from native_documents import documents
EP=R/'hardware/electrode-fullpanel-cam-20261030/Electrode84-450-CANDIDATE/pcb/Electrode84-450.epcb2'
S2=R/'hardware/sensor14-s2-20261030/Sensor14Bank-S2-CANDIDATE/pcb/PCB2.epcb2'
M=R/'hardware/electrode-fullpanel-cam-20261030/assembly/MECHANICAL-CANDIDATE.json'
H=R/'hardware/electrode-fullpanel-cam-20261030/assembly/HARNESS-96-PINS.csv'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(EP)=='b7e9ecb16e4ea0141e8bf67e942ae228f7d2daf6d877422ee6b835a3f779530a'
assert sha(S2)=='9e4b563e570f2247785a764dd4ceba188b41ed8def3ba1511d456148fbd88bee'
def pads(path):
 ds=documents(path);libs={d['head']['uuid']:d for d in ds};b=next(d for d in ds if d['head']['docType']=='PCB');at={};out={}
 for h,v in b['records']:
  if h['type']=='ATTR':at.setdefault(v['parentId'],{})[v['key']]=v['value']
 for h,v in b['records']:
  if h['type']!='COMPONENT':continue
  ref=at[h['id']]['Designator']
  if not ref.startswith('J'):continue
  angle=math.radians(v['angle']);c,s=math.cos(angle),math.sin(angle);pp={}
  for hh,p in libs[at[h['id']]['Footprint']]['records']:
   if hh['type']!='PAD':continue
   # Both verified single-row footprints have all y=0, so their front/back
   # reflection about local X does not alter center coordinates.
   assert abs(p['centerY'])<1e-8
   pp[int(p['num'])]=[(v['x']+p['centerX']*c-p['centerY']*s)*.0254,(v['y']+p['centerX']*s+p['centerY']*c)*.0254]
  out[ref]={'pads':pp,'center':[v['x']*.0254,v['y']*.0254],'layer':v['layerId'],'angle':v['angle']}
 return out
ep=pads(EP);sensor=pads(S2);m=json.loads(M.read_bytes());sensors={v['bank']:v for v in m['sensors']}
offset=m['left_panel_rect_mm'][:2];epz=m['left_panel_top_z_mm']-m['left_panel_thickness_mm'];rows=[];banks=[]
def rotate_sensor(xy,b):
 x,y=xy[0]-27.5,xy[1]-22.5;t=math.radians(b['rotation_deg']);c,s=math.cos(t),math.sin(t)
 return [b['center_global_mm'][0]+c*x-s*y,b['center_global_mm'][1]+s*x+c*y]
for b in sensors.values():
 for ref in ['J1','J2']:
  g=rotate_sensor(sensor[ref]['center'],b)
  assert math.dist(g,b[ref+'_global_mm'])<.00001,(ref,g,b)
for row in csv.DictReader(H.open(encoding='utf-8-sig')):
 bank,pin=int(row['bank']),int(row['pin']);b=sensors[bank]
 ea=ep[f'JB{bank}']['pads'][pin];a=[ea[0]+offset[0],ea[1]+offset[1],epz]
 sb=rotate_sensor(sensor['J1']['pads'][pin],b);z=b['board_top_z_candidate_mm'];bb=[*sb,z]
 euclidean=math.dist(a,bb);height=m['two_mated_connector_height_allowance_each_mm']
 exits=[[a[0],a[1],a[2]-height],[bb[0],bb[1],bb[2]+height]]
 rows.append({'harness':row['harness'],'bank':bank,'pin':pin,'raw_index':row['raw_index'],'A_EP84_topview_x_mm':round(a[0],6),'A_EP84_topview_y_mm':round(a[1],6),'A_EP84_board_surface_z_mm':round(a[2],6),'B_S2_topview_x_mm':round(bb[0],6),'B_S2_topview_y_mm':round(bb[1],6),'B_S2_board_surface_z_mm':round(bb[2],6),'board_to_board_straight_lower_bound_mm':round(euclidean,6),'conditional_cable_exit_straight_lower_bound_mm':round(math.dist(*exits),6),'candidate_length_mm':int(row['length_mm_candidate']),'physical_length_acceptance':'PENDING_NO_ACTUAL_HOUSING_WIRE_BEND_SPEC'})
assert len(rows)==96
for bank in range(6):
 rr=[r for r in rows if r['bank']==bank];r1=next(r for r in rr if r['pin']==1);r16=next(r for r in rr if r['pin']==16)
 ad=r16['A_EP84_topview_x_mm']-r1['A_EP84_topview_x_mm'];bd=r16['B_S2_topview_x_mm']-r1['B_S2_topview_x_mm']
 banks.append({'bank':bank,'pin_order_opposes_in_common_top_view':ad*bd<0,'EP_pin1_xyz_mm':[r1[k] for k in ['A_EP84_topview_x_mm','A_EP84_topview_y_mm','A_EP84_board_surface_z_mm']],'S2_pin1_xyz_mm':[r1[k] for k in ['B_S2_topview_x_mm','B_S2_topview_y_mm','B_S2_board_surface_z_mm']],'max_board_straight_lower_bound_mm':max(r['board_to_board_straight_lower_bound_mm'] for r in rr),'max_exit_straight_lower_bound_mm_assuming_16mm_each':max(r['conditional_cable_exit_straight_lower_bound_mm'] for r in rr)})
assert all(b['pin_order_opposes_in_common_top_view'] for b in banks)
with (D/'HARNESS-96-PIN-GEOMETRY-CANDIDATE.csv').open('w',encoding='utf-8',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
report={'schema':1,'status':'PASS_SOURCE_DERIVED_COORDINATES_ONLY_NOT_HARNESS_FIT_ACCEPTANCE','source_hashes':{'EP84':sha(EP),'SensorS2':sha(S2),'mechanical_candidate':sha(M),'pin_contract':sha(H)},'all96_numbered_connections_preserved':True,'sensor_J1_J2_nominal_centers_match_native_transforms':True,'common_topview_pin_order_opposed_all6':True,'banks':banks,'largest_board_to_board_straight_lower_bound_mm':max(r['board_to_board_straight_lower_bound_mm'] for r in rows),'hypothetical_100mm_not_ruled_out_by_straight_distance_only':all(r['board_to_board_straight_lower_bound_mm']<r['candidate_length_mm'] for r in rows),'candidate_board_surface_gap_mm':epz-sensors[0]['board_top_z_candidate_mm'],'conditional_free_vertical_gap_after_two16mm_connectors_mm':epz-sensors[0]['board_top_z_candidate_mm']-32,'assumptions':['S2 55x45mm board center at27.5,22.5 rotated90 as candidate drawing','EP84 local source plus global9,17 offset; connector on Bottom','Six S2 assembly top z14 and EP underside z55.4 are candidate installation coordinates','16mm mating/strain relief allowance per end is a limit hypothesis, not an actual product dimension'],'open_items':['Exact female housing and terminal retention/height, wire diameter and minimum bend radius','Supplier definition of100mm: free wire length vs total assembly length and tolerance','Real face-on mating views: common top view reverses pin order but electrical contract remains1:1','Wire fanout/strain relief, cable bend envelope and sensor clamp obstruction','Complete six control-to-S2 J2 bundles also occupy the lower compartment'],'manufacturing_release':False,'physical_fit_accepted':False,'native_source_modified':False}
(D/'HARNESS-GEOMETRY-CHECK.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps(report,ensure_ascii=True))
