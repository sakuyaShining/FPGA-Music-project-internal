"""Prepare open-item, harness and channel contracts; never manufacture output substitutes."""
import csv
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
def write(name,rows):
    with (ROOT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

rows=[]
module_maps={
 'J11':{1:'1 VCC; 5V only with regulator bypass J1 OPEN',2:'2 GND',3:'7 SCK',4:'6 MOSI',5:'3 CS',6:'5 DC',7:'4 RESET',8:'8 LED/BL',9:'NC',10:'NC',11:'NC',12:'2 GND return; harness join requires crimp review'},
 'J10':{1:'3/4 VDD (5V configuration); verify actual 40-pin header',2:'1/2 GND',3:'8 SCLK',4:'7 SDI',5:'6 SDO',6:'5 /SCS',7:'11 /RESET; V4 label ambiguity, verify actual board',8:'34 CTP_SDA',9:'35 CTP_SCL',10:'33 CTP_INT',11:'36 CTP_RESET_N; verify RC reset variant',12:'39/40 GND'}
}
for p in design['parts']:
    if p['ref'].startswith('J'):
        for pin,net in p['nets'].items():
            rows.append(dict(reference=p['ref'],pin=pin,net=net or 'NC',mpn=p['mpn'],
              meaning=p['role'],supplier_module_pin=module_maps.get(p['ref'],{}).get(int(pin),'N/A'),
              status=('primary_document_candidate_actual_revision_not_approved' if p['ref'] in module_maps else 'review_candidate_not_mating_approved')))
write('harness-contract.csv',rows)
harness_count=len(rows)
for count in [25,26]:
    rows=[]
    used=count*3+5
    for node in range(84):
        lane,addr=divmod(node,14)
        if node<count*3:
            slot,e=divmod(node,3);role=f'NOTE_SLOT_{slot:02}_E{e}'
        elif node<used:role=f'OCTAVE_NODE_{node-count*3}'
        else:role='SPARE'
        rows.append(dict(candidate_note_slots=count,logical_node=node,role=role,lane=lane,mux_address=addr,
            connector=f'J{20+lane}',connector_pin=addr+1,net=f'L{lane}_E{addr:02}',
            status='mapping_option_not_user_endpoint_decision'))
    write(f'electrode-map-{count}-OPTION.csv',rows)

open_items=[
 ('H01','screen_order','hold','7inch exact SPI4 + CTP version; product page says FT5316 while old interfacing sample says FT5206; touch points, IO voltage, MISO, native header drawing and domestic delivered price','Actual SKU configuration and corresponding datasheet; generic RA8875 or mixed-version samples are insufficient'),
 ('H02','small_screen','hold','MSP2401 exact board revision with 5V VCC regulator and 3.3V IO; visibility/view angle, price and cable mapping','Verified module drawing; J11 is our cable pinout, not vendor pinout'),
 ('H03','power','partially_implemented','V2 has PTC, reverse-polarity PMOS, TPS2553 current limit and power-domain I/O; actual adapter, load voltage, startup, off-state leakage and thermal remain unmeasured','Native schematic/pin audit completed; rail/sequence/short/full-load measurements still required; Nano J5.1 NC'),
 ('H04','mechanical','hold','Actual Nano revision, pin1 orientation, header row spacing, 7inch mounting, electrode cover; encoder generic electrical hole and rounded mounting-slot fit remain unapproved','Manufacturer drawings overlaid with footprints; physical fit check before board outline freeze; encoder row spacing 14.5mm confirmed'),
 ('H05','pcb','in_progress','230 devices/1054 pads mapped with zero differences; 21 test pads and 4 NPTH mounts implemented; routing, return paths, current ground pours and final DRC remain incomplete','Native routed DRC plus final Gerber/drill/mask/silkscreen review; initial drill export confirmed dimensions but is NOT FOR ORDER'),
 ('H06','assembly','hold','Current LCSC stock differs from JLC assembly/domestic stock; exact feeder classes, quote and substitutions','JLC matching report, assembly quote, native BOM and CPL from actual layout'),
 ('H07','sensor','pending_prototype','Touch delta, scan time, SNR, overlay/cable parasitic, leakage, ESD path and reference range','Small coupon calibration with actual overlay; no 1nF shunt assumption'),
 ('H08','firmware_capacity','hold_integration','Full dualscreen shared bus, RA readback, touch and PCM5122 startup not integrated; joint PnR failed in doc86','Real protocol wrapper + routing/timing pass; limited diagnostic results do not qualify full build'),
 ('H09','interaction','parameter_pending','25/26 note endpoints not selected; both maps provided and physical capacity84 maintained','User endpoint decision; neither option is silently selected'),
 ('H10','quote','hold','Historical 652.76CNY model does not include all present scope or fresh landed quotes','Current full RMB quote including both screens/CTP/cables/PCB/SMT/shipping'),
]
# This is an initial seed, not the maintained audit state. Re-running a harness
# generator must not silently erase later inventory, test and closure evidence.
if not (ROOT/'release-open-items.csv').exists():
    write('release-open-items.csv',[dict(id=i,area=a,status=s,remaining=r,closure_evidence=e) for i,a,s,r,e in open_items])
else:
    print('Preserved maintained release-open-items.csv; seed was not reapplied')
print('harness pins',harness_count,'open items',len(open_items))
