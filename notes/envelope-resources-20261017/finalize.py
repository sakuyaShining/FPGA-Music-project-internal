from pathlib import Path
import json,hashlib,zipfile,subprocess,sys,re
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent;R=P/'experiments/envelope_resources_20261017';E=R/'evidence'
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
 for rel,h in read(U/'delivery.json')[group].items():assert sha(U/rel)==h,('previous',rel)
original_gui=read(U/'upstream.json')
for name,h in original_gui['gui_files'].items():assert sha(Path(original_gui['gui_root'])/name)==h,('original GUI',name)
for name in ('matrix-core','matrix-serial','matrix-gui','shared-envelope','host-validation','transport-validation','transport-host','serial-config','serial-nominal','serial-dual','envelope-reference','phase-wrap','config-music','engine-compatibility','enabled-compatibility','fault-validation','board-config','board-nominal','board-build-audit'):
 d=read(E/(name+'.json'));assert d['status'].startswith('PASS'),name
 for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
for label,key in [('engine','engine-compatibility'),('enabled','enabled-compatibility')]:
 for name,item in read(E/(key+'.json'))['results'].items():
    trace=E/(name+'-compat.tsv') if label=='engine' else E/('enabled-'+name+'.tsv')
    assert sha(trace)==item['trace_sha256']==item['reference_sha256']
for key,trace in [('envelope-reference','envelope.tsv'),('config-music','config-music.tsv')]:assert sha(E/trace)==read(E/(key+'.json'))['trace_sha256']
assert sha(R/'reference/osc_env_original.v')==up['source_files']['src/osc_env.v']
syn={}
for label in ('reference','shared'):
 D=R/('synthesis_'+label);d=read(D/'run.json');syn[label]=d
 for name,item in d['inputs'].items():assert sha(D/name)==sha(R/item['source'])==item['sha256'],(label,name)
 assert sha(D/'probe.gprj')==d['project_sha256'] and sha(D/'synth.tcl')==d['tcl_sha256']
assert syn['reference']['status']=='FAILED synthesis' and 'The number(20767(' in (R/'synthesis_reference/console.txt').read_text(encoding='utf-8')
assert syn['shared']['status']=='PASS synthesis only' and syn['shared']['metrics']==dict(Logic=20537,BSRAM=46,Register=11428)
assert syn['reference']['project_sha256']==syn['shared']['project_sha256']
assert set(syn['reference']['inputs'])==set(syn['shared']['inputs'])
assert [k for k,v in syn['reference']['inputs'].items() if v['sha256']!=syn['shared']['inputs'][k]['sha256']]==['osc_env.v']
board=read(R/'build_board/run.json');assert board['returncode']==0
for name,item in board['inputs'].items():assert sha(R/'build_board'/name)==sha(R/item['source'])==item['sha256']
assert sha(R/'build_board/board_config.gprj')==board['project_sha256'] and sha(R/'build_board/build.tcl')==board['tcl_sha256']
audit=read(E/'board-build-audit.json');S=Path((N/'latest-hardware.txt').read_text(encoding='utf-8'));hardware=read(S/'uart/result.json');program=read(S/'program-result.json')
assert hardware['status'].startswith('PASS') and not hardware.get('cleanup_error')
assert hardware['hardware_tested'] and not hardware['flash_read_or_written'] and hardware['after']['active']==0 and hardware['cleanup_pcm']['nonzero']==0
assert hardware['script_sha256']==sha(N/'verify_hardware.py') and program['script_sha256']==sha(N/'program_sram.py') and program['operation']==2
assert program['board_audit_sha256']==sha(E/'board-build-audit.json')
assert program['bitstream_sha256']==hardware['bitstream_sha256']==audit['bitstream_sha256']==sha(R/'package/config-sram.fs')
assert len(hardware['applications'])==5 and all(v['status']=='VOLATILE_CONFIG_CONFIRMED' for v in hardware['applications'].values())
assert hardware['attack_rms_ratio']>3 and len(hardware['captures'])==10
for name,item in hardware['captures'].items():
 assert sha(S/'uart'/(name+'.s24le.bin'))==item['pcm_sha256'] and (S/'uart'/(name+'.s24le.bin')).stat().st_size==6144
manifest=read(R/'package/manifest.json');assert manifest['hardware_tested'] and manifest['hardware_result_sha256']==sha(S/'uart/result.json')
for name,h in manifest['files'].items():assert sha(R/'package'/name)==h
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(read(U/'delivery.json')['source_engine']['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
 out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace');(E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,(label,out.stdout,out.stderr)
sources={};evidence={}
for p in R.rglob('*'):
 if not p.is_file() or '__pycache__' in p.parts:continue
 rel=p.relative_to(R);parts=rel.parts
 if p.name=='delivery.json':continue
 if parts[0]=='evidence':
    if p.suffix in ('.json','.log','.tsv','.png'):evidence[rel.as_posix()]=sha(p)
 elif parts[0].startswith('synthesis_') or parts[0]=='build_board':
    if p.suffix in ('.v','.vh','.hex','.json','.gprj','.tcl','.txt','.html','.xml','.cst','.sdc','.fs','.log','.vg'):evidence[rel.as_posix()]=sha(p)
 elif p.suffix in ('.v','.vh','.hex','.json','.py','.md','.cmd','.qss','.ttf','.cst','.sdc','.fs'):sources[rel.as_posix()]=sha(p)
docs={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','76-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
hardware_evidence={p.relative_to(P).as_posix():sha(p) for p in S.rglob('*') if p.is_file()}
delivery=dict(version='envelope-resources-20261017-v0',status='partial product; shared envelope equivalence, full synthesis and bounded diagnostic hardware checks verified',source_main='fe326ad9505c94f46f9236bf7f9bfc3b5f1b9a12',source_engine=read(U/'delivery.json')['source_engine'],upstream_delivery_sha256=up['delivery_sha256'],backup=dict(root=str(B),files=len(backup),sha256=sha(B/'before.zip')),source_files=sources,evidence=evidence,documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},hardware_evidence=hardware_evidence,resource=dict(status='PASS synthesis only',reference_logic=20767,Logic=20537,Register=11428,BSRAM=46,limit=20736,logic_spare=199,bsram_spare=0),board_resource=audit['resource'],board_slack_ns=audit['slack_ns'],full_system_pnr=False,diagnostic_pnr=True,hardware_tested=True,hardware_scope='configuration adapter and UART/internal PCM; physical S2 this turn and analog listening unverified',serial_opened=True,fpga_programmed=True,download_mode='SRAM operation2 only',flash_read_or_written=False,original_gui_modified=False,full_config_supported=False,persisted=False,next='memory/cache resource plan; nonvolatile configuration and recorded accompaniment/replay integration')
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS recorded delivery identity only',sources=len(sources),evidence=len(evidence),hardware_evidence=len(hardware_evidence),backup_files=len(backup),resource=delivery['resource'],board_slack_ns=delivery['board_slack_ns'],hardware_tested=True)))
