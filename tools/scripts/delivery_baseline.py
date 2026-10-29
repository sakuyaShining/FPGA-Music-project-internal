"""Verify the delivery checkpoint bytes and explicit production holds.

Standard library only. Does not certify DFM, rerun CAD or qualify firmware.
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, io, json, zipfile

ROOT=Path(__file__).resolve().parents[2]
def digest(data): return hashlib.sha256(data).hexdigest()
def relative(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
        raise ValueError('Unsafe path: '+name)
    return Path(*p.parts)
def verify_zip(data, expected_files=None):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None
        names=[n for n in z.namelist() if not n.endswith('/')]
        assert len(names)==len(set(names)), 'Duplicate ZIP member'
        for n in names: relative(n)
        if expected_files is not None:
            for n,v in expected_files.items():
                assert digest(z.read(n))==v['sha256'],n
            assert set(names)==set(expected_files)|{'SOURCE-MANIFEST.json'}
        else:
            manifests=[n for n in names if n.endswith('/MANIFEST.json') or n=='MANIFEST.json']
            assert len(manifests)==1
            mn=manifests[0];m=json.loads(z.read(mn));prefix=mn[:-len('MANIFEST.json')]
            for n,h in m['files_sha256'].items():
                relative(n)
                assert digest(z.read(prefix+n))==h,n
        return z.namelist()
def check(root=ROOT):
    pointer=json.loads((root/'project/delivery-baseline.json').read_text(encoding='utf-8'))
    mp=root/relative(pointer['manifest']);m=json.loads(mp.read_text(encoding='utf-8'));base=mp.parent
    for n,v in m['files'].items():
        p=base/relative(n)
        assert p.is_file() and p.stat().st_size==v['bytes'] and digest(p.read_bytes())==v['sha256'],n
    assert m['finished_board_quantities']=={'Control88_R2':1,'Sensor14Bank_S1':6}
    assert m['net_quantities']=={'unique_C_numbers':38,'parts':256,'SMT':232,'TH':24}
    assert m['complete_product_accepted'] is False and m['paid'] is False and m['order_submitted'] is False
    assert m['status']==pointer['status']=='RECOVERABLE_CHECKPOINT_SENSOR_STRICT_CLEARANCE_FAB_HOLD'
    audit=json.loads((base/'evidence/retained-clearance-gate-audit.json').read_text(encoding='utf-8'))
    assert len(audit['retained_gate_failures'])==22
    assert audit['actual_Gerber_main_ground_min_gap_mm']<audit['retained_gate_mm']
    assert 'sensor_Gerber_22PAD_strict_0p1651mm_clearance_repair_and_reexport' in m['open_gates']
    for name in ['control88-frozen-r2-20261029.zip','sensor14-frozen-s1-20261029.zip','factory-handoff-20261029.zip']:
        verify_zip((base/name).read_bytes())
    q=json.loads((base/'Q4-SOURCE-CAPTURE.json').read_text(encoding='utf-8'))
    verify_zip((base/'Q4-FIRMWARE-SOURCE-RECOVERY-NOT-QUALIFIED.zip').read_bytes(),q['files'])
    with zipfile.ZipFile(base/'factory-handoff-20261029.zip') as z:
        for n in z.namelist():
            if '/99-Frozen-sources-and-evidence/' in n and n.endswith('.zip'):
                data=z.read(n);verify_zip(data)
                assert data==(base/Path(n).name).read_bytes(),n
    return {'status':'PASS_CHECKPOINT_INTEGRITY','baseline_id':m['id'],'files':len(m['files']),'Q4_recovery_inputs':len(q['files']),'sensor_production_hold':True,'supplier_acceptance':False,'complete_product_acceptance':False,'meaning':'Archive/source identity and correctly retained hold only; not manufacturing or functional sign-off'}
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);args=ap.parse_args()
    print(json.dumps(check(args.root),ensure_ascii=True,indent=2))
