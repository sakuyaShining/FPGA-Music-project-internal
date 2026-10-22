"""Generate auditable hardware candidates, not a production pinout or firmware."""
import csv
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
OUT=REPO/'hardware/system-candidate-20261015'
OUT.mkdir(exist_ok=True)

def csvfile(name,rows):
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

# Copied from the visually inspected J5/J6 symbols, official 3921 rev1.30 p2.
headers={'J6':{1:73,2:74,3:75,4:85,5:77,6:15,7:16,8:27,9:28,10:25,
               11:26,12:29,13:30,14:31,15:17,16:20,17:19,18:18},
         'J5':{3:76,4:80,5:42,6:41,7:56,8:54,9:51,10:48,11:55,12:49,
               13:86,14:79,17:72,18:71,19:53,20:52}}
header_lookup={pin:(h,index) for h,entries in headers.items() for index,pin in entries.items()}
clean={25,26,27,28,29,30,31,41,42,48,77}
led=set(range(15,21))
reserved={4,5,6,7,8,9,10,11,13,51,52,53,54,55,56,57,59,60,61,62,69,70,
          71,72,73,74,75,76,79,80,81,82,83,84,85,86,87,88}
signals=[('BUS_SCK',27,'out'),('BUS_MOSI',15,'out'),('SCAN_LATCH',16,'out'),
         ('INPUT_LOAD_N',17,'out'),('INPUT_DATA',28,'in'),
         ('SENSE_0',29,'in'),('SENSE_1',30,'in'),('SENSE_2',31,'in'),
         ('SENSE_3',41,'in'),('SENSE_4',42,'in'),('SENSE_5',48,'in'),
         ('STORE_SDA',25,'open_drain'),('STORE_SCL',26,'open_drain'),
         ('LCD_VIS_CS_N',18,'out'),('LCD_HARM_CS_N',19,'out'),
         ('LCD_SHARED_DC',20,'out'),('TP_INT',77,'bidir_at_reset_then_in')]
pins=[]
for signal,pin,direction in signals:
    h,pos=header_lookup[pin]
    pins.append(dict(signal=signal,fpga_package_pin=pin,board_header=h,board_header_pin=pos,
                     logic_voltage='3.3V',direction=direction,
                     existing_load='onboard_LED_510ohm' if pin in led else 'LCD_FPC_net; RGB_LCD_unplugged',
                     status='candidate_not_for_connection_until_board_and_wrapper_check'))
csvfile('nano-header-candidate.csv',pins)

shift=[dict(bit=i,signal=n,role=role,existing_prototype=('already_used' if i<6 else 'was_NC_needs_revision'))
       for i,n,role in [(0,'MUX_A0','address'),(1,'MUX_A1','address'),(2,'MUX_A2','address'),
                        (3,'MUX_A3','address'),(4,'MUX_EN_N','disable high'),(5,'RC_DRIVE','measurement'),
                        (6,'LCD_COMMON_RST_N','reset both displays'),(7,'TP_RST_N','touch reset')]]
csvfile('shift595-candidate.csv',shift)

wave=[('TP_RST',1,'595_Q7','3.3V'),('TP_INT',2,'TP_INT','3.3V'),
      ('TP_SCL',3,'STORE_SCL','3.3V'),('TP_SDA',4,'STORE_SDA','3.3V'),
      ('LCD_BL',5,'candidate_fixed_3V3_through_10k','3.3V; check module current'),
      ('LCD_RST',6,'595_Q6','3.3V; R21 fit check'),('LCD_DC',7,'LCD_SHARED_DC','3.3V'),
      ('LCD_CS',8,'LCD_HARM_CS_N','3.3V'),('SCLK',9,'BUS_SCK','3.3V'),
      ('MOSI',10,'BUS_MOSI','3.3V'),('MISO',11,'NC_write_only_LCD','module output; not tied to GND'),
      ('GND',12,'GND','0V'),('VCC',13,'5V_SOURCE','5V power; not GPIO')]
csvfile('waveshare-30896-interface.csv',[dict(module_pin=p,module_signal=s,host_signal=h,electrical_note=e,
    status='conditional_on_actual_module_revision') for s,p,h,e in wave])

capacity=[]
for count in (25,26):
    nodes=[(f'SLOT_{slot:02d}_E{e}','pitch') for slot in range(count) for e in range(3)]
    nodes += [(f'OCT_NODE_{i}','octave_position_only') for i in range(5)]
    mapping=[dict(node=name,role=role,lane=i%6,mux_address=i//6,
                  state='allocation_example_no_frozen_music_note_or_geometry') for i,(name,role) in enumerate(nodes)]
    mapping += [dict(node=f'REF_{lane}_{pf}pF',role='calibration',lane=lane,mux_address=a,
                     state='experimental_value') for lane in range(6) for a,pf in [(14,10),(15,100)]]
    csvfile(f'electrodes-{count}-slot-example.csv',mapping)
    active=[m for m in mapping if m['role']!='calibration']
    capacity.append({'slots':count,'pitch_nodes':count*3,'octave_nodes_example':5,'active_nodes':len(active),
                     'lanes':6,'available_sensing_addresses':84,'spare_sensing_addresses':84-len(active),
                     'all_addresses_unique':len({(m['lane'],m['mux_address']) for m in mapping})==len(mapping),
                     'active_addresses_below_reserved':all(m['mux_address']<14 for m in active)})

