from pathlib import Path
import hashlib,json,zipfile,subprocess,sys
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/register_memory_20261018';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
B=Path((N/'latest-backup.txt').read_text(encoding='utf-8'));backup=read(B/'manifest.json')
allowed={str(p) for prefix in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for path,item in backup.items():
  assert hashlib.sha256(z.read(item['member'])).hexdigest()==item['sha256']
  if path not in allowed:assert sha(Path(path))==item['sha256'],('protected original',path)
up=read(R/'upstream.json');U=Path(up['root']);old=read(U/'delivery.json');assert sha(U/'delivery.json')==up['delivery_sha256']
for group in ('source_files','evidence','inherited_76_artifacts'):
 for rel,h in old[group].items():assert sha(U/rel)==h,('previous stage',group,rel)
# The two original modules are deliberately left unchanged.
for name in ('reg_bank.v','tdm_top.v'):assert sha(R/'src'/name)==up['source_files']['src/'+name]
assert sha(R/'reference/tdm_top_owned_original.v')==up['source_files']['src/tdm_top_owned.v']
for name in ('matrix-core','matrix-serial','register-memory','register-resources','host-validation','transport-validation','transport-host','serial-config','serial-nominal','serial-dual','envelope-reference','phase-wrap','config-music','engine-compatibility','enabled-compatibility','fault-validation','board-config','board-nominal','board-register-audit'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS'),name
 for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
for label,key in [('engine','engine-compatibility'),('enabled','enabled-compatibility')]:
 for name,item in read(E/(key+'.json'))['results'].items():
  trace=E/(name+'-compat.tsv') if label=='engine' else E/('enabled-'+name+'.tsv')
  assert sha(trace)==item['trace_sha256']==item['reference_sha256']
for key,trace in [('envelope-reference','envelope.tsv'),('config-music','config-music.tsv')]:assert sha(E/trace)==read(E/(key+'.json'))['trace_sha256']
gui={p.relative_to(R).as_posix():sha(p) for p in (R/'gui').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for rel,h in gui.items():assert sha(U/rel)==h,('GUI changed',rel)
resource=read(E/'register-resources.json')
for folder in ('synthesis_reference','synthesis_compact_v1','build_board_register'):
 D=R/folder;d=read(D/'run.json');assert d['returncode']==0
 for name,item in d['inputs'].items():assert sha(D/name)==sha(R/item['source'])==item['sha256'],(folder,name)
audit=read(E/'board-register-audit.json')
assert audit['bitstream_sha256']==sha(R/'build_board_register/impl/pnr/board_config.fs') and not audit['programmed']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(old['source_engine']['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
 (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,(label,out.stdout,out.stderr)
sources={};evidence={};inherited={}
for p in R.rglob('*'):
 if not p.is_file() or '__pycache__' in p.parts or p.name=='delivery.json':continue
 rel=p.relative_to(R);parts=rel.parts
 if parts[0]=='package' and p.name!='INHERITED_76_ONLY.md':
  assert sha(p)==up['inherited_76_artifacts'][rel.as_posix()];inherited[rel.as_posix()]=sha(p)
 elif parts[0]=='evidence':
  if p.suffix in ('.json','.log','.tsv','.png','.csv','.v'):evidence[rel.as_posix()]=sha(p)
 elif parts[0].startswith('synthesis_') or parts[0]=='build_board_register':
  if p.suffix in ('.v','.vh','.hex','.json','.gprj','.tcl','.txt','.html','.xml','.cst','.sdc','.fs','.log','.vg'):evidence[rel.as_posix()]=sha(p)
 elif p.suffix in ('.v','.vh','.hex','.json','.py','.md','.cmd','.qss','.ttf','.cst','.sdc','.xml'):sources[rel.as_posix()]=sha(p)
docs={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','78-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
assert len(docs)==4,'Report and all three design entries must exist before finalizing'
assert 'register-memory-20261018-v0' in (R/'project/CURRENT.md').read_text(encoding='utf-8')
for prefix in ('38-','39-','49-'):
 assert '2026-10-18参数回读RAM优化' in next((P/'docs/02-技术方案').glob(prefix+'*.md')).read_text(encoding='utf-8')
delivery=dict(version='register-memory-20261018-v0',status='partial product; recorded RTL tests, full synthesis and diagnostic internal PnR verified; physical new RAM path unverified',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',source_engine=old['source_engine'],upstream_delivery_sha256=up['delivery_sha256'],backup=dict(root=str(B),files=len(backup),sha256=sha(B/'before.zip')),source_files=sources,evidence=evidence,documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},inherited_76_artifacts=inherited,inherited_gui=dict(modified=False,files=gui,verification='76 GUI104 inherited; not rerun this turn'),inherited_fx_verification=dict(source_sha256=sha(R/'src/fx_delay.v'),verification='77 dedicated FX equivalence inherited; not rerun this turn'),resource={k:resource[k] for k in ('before','after','logic_saved','registers_saved','extra_bsram','logic_spare','bsram_spare')},board_resource=audit['resource'],board_slack_ns=audit['slack_ns'],full_system_pnr=False,diagnostic_pnr=True,hardware_tested=False,serial_opened=False,fpga_programmed=False,flash_read_or_written=False,storage_media_accessed=False,persisted=False,recording_implemented=False,current_hardware='76 configuration diagnostic left unchanged',nonselected_trials={'synthesis_compact':'initial unused legacy top probe; not selected, not resource evidence'},next='isolated storage-controller and buffer verification/resource budget; then persistence and recorded accompaniment integration')
assert sha(R/'src/fx_delay.v')==up['source_files']['src/fx_delay.v']
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS recorded delivery identities only',sources=len(sources),evidence=len(evidence),inherited=len(inherited),backup=len(backup),resource=delivery['resource']),ensure_ascii=False))
