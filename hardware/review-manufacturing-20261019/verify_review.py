"""Independent native connectivity, critical pin function and BOM audit."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from native_review import ROOT, ORIGINAL

def main():
    expected=json.loads((ROOT/'expected-pin-nets.json').read_text())
    design=json.loads((ROOT/'design.json').read_text(encoding='utf-8'))
    native=(ROOT/'native-protel.net').read_text(encoding='utf-8')
    actual={};groups={}
    for block in re.findall(r'^\(\s*\n(.*?)^\)',native,re.M|re.S):
        lines=[x.strip() for x in block.splitlines() if x.strip()]
        net=lines[0];groups[net]=[]
        for line in lines[1:]:
            token=line.split()[0];ref,pin=token.rsplit('-',1)
            assert ref in expected,('unexpected part',ref)
            assert (ref,pin) not in actual,('duplicate net',ref,pin)
            actual[ref,pin]=net;groups[net].append(token)
    rows=[];errors=[]
    for ref,pins in expected.items():
        for pin,net in pins.items():
            got=actual.get((ref,pin));match=got==net
            if not match:errors.append((ref,pin,net,got))
            rows.append(dict(reference=ref,pin=pin,expected=net or 'NC',native=got or 'NC',match=match))
    assert not errors,errors[:25]
    assert len(actual)==sum(n is not None for ps in expected.values() for n in ps.values())
    # Independently state a few source-critical contracts, instead of regenerating
    # pin intent from build_review.py. Nexperia / TI primary documents cited in README.
    critical={
      'U11':{'1':'KEY_QH','2':'GND','3':'RA_MISO','4':'BUS_RETURN','5':'3V3_IO','6':'HARM_CS_N'},
      'U12':{'1':'DAC_3V3','2':'DAC_CAPP','3':'GND','4':'DAC_CAPM','5':'DAC_VNEG',
        '8':'DAC_3V3','9':'GND','10':'GND','16':'GND','17':'GND','18':'DAC_3V3',
        '20':'GND','21':'I2S_BCK','22':'I2S_DIN','23':'I2S_LRCK','24':'GND','26':'DAC_LDOO','27':'GND','28':'DAC_3V3'},
      'J5':{'5':'SENSE_4','6':'SENSE_3','7':'I2S_BCK','8':'I2S_DIN','10':'SENSE_5','11':'I2S_LRCK','16':'3V3_IO'},
      'J6':{'5':'TP_INT','6':'BUS_MOSI','7':'SCAN_LATCH','8':'BUS_SCK','9':'BUS_RETURN','10':'I2C_SDA','11':'I2C_SCL',
        '12':'SENSE_0','13':'SENSE_1','14':'SENSE_2','15':'INPUT_LOAD_N','16':'VIS_DC','17':'HARM_CS_N','18':'VIS_CS_N'},
      'U13':{'1':'5V_PERIPH','2':'GND','3':'5V_PERIPH','4':None,'5':'DAC_3V3'},
      'U14':{'1':'3V3_IO','2':'I2C_SCL','3':'I2C_SDA','4':'GND','5':'3V3_PERIPH','6':'I2C_MOD_SDA','7':'I2C_MOD_SCL','8':'3V3_PERIPH'},
      'U15':{'1':'GND','19':'GND','10':'GND','20':'3V3_PERIPH','17':'3V3_IO','3':'VIS_BL_EN',
        '2':'BUS_SCK','18':'DISP_SCK','4':'BUS_MOSI','16':'DISP_MOSI',
        '6':'VIS_CS_N','14':'DISP_VIS_CS_N','8':'HARM_CS_N','12':'DISP_HARM_CS_N',
        '11':'VIS_DC','9':'DISP_VIS_DC','13':'LCD_RESET_N','7':'DISP_RESET_N','15':'TP_RESET_N','5':'TP_RESET_MOD_N'},
      'U16':{'1':None,'2':'TP_INT_MOD','3':'GND','4':'TP_INT','5':'3V3_IO'},
      'U17':{'1':'5V_PROTECTED','2':'GND','3':'3V3_IO','4':'PWR_FAULT_N','5':'PWR_ILIM','6':'5V_PERIPH'},
      'Q1':{'1':'PWR_GATE','2':'5V_PROTECTED','3':'5V_FUSED'},
      'J13':{'1':'5V_IN','2':'GND'},
      'R71':{'1':'3V3_PERIPH','2':'GND'},
      'R72':{'1':'DAC_3V3','2':'GND'},
      'R73':{'1':'3V3_IO','2':'GND'},
      'U18':{'1':'5V_PERIPH','2':'GND','3':'5V_PERIPH','4':None,'5':'3V3_PERIPH'}
    }
    for ref,pins in critical.items():
        for pin,net in pins.items():assert actual.get((ref,pin))==net,(ref,pin,net)
    for i in range(1,7):
        for pin,net in {'1':f'RC{i-1}','10':'ADDR0','11':'ADDR1','14':'ADDR2','13':'ADDR3','12':'GND','15':'MUX_DISABLE','24':'3V3_IO'}.items():
            assert actual.get((f'U{i}',pin))==net
    for i in range(1,25):
        for pin in ('6','7','9','10'):assert (f'D{i}',pin) not in actual,'TI NC must not be an ESD connection'
        for pin in ('3','8'):assert actual[f'D{i}',pin]=='GND'
    assert 'DAC_3V3'!=actual['J5','16']
    assert ('J5','1') not in actual,'Do not silently parallel USB and 5V_SYS'
    assert actual['J10','1']==actual['J11','1']=='5V_PERIPH'
    assert actual['J11','8']=='VIS_BL_EN'
    assert actual['U12','11']=='I2C_MOD_SDA' and actual['U12','12']=='I2C_MOD_SCL'
    assert '5V_SYS' not in groups,'Unprotected legacy rail must not survive v2'
    assert actual['R67','1']=='PWR_ILIM' and actual['R67','2']=='GND'
    assert next(p for p in design['parts'] if p['ref']=='R67')['code']=='C22912'
    for net in ['DAC_3V3','3V3_PERIPH','3V3_IO']:
        assert net in groups
    for lane in range(6):
        for addr in range(14):
            net=f'L{lane}_E{addr:02}'
            assert len(groups[net])==3,(net,groups[net]) # connector, resistor, TVS IO
    # Compare native BOM grouped designators against every physically placed part.
    bom=list(csv.DictReader((ROOT/'native-bom.tsv').open(encoding='utf-8'),delimiter='\t'))
    refcol=next((k for k in bom[0] if k.lower() in ['designator','designators'] or k in ['位号']),None)
    assert refcol,('native BOM headers',list(bom[0]))
    native_refs=[r.strip() for row in bom for r in row[refcol].split(',') if r.strip()]
    assert Counter(native_refs)==Counter(p['ref'] for p in design['parts']),'Native BOM ref mismatch'
    intended={p['ref']:p for p in design['parts']}
    for row in bom:
        for ref in [x.strip() for x in row[refcol].split(',') if x.strip()]:
            assert row['Supplier Part']==intended[ref]['code'],('Native supplier code mismatch',ref,row['Supplier Part'],intended[ref]['code'])
            assert row['Footprint']==intended[ref]['footprint'],('Native footprint mismatch',ref)
    # Preserve evidence from the original four-strip project.
    manifest=json.loads((ROOT/'evidence/original-manifest.json').read_text())
    changes=[p for p,h in manifest.items() if not (ORIGINAL/p).exists() or hashlib.sha256((ORIGINAL/p).read_bytes()).hexdigest()!=h]
    assert not changes,('Original was changed',changes)
    with (ROOT/'pin-net-audit.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result={'scope':'Native exported connectivity / BOM / critical source pin contracts only; NOT physical or production verification',
        'components':len(expected),'pins':len(rows),'connected_pins':len(actual),'intentional_nc':len(rows)-len(actual),
        'nets':len(groups),'mismatches':len(errors),'native_bom_refs':len(native_refs),'original_project_unchanged':True,
        'critical_pin_contracts':'PASS','native_drc':json.loads((ROOT/'native-drc.json').read_text(encoding='utf-8')),
        'fabrication_release':False,'pcb_evidence':'See separate pcb-pad-audit.json and pcb-drc.json; this audit checks the schematic',
        'hashes':{n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['design.json','native-protel.net','expected-pin-nets.json','native-bom.tsv','pin-net-audit.csv']}}
    (ROOT/'connectivity-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