proto=list(csv.DictReader((REPO/'hardware/pitch-sliders/prototype-schematic-20261015/prototype-bom.csv').open(encoding='utf-8-sig')))
full={'C1591':10,'C1592':1,'C1634':6,'C71652':0,'C14858':6,'C247920':None,
      'C105579':6,'C107696':6,'C21190':80,'C4190':2,'C23162':3,'C98220':7,
      'C470754':1,'C318884':5,'C496123':6,'C133541':1,'C205940':1,'C273656':1,'C411625':1}
refresh={r['lcsc']:r for r in json.loads((ROOT/'evidence/domestic-refresh.json').read_text(encoding='utf-8'))}
bom=[]
for p in proto:
    code=p['Supplier Part'];q=full[code]
    bom.append(dict(role=p['Comment'],manufacturer=p['Manufacturer'],mpn=p['Manufacturer Part'],lcsc=code,
                    prototype_fitted_qty=int(p['Quantity']),full_25_example_qty='' if q is None else q,
                    full_26_example_qty='' if q is None else q+(3 if code=='C21190' else 0),
                    current_domestic_stock=refresh.get(code,{}).get('stock',''),
                    unit_price_cny='',quote_status='pending',
                    note=('full connector topology unknown; do not multiply prototype connector' if q is None else
                          '47pF belongs to three-reference prototype only' if q==0 else
                          'adds two CS pullups; not yet in native schematic' if code=='C98220' else
                          'candidate quantity; physical validation pending')))
extras=[
 ('right display','Waveshare','3.5inch RPi LCD (F)','',1,1,'SKU30896; manufacturer search index CNY107.06 only; no stock/checkout proof'),
 ('per-electrode ESD primary candidate','TI','TPD1E01B04DPYR','C779389',80,83,'native exact identity; price and installed protection pending'),
 ('per-electrode ESD alternative','TECH PUBLIC','TPD1E01B04DPYR-TP','C2858691',80,83,'alternative to TI, not additional; package conflict unresolved'),
 ('recording media','','microSDHC 16/32GB candidate','',1,1,'exact MPN, busy-time qualification and price pending'),
 ('power input','','5V 2A minimum planning target','',1,1,'conditional purchase if no suitable existing source; no dual-source backfeed'),
 ('electrode PCB','','two octave rows plus octave selector','',1,1,'geometry and fabrication quote pending'),
 ('core/carrier PCB','','six RC lanes with controls and display interfaces','',1,1,'prototype/final quantities and fabrication quote pending'),
 ('cover/mounts/knob caps/cables','','mechanical accessories','',1,1,'not included in electronics unit quotes'),
 ('assembly and freight','','manufacturing services','',1,1,'quote pending; no free coupon assumption'),
]
for role,mfr,mpn,code,q25,q26,note in extras:
    bom.append(dict(role=role,manufacturer=mfr,mpn=mpn,lcsc=code,prototype_fitted_qty=0,
                    full_25_example_qty=q25,full_26_example_qty=q26,
                    current_domestic_stock=refresh.get(code,{}).get('stock',''),unit_price_cny='',
                    quote_status='pending',note=note))
csvfile('system-bom-candidate.csv',bom)

profile={'status':'discussion_not_implementation_or_manufacturing_release','reference_board':'3921 rev1.30',
         'profile':'17_GPIO_shared_DC_and_LCD_reset_via_595',
         'gpio_count':len(pins),'unique_pin_count':len({p['fpga_package_pin'] for p in pins}),
         'all_pins_on_actual_headers':all(p['fpga_package_pin'] in header_lookup for p in pins),
         'all_pins_in_reviewed_3V3_groups':all(p['fpga_package_pin'] in clean|led for p in pins),
         'reserved_pin_overlap':sorted({p['fpga_package_pin'] for p in pins}&reserved),
         'LED_pins_repurposed':sorted({p['fpga_package_pin'] for p in pins}&led),
         'fast_signal_on_LED_pin':'BUS_MOSI pin15; waveform/loading unverified',
         'capacity_examples':capacity,'system_bom_rows':len(bom),
         'quote_closed':False,'touch_latency_verified':False,'board_revision_matched_to_user':False,
         'physical_display_pinout_known':False,'prototype_speaker_user_report':{'ohms':4,'rated_watts':3},
         'engine_RTL_changed':False,'native_schematic_changed':False,'purchased':False}
assert profile['unique_pin_count']==17 and not profile['reserved_pin_overlap']
assert all(x['all_addresses_unique'] and x['active_addresses_below_reserved'] for x in capacity)
old=json.loads((REPO/'notes/right-touch-selection-20261015/evidence/project-before-readonly.json').read_text(encoding='utf-8'))
project=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Slider-Prototype-20261015')
profile['native_project_changed_files']=[name for name,h in old.items() if hashlib.sha256((project/name).read_bytes()).hexdigest()!=h]
assert not profile['native_project_changed_files']
(OUT/'audit.json').write_text(json.dumps(profile,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files=[p for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json']+[p for p in ROOT.rglob('*') if p.is_file()]
(OUT/'manifest.json').write_text(json.dumps({str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n',encoding='utf-8')
print(json.dumps(profile,ensure_ascii=True))
