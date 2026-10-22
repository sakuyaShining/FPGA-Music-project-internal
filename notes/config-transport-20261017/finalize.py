from pathlib import Path
import json,hashlib,zipfile,re,subprocess,sys
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/config_transport_20261017';E=R/'evidence'
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
for group in ('source_files','evidence'):
 for rel,h in read(U/'delivery.json')[group].items():assert sha(U/rel)==h,('upstream',rel)
for name,h in up['gui_files'].items():assert sha(Path(up['gui_root'])/name)==h,('original GUI',name)
for name in ('matrix-serial','matrix-core','matrix-gui','host-validation','transport-validation','transport-host','serial-config','serial-nominal','serial-dual','envelope-reference','phase-wrap','config-music','engine-compatibility','enabled-compatibility','fault-validation'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS'),name
 for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
for name,item in read(E/'engine-compatibility.json')['results'].items():assert sha(E/(name+'-compat.tsv'))==item['trace_sha256']==item['reference_sha256']
for name,item in read(E/'enabled-compatibility.json')['results'].items():assert sha(E/('enabled-'+name+'.tsv'))==item['trace_sha256']==item['reference_sha256']
for key,trace in [('envelope-reference','envelope.tsv'),('config-music','config-music.tsv')]:assert sha(E/trace)==read(E/(key+'.json'))['trace_sha256']
for name in ('serial-config','serial-nominal','serial-dual'):
 c=read(E/('compile-'+name+'-inputs.json'));v=read(E/('run-'+name+'-inputs.json'))
 assert c['returncode']==0 and v['returncode']==0
 for p,h in c['inputs'].items():assert sha(Path(p))==h,(name,p)
 for p,h in v['inputs'].items():assert sha(Path(p))==h,(name,p)
S=R/'synthesis_selected';syn=read(S/'run.json');assert syn['status']=='FAILED synthesis'
for name,item in syn['inputs'].items():assert sha(S/name)==sha(R/item['source'])==item['sha256'],name
assert sha(S/'probe.gprj')==syn['project_sha256'] and sha(S/'synth.tcl')==syn['tcl_sha256']
logic=int(re.search(r'The number\((\d+)\(', (S/'console.txt').read_text(encoding='utf-8'))[1]);assert logic==20767
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(read(U/'delivery.json')['source_engine']['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace');(E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,(label,out.stdout,out.stderr)
sources={};evidence={}
for p in R.rglob('*'):
 if not p.is_file() or '__pycache__' in p.parts:continue
 rel=p.relative_to(R);parts=rel.parts
 if p.name=='delivery.json':continue
 if parts[0]=='evidence':
    if p.suffix in ('.json','.log','.tsv','.png'):evidence[rel.as_posix()]=sha(p)
 elif parts[0].startswith('synthesis_'):
    if p.suffix in ('.v','.vh','.hex','.json','.gprj','.tcl','.txt') and 'impl' not in parts:evidence[rel.as_posix()]=sha(p)
 elif p.suffix in ('.v','.vh','.hex','.json','.py','.md','.cmd','.qss','.ttf'):sources[rel.as_posix()]=sha(p)
docs={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','75-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
delivery=dict(version='config-transport-20261017-v0',status='partial implementation; recorded simulation/offline checks passed; full synthesis FAILED',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',source_engine=read(U/'delivery.json')['source_engine'],upstream_delivery_sha256=up['delivery_sha256'],backup=dict(root=str(B),files=len(backup),sha256=sha(B/'before.zip')),source_files=sources,evidence=evidence,documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},resource=dict(status='FAILED',Logic=logic,limit=20736,over=logic-20736,registers=None,BSRAM=None),pnr_tested=False,hardware_tested=False,serial_opened=False,fpga_programmed=False,flash_read_or_written=False,original_gui_modified=False,isolated_gui_modified=True,persisted=False,full_config_supported=False,next='resource optimization with regressions; then board wrapper/PnR/SRAM configuration and PCM validation')
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS recorded delivery identity only',sources=len(sources),evidence=len(evidence),backup_files=len(backup),resource=delivery['resource'],hardware_tested=False)))
