"""Validate handoff helpers in disposable workspaces. Never programs hardware."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys

HERE=Path(__file__).resolve().parent
P=Path('D:/FPGA-Project/codex-deliverables/fpga-agent-handoff-20261022-v1')
W1=Path('D:/FPGA-Project/codex-builds/fpga-handoff-validation-20261022-v1')
W2=Path('D:/FPGA-Project/codex-builds/fpga-handoff-validation-20261022-v2')
W3=Path('D:/FPGA-Project/codex-builds/fpga-handoff-validation-20261022-v3')
C=HERE.parents[1]/'experiments/nano20k_feasibility_20261021'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
J=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
ap=argparse.ArgumentParser();ap.add_argument('action',choices=('prepare','audit','finish'));a=ap.parse_args()
V=P/'validation';V.mkdir(exist_ok=True)
if a.action=='prepare':
    initial=V/'initial-assembly-manifest.json'
    assert not initial.exists();shutil.copyfile(P/'MANIFEST.json',initial)
    mapping=J(P/'source-map.json')
    updated=[]
    for p in HERE.rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts:continue
        rel=p.relative_to(HERE);dst=P/rel
        if dst.exists() and dst.read_bytes()==p.read_bytes():continue
        old=sha(dst) if dst.exists() else None
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,dst)
        updated.append(dict(path=rel.as_posix(),old_sha256=old,new_sha256=sha(dst)))
        mapping['original_inputs'][rel.as_posix()]=dict(path=str(p),sha256=sha(p))
    mapping['staging_helper_updates']=updated
    (P/'source-map.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run([sys.executable,str(HERE/'build_handoff.py'),'seal'],check=True)
    subprocess.run([sys.executable,str(P/'tools/bootstrap.py'),'--destination',str(W2)],check=True)
elif a.action=='audit':
    B=W3/'build_archived_baseline';assert not B.exists();shutil.copytree(P/'baseline_build',B)
    d=J(B/'run.json')
    for name,v in d['inputs'].items():
        src=W3/v['source'];assert sha(src)==v['sha256'],name
        dst=B/name
        if dst.exists():assert sha(dst)==v['sha256'],name
        else:shutil.copyfile(src,dst)
    # Copy the actual archived .fs solely into this test workspace so the audit
    # can require real bitstream completion. It is never packaged or programmed.
    orig=C/'build_nominal_v0/impl/pnr/board.fs'
    recorded=J(C/'delivery.json')['build_files']['build_nominal_v0/impl/pnr/board.fs']
    assert sha(orig)==recorded
    shutil.copyfile(orig,B/'impl/pnr/board.fs')
    out=W3/'evidence/archived-baseline-audit.json'
    p=subprocess.run([sys.executable,str(P/'tools/audit_build.py'),'--workspace',str(W3),
        '--label',B.name,'--output',str(out)],capture_output=True,text=True)
    (V/'archived-audit-console.log').write_text(p.stdout+p.stderr,encoding='utf-8')
    result=J(out)
    assert p.returncode==2 and result['route_completed'] and not result['scoped_static_pass']
    assert result['timing']['slack_ns']['Setup']==-6.397 and result['timing']['slack_ns']['Hold']==-.048
    shutil.copyfile(out,V/'archived-baseline-audit.json')
    print('PASS audited real archived routed build: correctly rejected negative setup/hold')
else:
    cases=[(W1,'transfer01-native'),(W1,'transfer01-pitch'),(W1,'transfer01-engine'),
           (W2,'transfer02-envelope'),(W2,'transfer02-phase_wrap')]
    receipts={}
    for work,name in cases:
        e=work/'evidence'/name;r=J(e/'suite-run.json')
        assert r['status']=='PASS scoped regression only' and not r['source_changed_from_bootstrap'],name
        for f in e.iterdir():
            if f.is_file() and f.suffix in ('.json','.log'):
                dest=V/name/f.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
        receipts[name]=dict(receipt=r,receipt_sha256=sha(e/'suite-run.json'),original_evidence=str(e))
    failure=W1/'evidence/transfer01-envelope'
    assert J(failure/'suite-run.json')['status']=='FAIL'
    for f in failure.iterdir():
        if f.is_file() and f.suffix in ('.json','.log'):
            dest=V/'preserved-first-envelope-failure'/f.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(f,dest)
    guards=[]
    def reject(cmd,needle):
        p=subprocess.run(cmd,capture_output=True,text=True)
        assert p.returncode!=0 and needle in p.stdout+p.stderr,(cmd,p.stdout,p.stderr)
        guards.append(dict(command=cmd,returncode=p.returncode,expected=needle,output=p.stdout+p.stderr))
    reject([sys.executable,str(P/'tools/bootstrap.py'),'--destination',str(W3)],'Refuse to overwrite an existing workspace')
    duplicate=W3/'evidence/guard-native';duplicate.mkdir()
    reject([sys.executable,str(P/'tools/run_checks.py'),'--workspace',str(W3),'--suite','native','--run-id','guard'],'Never overwrite evidence')
    fixture=W3/'tamper-fixture';fixture.mkdir();(fixture/'test.txt').write_text('original',encoding='utf-8')
    (fixture/'MANIFEST.json').write_text(json.dumps(dict(files={'test.txt':{'sha256':sha(fixture/'test.txt')}})))
    subprocess.run([sys.executable,str(P/'tools/verify.py'),str(fixture)],check=True,capture_output=True)
    (fixture/'test.txt').write_text('changed',encoding='utf-8')
    reject([sys.executable,str(P/'tools/verify.py'),str(fixture)],'Package identity mismatch')
    summary=dict(status='PASS scoped handoff transfer validation',tested=receipts,guards=guards,
        preserved_failure='First envelope compilation lacked TIMING_RTL_SIM and native RAM model for current full source set; bootstrap adaptations repaired, same frozen RTL and same assertions passed on second workspace. Initial archived-build audit also detected missing constraints in the old source inventory; handoff now explicitly binds and includes all 100 actual build inputs, validated on a fresh third workspace.',
        audited_archived_build=J(V/'archived-baseline-audit.json'),
        tested_payload_identities={p.relative_to(P).as_posix():sha(p) for p in list((P/'tools').glob('*.py'))+list((P/'candidate_source/engine/src').glob('*')) if p.is_file()},
        no_new_pnr=True,hardware_programmed=False,complete_product_qualified=False,
        not_rerun_in_this_handoff=['joint','renderer','scan','delta','sensor'],
        statement='Those suites are included with existing scoped evidence; no new pass is claimed for unexecuted suites.')
    (V/'VALIDATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS transfer checks, guards and archived failing-STA audit; initial failure preserved')
