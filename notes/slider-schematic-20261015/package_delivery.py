"""Package actual native files, verify BOM and image signatures, retain hashes."""
import csv
import hashlib
import io
import json
import shutil
import struct
import zipfile
from phase import ROOT,REPO,PROJECT

DEST=REPO/'hardware/pitch-sliders/prototype-schematic-20261015'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    audit=json.loads((ROOT/'connectivity-audit.json').read_text(encoding='utf-8'))
    assert audit['mismatches']==0 and audit['native_drc']==[]
    assert audit['sources']['native-protel.net']==sha(ROOT/'native-protel.net'),'Stale connectivity audit'
    drc=json.loads((ROOT/'evidence/native-schematic-drc.json').read_text(encoding='utf-8'))['value']
    assert drc==[],'Latest native DRC is not clean'
    DEST.mkdir(exist_ok=True)
    exports=PROJECT/'schematic-draft-exports'
    with zipfile.ZipFile(exports/'prototype-schematic.zip') as z:
        assert z.testzip() is None
        members=z.namelist(); assert len(members)==3
        for i,(member,key) in enumerate(zip(members,['core','electrodes','interface'])):
            data=z.read(member);assert data[:8]==b'\x89PNG\r\n\x1a\n'
            width,height=struct.unpack('>II',data[16:24]);assert width==3000 and height>2000
            (DEST/f'0{i+1}-{key}.png').write_bytes(data)
    catalog=json.loads((REPO/'hardware/pitch-sliders/selection-20261015/catalog-checked.json').read_text(encoding='utf-8'))
    identities={x['lcsc']:x['mpn'] for x in catalog}
    connector=json.loads((ROOT/'connector-candidate.json').read_text(encoding='utf-8'))
    identities[connector['supplierId']]=connector['manufacturerId']
    expected={};expected_refs={}
    for name in ['placed-rc','placed-support']:
        for p in json.loads((ROOT/f'evidence/{name}.json').read_text(encoding='utf-8'))['value']['made']:
            assert identities[p['lcsc']]==p['mpn']
            expected_refs[p['ref']]=(p['lcsc'],p['mpn'])
    original=json.loads((REPO/'notes/hardware-selection-resume-20261015/evidence/final-pin-readback.json').read_text(encoding='utf-8'))['value']['parts']
    for p in original:
        assert identities[p['lcsc']]==p['mpn']
        expected_refs[p['ref']]=(p['lcsc'],p['mpn'])
    expected_refs['J2']=(connector['supplierId'],connector['manufacturerId'])
    for lcsc,mpn in expected_refs.values():expected[lcsc]=expected.get(lcsc,0)+1
    raw=(exports/'prototype-bom.tsv').read_bytes()
    bom=list(csv.DictReader(io.StringIO(raw.decode('utf-16')),delimiter='\t'))
    assert len(bom)==19 and sum(int(r['Quantity']) for r in bom)==53
    assert {r['Supplier Part']:int(r['Quantity']) for r in bom}==expected
    for r in bom:assert identities[r['Supplier Part']]==r['Manufacturer Part']
    with (DEST/'prototype-bom.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=bom[0].keys());w.writeheader();w.writerows(bom)
    (DEST/'prototype-bom-native-utf16.tsv').write_bytes(raw)
    for source,target in [('native-protel.net','prototype-native.net'),('pin-net-audit.csv','pin-net-audit.csv'),('connectivity-audit.json','connectivity-audit.json'),('expected-pin-nets.json','expected-pin-nets.json')]:shutil.copyfile(ROOT/source,DEST/target)
    with zipfile.ZipFile(DEST/'EasyEDA-prototype-project.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in PROJECT.rglob('*'):
            if p.is_file() and not any('exports' in s for s in p.relative_to(PROJECT).parts):z.write(p,p.relative_to(PROJECT))
    with zipfile.ZipFile(DEST/'EasyEDA-prototype-project.zip') as z:assert z.testzip() is None
    fs=27000000/512;rate=fs*2
    capacity={'source':'Native engine 27MHz/512, mono signed PCM16; capacity arithmetic only',
              'sample_rate_numerator':27000000,'sample_rate_denominator':512,'bytes_per_second':rate,
              'five_minutes_ideal_bytes':rate*300,'five_minutes_MiB':rate*300/2**20,
              'eeprom_32KiB_ideal_seconds':32768/rate,'sdram_8MiB_ideal_seconds':2**23/rate,
              'record_ring_256KiB_ideal_seconds':2**18/rate,
              'onboard_tf_reserved_package_pins':{'DAT2':80,'DAT3_CS':81,'CMD_MOSI':82,'CLK':83,'DAT0_MISO':84,'DAT1':85},
              'duration_requirement':'pending_user_answer; five minutes is proposal, not freeze',
              'additional_card_budget_cny':30,'existing_reserve_after_card_cny':30,'total_budget_goal_cny':500,
              'actual_quote_complete':False,'resource_fit_verified':False}
    (DEST/'recording-capacity-plan.json').write_text(json.dumps(capacity,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    receipt={'status':'部分实现','native_component_count':53,'native_bom_skus':19,
             'pin_contract_count':231,'connected_pins':207,'intentional_nc':24,'nets':59,'native_drc_violations':0,
             'musical_engine_modified':False,'main_head':'fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',
             'main_baseline':'PASS 192 inputs','newest_engine_baseline':'PASS 246 inputs',
             'pre_edit_backup':str(ROOT/'evidence/before-schematic.zip'),
             'pre_edit_backup_sha256':sha(ROOT/'evidence/before-schematic.zip'),
             'manufacturing_release':False,
             'unverified':['ESD/protection qualification','electrode coupon footprints and geometry','physical Nano header and board revision','encoder and switch mechanical/electrical drawing qualification','resource fit of SD/SDRAM/filesystem/score UI','record/play functionality','physical RC noise/position/latency','PCB/DRC/quotation'],
             'files':{p.name:sha(p) for p in DEST.iterdir() if p.is_file() and p.name!='delivery-receipt.json'}}
    (DEST/'delivery-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'bom_skus':len(bom),'components':sum(int(x['Quantity']) for x in bom),'project_sha256':sha(DEST/'EasyEDA-prototype-project.zip'),'five_min_MiB':capacity['five_minutes_MiB']},ensure_ascii=True))

if __name__=='__main__':main()
