"""Verify this stage, preserving original sources and all earlier snapshots."""
from pathlib import Path
import hashlib,json,re,subprocess,sys,zipfile
import xml.etree.ElementTree as ET
N=Path(__file__).resolve().parent;P=N.parents[1];R=P/'experiments/left_hand_events_20261016';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
b=Path((N/'latest-backup.txt').read_text(encoding='utf-8').strip());backup=read(b/'manifest.json')
for item in backup.values():
    assert sha(Path(item['archive']))==item['sha256']
    with zipfile.ZipFile(item['archive']) as z:
        assert z.testzip() is None
        for name,digest in item['files'].items():
            assert sha(Path(item['root'])/name)==digest,name
            assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
upstream=read(R/'upstream.json');U=Path(upstream['root'])
assert sha(U/'delivery.json')==upstream['delivery_sha256']
for name,digest in upstream['files'].items():
    assert sha(U/name)==digest,name
    if not name.startswith('project/'):
        assert sha(R/name)==digest,('copied code',name)
origin=read(R/'source-engine.json')
for name,digest in origin['files'].items():
    assert sha(Path(origin['root'])/name)==digest,name
    assert sha(R/'engine'/Path(name).name)==digest,name

for name in ['validation.json','music-validation.json','sensor-music-validation.json','serial-validation.json']:
    record=read(E/name)
    for path,digest in record['inputs'].items():assert sha(R/path)==digest,(name,path)
    logs=record.get('results',record.get('logs',{}))
    if not logs:logs={'sensor_music':record['log']}
    assert logs,name
    for key,text in logs.items():assert 'PASS ' in text,(name,key)
derived=read(E/'derivation-check.json')
for path,digest in derived['files'].items():assert sha(R/path)==digest,('derived',path)
for path,digest in derived['generators'].items():assert sha(R/path)==digest,('generator',path)
assert (R/'optimization/note_map_owned_parallel.v').read_text(encoding='utf-8')==(R/'candidate/note_map_owned.v').read_text(encoding='utf-8').replace('module note_map_owned #(','module note_map_owned_parallel #(')

resources={}
for profile,expected in [('bridge',(1690,1518,0)),('owned_joint',(19758,11923,41)),('owned_serial',(19621,11928,41))]:
    D=R/'synthesis'/profile;inputs=read(D/'inputs.json');run=read(D/'run.json')
    assert run['exit_code']==0 and run['inputs_sha256']==sha(D/'inputs.json'),profile
    for name,data in inputs.items():
        assert sha(D/name)==data['sha256'],(profile,name)
        assert sha(R/data['source'])==data['sha256'],(profile,'source',name)
    text=(D/'synthesis-console.txt').read_text(encoding='utf-8',errors='replace')
    assert 'GowinSynthesis finish' in text and 'ERROR (' not in text,profile
    for line in text.splitlines():
        assert not ('WARN' in line and 'EX3791' in line and any(x in line for x in ['left_contact_bridge.v','note_map_owned.v','tdm_top_owned.v'])),line
    html=(D/'impl/gwsynthesis/probe_syn.rpt.html').read_text(encoding='utf-8',errors='replace')
    logic=int(re.search(r'>Logic</td>\s*<td>(\d+)',html)[1]);ram=int(re.search(r'>BSRAM</td>\s*<td>(\d+)',html)[1])
    reg=int(ET.parse(D/'impl/gwsynthesis/probe_syn_rsc.xml').getroot().attrib['T_Register'].split('(')[0])
    assert (logic,reg,ram)==expected,(profile,logic,reg,ram)
    resources[profile]=dict(logic=logic,register=reg,bsram=ram,logic_limit=20736,pnr_tested=False)

# Identity checks are captured now, rather than upgraded from a historical PASS.
for label,cwd,args in [('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',Path(origin['root']),['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]:
    r=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (E/('identity-'+label+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,(label,r.stdout,r.stderr)

source_files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and not any(x in ('impl','evidence','__pycache__') for x in p.relative_to(R).parts) and p.suffix in ('.v','.vh','.hex','.py','.md','.json','.gprj','.tcl') and p.name not in ('delivery.json','run.json')}
evidence={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and ((p.parent==E and p.suffix in ('.json','.log')) or ('impl' in p.relative_to(R).parts and p.suffix in ('.log','.html','.xml','.vg')) or p.name in ('synthesis-console.txt','run.json'))}
docs={p.relative_to(P).as_posix():sha(p) for prefix in ['38-','39-','49-','69-'] for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
delivery=dict(status='部分实现',digital_sensor_to_pcm_verified=True,physical_hardware_tested=False,display_refresh_tested=False,pnr_tested=False,original_sources_preserved=True,source_engine=origin,upstream_delivery_sha256=upstream['delivery_sha256'],backup=str(b),protected_counts={k:len(v['files']) for k,v in backup.items()},resources=resources,remaining=dict(logic=1115,bsram=5,full_product_capacity_verified=False),source_files=source_files,evidence=evidence,design_documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},next='最小完整配置/激励包络与双层实例；进一步资源/存储接合')
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS stage provenance/recorded digital checks only',protected_counts=delivery['protected_counts'],source_files=len(source_files),resources=resources,hardware_tested=False),ensure_ascii=True))
