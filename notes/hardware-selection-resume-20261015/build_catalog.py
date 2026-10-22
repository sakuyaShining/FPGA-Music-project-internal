"""Bind explicit MPN+C-number choices to actual EasyEDA search results."""
import csv
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DEST=ROOT.parents[1]/'hardware/pitch-sliders/selection-20261015'


def main():
    rows=[]
    for name in ('prototype-state-and-library','library-exact-candidates','encoder-pullup-library',
                 'reference-capacitors-library','encoder-alternatives-library','passive-alternatives-library'):
        value=json.loads((ROOT/f'evidence/{name}.json').read_text(encoding='utf-8'))['value']
        for batch in value.values():
            if isinstance(batch,list): rows.extend(r for r in batch if isinstance(r,dict))
    # Quantities are engineering candidates for a 4-strip prototype and an
    # illustrative 8-lane full panel, NOT an approved complete purchase order.
    choices=[
        ('CD74HC4067M96','C496123',2,8,'raw electrode mux'),
        ('SN74LVC14ADR','C133541',1,2,'Schmitt input stage'),
        ('SN74LV595ADR','C205940',1,1,'latched address/enable/common RC drive'),
        ('SN74LV165ADR','C273656',1,1,'four presets/edit/encoder A B push'),
        ('24LC256-I/SN','C411625',1,1,'persistent preset storage'),
        ('EC11E15244B2','C470754',1,1,'push rotary encoder candidate'),
        ('TS-1187A-B-A-B','C318884',5,5,'four preset plus edit switch candidate'),
        ('0603WAF1001T5E','C21190',12,107,'1k electrode series; full qty is maximum illustrated raw nodes'),
        ('RC0603FR-0747KL','C105579',2,8,'47k initial RC load; NOT sensor-qualified'),
        ('RC0603FR-07220RL','C107696',2,8,'220R sense output series'),
        ('RC0603FR-0710KL','C98220',5,5,'10k tactile input pull-up'),
        ('0603WAF4701T5E','C23162',3,3,'4k7 I2C pair plus encoder switch pull-up'),
        ('0603WAF2201T5E','C4190',2,2,'2k2 encoder A/B pull-up candidate'),
        ('CL10B104KB8NNNC','C1591',6,13,'100nF IC decoupling'),
        ('CL10A105KO8NNNC','C1592',2,4,'1uF local bulk candidate'),
        ('CL10C100JB8NNNC','C1634',2,8,'10pF C0G reference'),
        ('GRM1885C1H470JA01D','C71652',2,0,'47pF C0G prototype comparison only; domestic stock pending'),
        ('CL10C101JB8NNNC','C14858',2,8,'100pF C0G reference'),
    ]
    selected=[]
    for mpn,code,small,full,role in choices:
        matches=[r for r in rows if r.get('manufacturerId')==mpn and r.get('supplierId')==code]
        assert matches,(mpn,code)
        device=matches[0]
        assert all(device.get(k) for k in ('uuid','libraryUuid','symbolUuid','footprintUuid'))
        datasheet=device.get('otherProperty',{}).get('Datasheet','')
        linked_codes=re.findall(r'C\d+',datasheet)
        selected.append({'mpn':mpn,'lcsc':code,'prototype_quantity':small,'full_example_quantity':full,
            'role':role,'manufacturer':device.get('manufacturer'),'libraryUuid':device['libraryUuid'],
            'deviceUuid':device['uuid'],'symbolUuid':device['symbolUuid'],'footprintUuid':device['footprintUuid'],
            'footprintName':device.get('footprintName'),'datasheet_library_reference':datasheet,
            'datasheet_other_C_codes':[c for c in linked_codes if c!=code],
            'library_identity':'checked_exact_mpn_and_c','electrical_qualification':'pending_prototype',
            'domestic_unit_price_cny':None,'manufacturing_release':False})
    DEST.mkdir(parents=True,exist_ok=True)
    (DEST/'catalog-checked.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for name,key in [('prototype-bom-import.csv','prototype_quantity'),('full-example-bom-import.csv','full_example_quantity')]:
        with (DEST/name).open('w',newline='',encoding='utf-8-sig') as output:
            writer=csv.writer(output);writer.writerow(['LCSC Part Number','Manufacturer Part Number','Quantity','Role','Status'])
            for p in selected:
                if p[key]>0:writer.writerow([p['lcsc'],p['mpn'],p[key],p['role'],'REVIEW ONLY - NOT COMPLETE BOM'])
    pages=[]
    for p in selected:
        # Public product route is obtained from the library's actual datasheet link.
        match=re.search(r'item\.szlcsc\.com/datasheet/.+/(\d+)\.html',p['datasheet_library_reference'])
        if match:pages.append({'mpn':p['mpn'],'lcsc':p['lcsc'],'url':f'https://item.szlcsc.com/{match[1]}.html'})
    (ROOT/'domestic-pages.json').write_text(json.dumps(pages,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'exact_identity_checked':len(selected),'domestic_routes':len(pages),'destination':str(DEST)}))


if __name__=='__main__':main()
