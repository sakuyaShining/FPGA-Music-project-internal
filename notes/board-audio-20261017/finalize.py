from pathlib import Path
import hashlib,json,zipfile,subprocess,sys,concurrent.futures,filecmp
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/board_audio_20261017';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
B=Path((N/'latest-backup.txt').read_text(encoding='utf-8'));backup=read(B/'manifest.json')
allowed={p.relative_to(P).as_posix() for prefix in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
with zipfile.ZipFile(B/'before.zip') as z:
    assert z.testzip() is None
    for name,digest in backup.items():
        assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
        if name not in allowed:assert sha(P/name)==digest,('protected',name)
up=read(R/'upstream.json');U=Path(up['root']);assert sha(U/'delivery.json')==up['delivery_sha256']
for name,digest in up['files'].items():assert sha(U/name)==digest,('upstream',name)
for name in ('validation.json','host-validation.json','engine-compatibility.json','reset-fault.json','build-audit.json'):
    data=read(E/name);assert data['status'].startswith('PASS'),name
    for rel,digest in data['inputs'].items():assert sha(R/rel)==digest,(name,rel)
assert read(E/'host-validation.json')['tests']==9
compat=read(E/'engine-compatibility.json')
for key,item in compat['results'].items():
    assert sha(E/(key+'-compat.tsv'))==item['trace_sha256']==item['reference_sha256'],key
    assert filecmp.cmp(E/(key+'-compat.tsv'),U/'evidence'/(key+'-all.tsv'),shallow=False),key
audit=read(E/'build-audit.json')
assert audit['profiles']['build_ready_default']['slack_ns']['Setup']>0
for profile in ('build_ready_default','build_mute'):
    D=R/profile;data=read(D/'run.json');assert data['returncode']==0
    assert data['project_sha256']==sha(D/'board_audio.gprj') and data['tcl_sha256']==sha(D/'build.tcl')
    for name,item in data['inputs'].items():assert sha(D/name)==sha(R/item['source'])==item['sha256'],(profile,name)
    assert sha(D/'impl/pnr/board_audio.fs')==audit['profiles'][profile]['bitstream_sha256']
package=read(R/'package/manifest.json')
for name,digest in package['files'].items():assert sha(R/'package'/name)==digest,name
old=N.parent/'left-hand-events-20261016';old_B=Path((old/'latest-backup.txt').read_text(encoding='utf-8').strip());counts={}
for label,item in read(old_B/'manifest.json').items():
    counts[label]=len(item['files']);assert sha(Path(item['archive']))==item['sha256']
    for name,digest in item['files'].items():assert sha(Path(item['root'])/name)==digest,('original',label,name)
origin=read(U/'delivery.json')['source_engine'];engine=Path(origin['root'])
jobs=[('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',engine,['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]
def identity(job):
    label,cwd,args=job;r=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace');(E/('identity-'+label+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8');assert r.returncode==0,(label,r.stdout,r.stderr)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:list(ex.map(identity,jobs))
sources={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and not any(x in p.relative_to(R).parts for x in ('impl','evidence','__pycache__','package')) and p.name not in ('delivery.json','run.json','console.txt') and p.suffix in ('.v','.vh','.hex','.py','.json','.md','.gprj','.tcl','.cst','.sdc')}
evidence={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and p.suffix in ('.log','.json','.html','.xml','.txt','.fs','.vg') and (p.parent==E or p.name in ('console.txt','run.json') or 'impl' in p.relative_to(R).parts or 'package' in p.relative_to(R).parts)}
docs={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','72-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
delivery=dict(version='board-audio-20261017-v0',status='已实现待验证：实体板级',preparation_status='已验证：记录的数字/内部PnR/引脚范围',source_engine=origin,upstream_delivery_sha256=up['delivery_sha256'],backup=dict(root=str(B),files=len(backup),zip_sha256=sha(B/'before.zip')),protected_counts=counts,hardware_tested=False,serial_opened=False,fpga_programmed=False,flash_read_or_written=False,external_i2s_timing_verified=False,profile='audio diagnostic only; excludes physical touch/screens/storage',build_audit=audit['profiles'],source_files=sources,evidence=evidence,design_documents=docs,package_manifest_sha256=sha(R/'package/manifest.json'),stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},next='实体上电后核验器件/连接，临时SRAM测试；保存真实UART/音频证据')
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS prepared artifact/provenance only',source_files=len(sources),protected_counts=counts,pnr=audit['profiles']['build_ready_default']['slack_ns'],hardware_tested=False,programmed=False),ensure_ascii=True))
