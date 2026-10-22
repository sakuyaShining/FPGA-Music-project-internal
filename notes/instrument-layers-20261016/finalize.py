"""Validate recorded evidence and identities before writing a NEW delivery."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,zipfile,concurrent.futures
import xml.etree.ElementTree as ET
N=Path(__file__).resolve().parent;P=N.parents[1];R=P/'experiments/instrument_layers_20261016';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
b=N/'backup-20261016-212925';manifest=read(b/'manifest.json')
allowed={str(p.relative_to(P)).replace('\\','/') for prefix in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
with zipfile.ZipFile(b/'before.zip') as z:
    assert z.testzip() is None
    for name,digest in manifest.items():
        assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
        if name not in allowed:assert sha(P/name)==digest,('protected backup input',name)
up=read(R/'upstream.json');U=Path(up['source'])
for name,digest in up['inputs'].items():assert sha(U/name)==digest,('upstream',name)
# Recheck the previous stage's wider main/engine/source protection, without
# running its finalizer or rewriting its historical delivery/document hashes.
previous=N.parent/'left-hand-events-20261016'
old_b=Path((previous/'latest-backup.txt').read_text(encoding='utf-8').strip())
counts={}
for label,data in read(old_b/'manifest.json').items():
    counts[label]=len(data['files']);assert sha(Path(data['archive']))==data['sha256']
    for name,digest in data['files'].items():assert sha(Path(data['root'])/name)==digest,('original',label,name)
for name in ['validation.json','memory-opt.json','derivations.json']:
    record=read(E/name)
    assert record['status'].startswith('PASS'),name
    for path,digest in record.get('inputs',record.get('files',{})).items():assert sha(R/path)==digest,(name,path)
    for path,digest in record.get('generators',{}).items():assert sha(P/path)==digest,(name,path)
    for log in record.get('results',{}).values():
        assert 'PASS ' in log and 'pcm_hash=xxxx' not in log and 'i2s_hash=xxxx' not in log,name
assert read(E/'slot-format.json')['random_round_trips']==100
profiles={}
for profile in ['synthesis','synthesis_bram','synthesis_memory','synthesis_selected']:
    D=R/profile;record=read(D/'run.json')
    assert record['project_sha256']==sha(D/'probe.gprj')
    assert record['tcl_sha256']==sha(D/'synth.tcl')
    for name,data in record['inputs'].items():
        assert sha(D/name)==data['sha256'],(profile,name)
        if profile=='synthesis_selected':assert sha(R/data['source'])==data['sha256'],('selected source',name)
    log=(D/'console.txt').read_text(encoding='utf-8',errors='replace')
    if profile!='synthesis_selected':
        assert record['returncode']!=0 and 'ERROR (RP0006)' in log
        metrics={'Logic':int(re.search(r'The number\((\d+)\(',log)[1])}
    else:
        assert record['returncode']==0 and 'ERROR (' not in log
        text=(D/'impl/gwsynthesis/probe_syn.rpt.html').read_text(encoding='utf-8',errors='replace')
        metrics={key:int(re.search('>'+key+r'</td>\s*<td>(\d+)',text)[1]) for key in ['Logic','BSRAM']}
        metrics['Register']=int(ET.parse(D/'impl/gwsynthesis/probe_syn_rsc.xml').getroot().get('T_Register').split('(')[0])
        assert metrics==record['metrics']==dict(Logic=20668,BSRAM=43,Register=12604)
        for line in log.splitlines():
            assert not ('WARN' in line and 'EX3791' in line and any(s in line for s in ('instrument_table.v','layer_dispatch.v','finger_pitch.v','note_map_owned.v','left_layer_music_probe.v'))),line
    profiles[profile]=dict(status=record['status'],metrics=metrics,pnr_tested=False)
origin=read(U/'source-engine.json');engine=Path(origin['root'])
jobs=[('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',engine,['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]
def identity(job):
    label,cwd,args=job
    out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,(label,out.stdout,out.stderr)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:list(executor.map(identity,jobs))
inputs={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and not any(x in p.relative_to(R).parts for x in ('impl','evidence','__pycache__')) and p.name not in ('delivery.json','run.json','console.txt') and p.suffix in ('.v','.vh','.hex','.py','.md','.json','.gprj','.tcl')}
evidence={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and p.suffix in ('.log','.json','.txt','.html','.xml','.vg') and (p.parent==E or p.name in ('console.txt','run.json') or 'impl' in p.relative_to(R).parts)}
docs={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','70-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
delivery=dict(version='instrument-layers-20261016-v0',status='部分实现',digital_dual_layer_verified=True,full_configuration_applied=False,hardware_tested=False,pnr_tested=False,source_engine=origin,upstream_delivery_sha256=sha(U/'delivery.json'),backup=dict(directory=str(b),files=len(manifest),zip_sha256=sha(b/'before.zip')),protected_counts=counts,resources=profiles,remaining=dict(logic=68,bsram=3,full_product_capacity_verified=False),source_files=inputs,evidence=evidence,design_documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},next='优先资源优化，逐层完整包络、非易失和TF/SDRAM录放接合')
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS provenance and recorded digital evidence only',source_files=len(inputs),protected_counts=counts,resources=profiles['synthesis_selected'],hardware_tested=False),ensure_ascii=True))
