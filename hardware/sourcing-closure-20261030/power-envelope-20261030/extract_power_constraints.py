from pathlib import Path
import json,zipfile,hashlib,collections,csv,io,sys
R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[3];D=Path(__file__).resolve().parent
Z=R/'hardware/delivery-baselines/20261029-r2-s1/control88-frozen-r2-20261029.zip';prefix='control88-frozen-r2-20261029/'
assert hashlib.sha256(Z.read_bytes()).hexdigest()=='24fe5ec56d973144bcdb217d0b1af5efbf2fd85d14ee655555ba9a2d41b1dcfd'
with zipfile.ZipFile(Z) as z:
 data=z.read(prefix+'source/pcb/PCB1.epcb2');bom={r['Designator']:r for r in csv.DictReader(io.StringIO(z.read(prefix+'manufacturing/Control88-R2-BOM.csv').decode('utf-8-sig')))}
assert hashlib.sha256(data).hexdigest()=='733e1d9c33d11ef946863dca0bc9f36ae2916b9965d038b147aafea416194eb8'
docs=[];cur=None
for line in data.decode('utf-8-sig').splitlines():
 if not line.strip():continue
 h,v=line.split('||',1);h=json.loads(h);v=v[:-1] if v.endswith('|') else v
 if not v.strip():continue
 v=json.loads(v)
 if h['type']=='DOCHEAD':cur={'head':v,'records':[]};docs.append(cur)
 cur['records'].append((h,v))
b=next(d for d in docs if d['head']['docType']=='PCB');attrs=collections.defaultdict(dict);component_attrs={h['id']:v.get('attrs',{}) for h,v in b['records'] if h['type']=='COMPONENT'};nets=collections.defaultdict(dict)
for h,v in b['records']:
 if h['type']=='ATTR':attrs[v['parentId']][v['key']]=v['value']
 elif h['type']=='PAD_NET':_,cid,num,padid=json.loads(h['id']);nets[cid][num]=v['padNet']
refs={a['Designator']:cid for cid,a in attrs.items() if 'Designator' in a}
parts={}
for ref in ['F1','Q1','U17','R67','U13','U18','J13','J10','J5','J6']:
 cid=refs[ref];parts[ref]={'MPN':bom[ref]['MPN'],'LCSC':bom[ref]['LCSC'],'pads':dict(nets[cid])}
assert parts['F1']['MPN']=='MF-MSMF110/16-2' and set(parts['F1']['pads'].values())=={'5V_IN','5V_FUSED'}
assert parts['U17']['MPN']=='TPS2553DBVR' and parts['U17']['pads']['1']=='5V_PROTECTED' and parts['U17']['pads']['6']=='5V_PERIPH'
assert parts['U17']['pads']['3']=='3V3_IO' and parts['U17']['pads']['5']=='PWR_ILIM'
assert parts['R67']['MPN']=='0603WAF2372T5E' and set(parts['R67']['pads'].values())=={'PWR_ILIM','GND'}
assert parts['J13']['pads']=={'1':'5V_IN','2':'GND'}
assert parts['J5']['pads']['1']==''
loads={rail:[] for rail in ['5V_IN','5V_FUSED','5V_PROTECTED','5V_PERIPH','3V3_IO','3V3_PERIPH','DAC_3V3']}
for ref,cid in refs.items():
 for pin,net in nets[cid].items():
  if net in loads:loads[net].append(ref+'.'+pin)
pdf=D/'Bourns-MF-MSMF-official.pdf';assert hashlib.sha256(pdf.read_bytes()).hexdigest()=='50d80228581842471d563e28ba0f1b67ab095ee95dfac4079f4a49f7f7bbf3c8'
temps=[23,40,50,60,70,85];holds=[1.10,.95,.87,.80,.71,.60]
candidate_C88_steady_A=.5
derating=[{'ambient_C':t,'F1_hold_A':h,'headroom_to_candidate_steady_A':round(h-candidate_C88_steady_A,3),'candidate_fraction_of_hold':round(candidate_C88_steady_A/h,4)} for t,h in zip(temps,holds)]
limits={'candidate_C88_J13_steady_current_allocation_A':candidate_C88_steady_A,'allocation_is_measurement':False,'allocation_origin':'Existing R2 IR-drop estimated load only; not a measured or guaranteed maximum','F1_hold_at_23C_A':1.1,'F1_hold_at_60C_A':.8,'F1_R1max_23C_ohm':.21,'F1_drop_at_candidate_and_R1max_V':round(.21*candidate_C88_steady_A,3),'drop_bound_is_all_temperature_guarantee':False,'TPS2553_previous_verified_limit_A':[1.002,1.184],'PSU_current_rating_is_not_board_path_current_rating':True,'Nano_USB_current_A':None,'all_machine_peak_current_A':None,'screen_complete_configuration_peak_A':None,'exact_domestic_PSU_SKU':None,'shipping_inclusive_price_CNY':None,'budget_accepted':False}
report={'schema':1,'status':'PARTIAL_SOURCE_AND_FUSE_TEMPERATURE_ENVELOPE_NOT_COMPLETE_LOAD_BUDGET','PCB_sha256':hashlib.sha256(data).hexdigest(),'parts':parts,'rail_incidence_not_load_currents':loads,'F1_derating':derating,'limits':limits,'sources':[{'url':'https://www.bourns.com/docs/product-datasheets/mf-msmf.pdf','sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'page_1based':9,'visual_review':'Confirmed non-X MF-MSMF110/16 row; do not use /16X row'},{'url':'https://www.ti.com/lit/ds/symlink/tps2553.pdf','revision_observed':'SLVS841G October2026','scope':'Original current limit retained; no threshold change'}],'open_items':['Actual Nano USB and Nano 3V3_IO maximum dynamic current at intended bitstream/scan rate','Exact screen variant steady/start-up current and complete touch wiring','Whole C88 protected branch start-up/transient including actual wiring voltage drop','Enclosure temperature, F1 heating and LDO thermal behavior','Domestic exact PSU product, two5V branches, polarity/current rating/voltage-drop of complete cables, shipped quote'],'manufacturing_release':False,'physical_power_acceptance':False}
(D/'POWER-CONSTRAINTS.json').write_bytes((json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode());print(json.dumps({'status':report['status'],'parts_checked':len(parts),'F1_derating':derating,'source_changed':False}))
