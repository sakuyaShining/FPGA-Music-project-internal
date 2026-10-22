"""Audit the actual saved sourcing sheet, BOM identities, and hardware budgets."""
import csv
import hashlib
import io
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
DEST=REPO/'hardware/pitch-sliders/selection-20261015'
PROJECT=Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Slider-Prototype-20261015')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects').resolve() in PROJECT.resolve().parents
    catalog=json.loads((DEST/'catalog-checked.json').read_text(encoding='utf-8'))
    by_code={p['lcsc']:p for p in catalog}
    parts=json.loads((ROOT/'evidence/final-pin-readback.json').read_text(encoding='utf-8'))['value']['parts']
    assert len(parts)==12 and len({p['ref'] for p in parts})==12
    expected_pins={'U1':24,'U2':24,'U3':14,'U4':16,'U5':16,'U6':8,'SW1':7,
                   **{f'SW{i}':4 for i in range(2,7)}}
    expected_quantities={}
    with (DEST/'pins-readback.csv').open('w',encoding='utf-8-sig',newline='') as output:
        writer=csv.writer(output);writer.writerow(['Reference','MPN','LCSC','Pin number','Pin name','X (10mil)','Y (10mil)'])
        for p in parts:
            assert p['lcsc'] in by_code and by_code[p['lcsc']]['mpn']==p['mpn']
            assert p['addBom'] is True and p['addPcb'] is False
            assert len(p['pins'])==expected_pins[p['ref']]
            assert len({pin['number'] for pin in p['pins']})==len(p['pins'])
            expected_quantities[p['lcsc']]=expected_quantities.get(p['lcsc'],0)+1
            for pin in p['pins']:
                writer.writerow([p['ref'],p['mpn'],p['lcsc'],pin['number'],pin['name'],pin['x'],pin['y']])
    native=PROJECT/'selection-review-exports/keyparts-unfiltered.csv'
    rows=list(csv.DictReader(io.StringIO(native.read_bytes().decode('utf-16')),delimiter='\t'))
    assert len(rows)==7
    actual={r['Supplier Part']:int(r['Quantity']) for r in rows}
    assert actual==expected_quantities
    for r in rows:assert r['Manufacturer Part']==by_code[r['Supplier Part']]['mpn']
    with (DEST/'keyparts-native-verified.csv').open('w',encoding='utf-8-sig',newline='') as output:
        writer=csv.DictWriter(output,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
    shutil.copyfile(native,DEST/'keyparts-native-original-utf16.tsv')
    image=PROJECT/'selection-review-exports/selection-review-full.png'
    raw=image.read_bytes();assert raw[:8]==b'\x89PNG\r\n\x1a\n'
    width,height=struct.unpack('>II',raw[16:24]);assert width>1100 and height>800
    shutil.copyfile(image,DEST/'selection-review.png')
    supply=[]
    for name in ['domestic-stock-catalog','passive-alternatives-domestic','encoder-domestic-stock','manual-domestic-stock']:
        path=ROOT/f'evidence/{name}.json'
        if path.exists():supply.extend(json.loads(path.read_text(encoding='utf-8')))
    stock={r['lcsc']:r for r in sorted(supply,key=lambda r:r.get('retrieved_at','')) if r['status']=='identity_checked_public_page'}
    with (DEST/'supply-review.csv').open('w',encoding='utf-8-sig',newline='') as output:
        writer=csv.writer(output);writer.writerow(['LCSC','MPN','Domestic stock field','Sales multiplier field','Minimum field','Actual unit price CNY','Status','Source'])
        for p in catalog:
            r=stock.get(p['lcsc']);ratio=None
            if r:
                assert r['mpn']==p['mpn']
                html=ROOT/f"evidence/{p['lcsc']}-domestic.html"
                assert sha(html)==r['html_sha256']
                payload=json.loads(re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',html.read_text(encoding='utf-8'),re.S)[1])
                ratio=payload['props']['pageProps']['webData']['productRecord'].get('theRatio')
            writer.writerow([p['lcsc'],p['mpn'],r.get('stock') if r else '',ratio if ratio else '',
                             r.get('minimum') if r else '', '',
                             'PUBLIC PAGE ONLY - PRICE UNQUOTED' if r else 'DOMESTIC STOCK/PRICE NOT VERIFIED',r.get('url') if r else ''])
    # Both illustrative 25/26-pitch versions fit with TWO reference addresses
    # per lane. Three per lane would overflow the 26-pitch example.
    node_cases=[]
    for pitches in (25,26):
        labels=[f'PITCH_{i+1}_E{e}' for i in range(pitches) for e in range(3)]
        labels += [f'OCTAVE_EXAMPLE_{i}' for i in range(5)]
        labels += [f'HARMONIC_EXAMPLE_{i+1}_E{e}' for i in range(8) for e in range(3)]
        mapping=[{'node':label,'lane':i%8,'address':i//8} for i,label in enumerate(labels)]
        assert max(row['address'] for row in mapping)<14
        mapping += [{'node':f'REFERENCE_{lane}_{cap}pF','lane':lane,'address':address}
                    for lane in range(8) for address,cap in [(14,10),(15,100)]]
        assert len({(r['lane'],r['address']) for r in mapping})==len(mapping)<=128
        case={'pitch_positions':pitches,'raw_nodes':len(labels),'reference_nodes':16,'occupied':len(mapping),
              'spare':128-len(mapping),'status':'ILLUSTRATIVE, NOT USER ENDPOINT/GEOMETRY FREEZE',
              'note':'Triplets may cross lanes; lane normalization and frame timing require prototype validation.'}
        node_cases.append(case)
        (DEST/f'channel-map-example-{pitches}.json').write_text(json.dumps({'summary':case,'map':mapping},indent=2)+'\n')
    budget=[('sense and expansion ICs',85),('passives protection connectors',50),('encoder switches knobs',30),
            ('prototype PCB',50),('full PCB allowance',95),('assembly soldering',60),('overlay fixing',40),
            ('shipping',30),('reserve',60)]
    assert sum(amount for _,amount in budget)==500
    (DEST/'budget-ceilings.json').write_text(json.dumps({'currency':'CNY','type':'PLANNING CEILINGS, NOT QUOTATION',
        'includes_prototype_and_later_hardware':True,'existing_Nano_screen_speaker_excluded':True,
        'lines':dict(budget),'total':500,'actual_cost':None,'order_submitted':False},indent=2)+'\n')
    archive=DEST/'eda-review-project.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in PROJECT.rglob('*'):
            if path.is_file() and 'selection-review-exports' not in path.parts:
                z.write(path,path.relative_to(PROJECT).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None;project_files=len(z.namelist())
    report={'status':'IDENTITY/READBACK AUDIT PASS, NOT MANUFACTURING RELEASE',
        'library_mpn_C_pairs':len(catalog),'placed_major_parts':12,'native_bom_skus':7,'native_bom_quantity':12,
        'readback_pins':sum(len(p['pins']) for p in parts),'image_dimensions':[width,height],
        'domestic_page_verified_selected_skus':sum(p['lcsc'] in stock for p in catalog),
        'unquoted_selected_skus':len(catalog),'project_files_in_zip':project_files,
        'project_path':str(PROJECT/(PROJECT.name+'.eprj3')),'node_cases':node_cases,
        'GPIO_signal_example':{'shared_sck_mosi':2,'595_latch':1,'165_load_and_data':2,'eight_sense_inputs':8,
                               'LCD_CS_DC_RESET':3,'EEPROM_SDA_SCL':2},
        'schematic_wires_complete':False,'ERC_PCB_DRC_done':False,'actual_touch_latency_verified':False,
        'budget_500_actual_quote_verified':False,'manufacturing_release':False}
    assert sum(report['GPIO_signal_example'].values())==18
    files=[p for p in DEST.iterdir() if p.is_file() and p.name!='review-audit.json']
    report['artifacts_sha256']={p.name:sha(p) for p in files}
    report['evidence_sha256']={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'evidence').glob('*.json')}
    report['scripts_sha256']={p.name:sha(p) for p in ROOT.glob('*.py')}
    (DEST/'review-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','library_mpn_C_pairs','placed_major_parts','readback_pins','domestic_page_verified_selected_skus','unquoted_selected_skus','manufacturing_release']}))


if __name__=='__main__':main()
