from pathlib import Path
import json,hashlib,zipfile,subprocess,sys,filecmp
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/instrument_config_20261017';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
B=Path((N/'latest-backup.txt').read_text(encoding='utf-8'));backup=read(B/'manifest.json')
allowed={str(p) for prefix in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
with zipfile.ZipFile(B/'before.zip') as z:
    assert z.testzip() is None
    for path,item in backup.items():
        assert hashlib.sha256(z.read(item['member'])).hexdigest()==item['sha256']
        if path not in allowed:assert sha(Path(path))==item['sha256'],('protected',path)
up=read(R/'upstream.json');U=Path(up['root']);assert sha(U/'delivery.json')==up['delivery_sha256']
for rel,digest in up['files'].items():assert sha(U/rel)==digest,('upstream',rel)
for group in ('source_files','evidence'):
    for rel,digest in read(U/'delivery.json')[group].items():assert sha(U/rel)==digest,('previous',rel)
for name in ('host-validation.json','envelope-reference.json','phase-wrap.json','config-music.json','engine-compatibility.json','enabled-compatibility.json','fault-validation.json'):
    d=read(E/name);assert d['status'].startswith('PASS'),name
    for rel,digest in d['inputs'].items():assert sha(R/rel)==digest,(name,rel)
assert read(E/'host-validation.json')['tests']==11
for name,item in read(E/'engine-compatibility.json')['results'].items():assert sha(E/(name+'-compat.tsv'))==item['trace_sha256']==item['reference_sha256']
for name,item in read(E/'enabled-compatibility.json')['results'].items():assert sha(E/('enabled-'+name+'.tsv'))==item['trace_sha256']==item['reference_sha256']
assert sha(E/'envelope.tsv')==read(E/'envelope-reference.json')['trace_sha256']
assert sha(E/'config-music.tsv')==read(E/'config-music.json')['trace_sha256']
D=R/'synthesis_full';syn=read(D/'run.json');assert syn['status'].startswith('PASS')
for name,item in syn['inputs'].items():assert sha(D/name)==sha(R/item['source'])==item['sha256'],name
assert sha(D/'probe.gprj')==syn['project_sha256'] and sha(D/'synth.tcl')==syn['tcl_sha256']
assert syn['metrics']==dict(Logic=20277,BSRAM=45,Register=11189)
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(read(U/'delivery.json')['source_engine']['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
    out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace');(E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,(label,out.stdout,out.stderr)
source_files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and not any(part in p.relative_to(R).parts for part in ('evidence','__pycache__','impl')) and p.name not in ('delivery.json','console.txt','run.json') and p.suffix in ('.v','.vh','.hex','.json','.py','.md','.gprj','.tcl')}
evidence={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and (p.parent==E and p.suffix in ('.json','.log','.tsv') or p.name in ('run.json','console.txt') or 'impl' in p.relative_to(R).parts)}
docs={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','74-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
delivery=dict(version='instrument-config-20261017-v0',status='部分实现；记录的编译/逻辑应用/PCM与综合范围已验证',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',source_engine=read(U/'delivery.json')['source_engine'],upstream_delivery_sha256=up['delivery_sha256'],backup=dict(root=str(B),files=len(backup),sha256=sha(B/'before.zip')),source_files=source_files,evidence=evidence,documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},resource=syn['metrics'],pnr_tested=False,hardware_tested=False,serial_opened=False,fpga_programmed=False,flash_read_or_written=False,gui_modified=False,full_config_supported=False,next='能力识别/可靠传输与GUI应用，再做对应板级构建和实际音频验证')
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(dict(status='PASS delivery identity only',sources=len(source_files),evidence=len(evidence),backup_files=len(backup),resource=syn['metrics'],hardware_tested=False)))
