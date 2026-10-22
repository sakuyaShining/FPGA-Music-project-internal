from pathlib import Path
import json,hashlib,zipfile,subprocess,sys
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/fx_memory_20261017';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
B=Path((N/'latest-backup.txt').read_text(encoding='utf-8'));backup=read(B/'manifest.json')
allowed={str(p) for prefix in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for path,item in backup.items():
    assert hashlib.sha256(z.read(item['member'])).hexdigest()==item['sha256']
    if path not in allowed:assert sha(Path(path))==item['sha256'],('protected',path)
up=read(R/'upstream.json');U=Path(up['root']);old=read(U/'delivery.json');assert sha(U/'delivery.json')==up['delivery_sha256']
for group in ('source_files','evidence'):
 for rel,h in old[group].items():assert sha(U/rel)==h,('previous',rel)
for rel,h in old['hardware_evidence'].items():assert sha(P/rel)==h,('previous hardware',rel)
assert sha(R/'reference/fx_delay_original.v')==up['source_files']['src/fx_delay.v']
for name in ('matrix-core','matrix-serial','fx-equivalence','host-validation','transport-validation','transport-host','serial-config','serial-nominal','serial-dual','envelope-reference','phase-wrap','config-music','engine-compatibility','enabled-compatibility','fault-validation','board-config','board-nominal','board-memory-audit'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS'),name
 for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
for label,key in [('engine','engine-compatibility'),('enabled','enabled-compatibility')]:
 for name,item in read(E/(key+'.json'))['results'].items():
    trace=E/(name+'-compat.tsv') if label=='engine' else E/('enabled-'+name+'.tsv')
    assert sha(trace)==item['trace_sha256']==item['reference_sha256']
for key,trace in [('envelope-reference','envelope.tsv'),('config-music','config-music.tsv')]:assert sha(E/trace)==read(E/(key+'.json'))['trace_sha256']
gui={p.relative_to(R).as_posix():sha(p) for p in (R/'gui').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for rel,h in gui.items():assert sha(U/rel)==h,('GUI unchanged',rel)
syn={}
for label in ('reference','single_read'):
 D=R/('synthesis_'+label);d=read(D/'run.json');syn[label]=d;assert d['status']=='PASS synthesis only'
 for name,item in d['inputs'].items():assert sha(D/name)==sha(R/item['source'])==item['sha256'],(label,name)
 assert sha(D/'probe.gprj')==d['project_sha256'] and sha(D/'synth.tcl')==d['tcl_sha256']
assert syn['reference']['metrics']==dict(Logic=20537,BSRAM=46,Register=11428)
assert syn['single_read']['metrics']==dict(Logic=20635,BSRAM=28,Register=11592)
assert syn['reference']['project_sha256']==syn['single_read']['project_sha256']
assert set(syn['reference']['inputs'])==set(syn['single_read']['inputs'])
assert [k for k,v in syn['reference']['inputs'].items() if v['sha256']!=syn['single_read']['inputs'][k]['sha256']]==['fx_delay.v']
inventory=read(E/'memory-inventory.json');assert inventory['fx_before']==20 and inventory['fx_after']==2 and inventory['freed_blocks']==18
for rel,h in inventory['source_xml'].items():assert sha(R/rel)==h
audit=read(E/'board-memory-audit.json');board=read(R/'build_board_memory/run.json');assert board['returncode']==0
for name,item in board['inputs'].items():assert sha(R/'build_board_memory'/name)==sha(R/item['source'])==item['sha256']
assert sha(R/'build_board_memory/board_config.gprj')==board['project_sha256'] and sha(R/'build_board_memory/build.tcl')==board['tcl_sha256']
assert audit['bitstream_sha256']==sha(R/'build_board_memory/impl/pnr/board_config.fs') and not audit['programmed']
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(old['source_engine']['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace');(E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,(label,out.stdout,out.stderr)
sources={};evidence={};inherited={}
for p in R.rglob('*'):
 if not p.is_file() or '__pycache__' in p.parts:continue
 rel=p.relative_to(R);parts=rel.parts
 if p.name=='delivery.json':continue
 if parts[0]=='package' and p.name!='INHERITED_76_ONLY.md':
    assert sha(p)==up['source_files'][rel.as_posix()];inherited[rel.as_posix()]=sha(p)
 elif parts[0]=='evidence':
    if p.suffix in ('.json','.log','.tsv','.png','.csv'):evidence[rel.as_posix()]=sha(p)
 elif parts[0].startswith('synthesis_') or parts[0]=='build_board_memory':
    if p.suffix in ('.v','.vh','.hex','.json','.gprj','.tcl','.txt','.html','.xml','.cst','.sdc','.fs','.log','.vg'):evidence[rel.as_posix()]=sha(p)
 elif p.suffix in ('.v','.vh','.hex','.json','.py','.md','.cmd','.qss','.ttf','.cst','.sdc','.xml'):sources[rel.as_posix()]=sha(p)
docs={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','77-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
delivery=dict(version='fx-memory-20261017-v0',status='partial product; recorded RTL equivalence/regressions/full synthesis and diagnostic PnR verified; new memory hardware path unverified',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',source_engine=old['source_engine'],upstream_delivery_sha256=up['delivery_sha256'],backup=dict(root=str(B),files=len(backup),sha256=sha(B/'before.zip')),source_files=sources,evidence=evidence,documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},inherited_76_artifacts=inherited,inherited_gui=dict(modified=False,gui_files=gui,verification='76 GUI104 not rerun this turn'),resource=dict(status='PASS synthesis only',before=syn['reference']['metrics'],after=syn['single_read']['metrics'],logic_change=98,bsram_freed=18,logic_spare=101,bsram_spare=18),board_resource=audit['resource'],board_slack_ns=audit['slack_ns'],full_system_pnr=False,diagnostic_pnr=True,hardware_tested=False,serial_opened=False,fpga_programmed=False,flash_read_or_written=False,storage_media_accessed=False,persisted=False,full_config_supported=False,current_hardware='76 configuration diagnostic left unchanged',next='use released BSRAM to regain logic capacity; then storage controller/persistence and recorded accompaniment integration')
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS recorded delivery identity only',sources=len(sources),evidence=len(evidence),inherited_artifacts=len(inherited),backup_files=len(backup),resource=delivery['resource'],hardware_tested=False)))
