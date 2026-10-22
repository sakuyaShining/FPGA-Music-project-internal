"""Write a new delivery only after current inputs and recorded checks agree."""
from pathlib import Path
import hashlib,json,zipfile,re,filecmp,subprocess,sys,concurrent.futures
import xml.etree.ElementTree as ET
N=Path(__file__).resolve().parent;P=N.parents[1];R=P/'experiments/resource_safety_20261016';E=R/'evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
b=Path((N/'latest-backup.txt').read_text(encoding='utf-8'));backup=read(b/'manifest.json')
allowed={p.relative_to(P).as_posix() for prefix in ('38-','39-','49-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
with zipfile.ZipFile(b/'before.zip') as z:
    assert z.testzip() is None
    for name,digest in backup.items():
        assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
        if name not in allowed:assert sha(P/name)==digest,('protected input',name)
up=read(R/'upstream.json');U=Path(up['root'])
assert sha(U/'delivery.json')==up['delivery_sha256']
for name,digest in up['files'].items():assert sha(U/name)==digest,('upstream',name)
previous=N.parent/'left-hand-events-20261016';old_b=Path((previous/'latest-backup.txt').read_text(encoding='utf-8').strip());counts={}
for label,item in read(old_b/'manifest.json').items():
    counts[label]=len(item['files']);assert sha(Path(item['archive']))==item['sha256']
    for name,digest in item['files'].items():assert sha(Path(item['root'])/name)==digest,('original source',label,name)
gates=['units.json','bridge-equivalence.json','fault-detection.json','music-equivalence-all.json','derivations.json']
for name in gates:
    record=read(E/name);assert record['status'].startswith('PASS'),name
    for rel,digest in record.get('inputs',{}).items():assert sha(R/rel)==digest,(name,rel)
    for rel,digest in record.get('files',{}).items():assert sha(R/rel)==digest,(name,rel)
    for rel,digest in record.get('generators',{}).items():assert sha(P/rel)==digest,(name,rel)
fault=read(E/'fault-detection.json');assert len(fault['results'])==3
for item in fault['results'].values():assert item['returncode']!=0 and item['failure'] in item['log']
music=read(E/'music-equivalence-all.json')
for key,item in music['traces'].items():
    trace=E/(key+'.tsv');assert sha(trace)==item['sha256'] and trace.stat().st_size==item['bytes'],key
for name in ('compat','layers','sensor'):
    assert filecmp.cmp(E/(name+'-reference.tsv'),E/(name+'-all.tsv'),shallow=False),name
resources={}
for profile in ('synthesis_reference','synthesis_both','synthesis_all','synthesis_all_clean'):
    D=R/profile;record=read(D/'run.json')
    assert record['returncode']==0 and record['project_sha256']==sha(D/'probe.gprj') and record['tcl_sha256']==sha(D/'synth.tcl'),profile
    for name,item in record['inputs'].items():
        assert sha(D/name)==item['sha256'],(profile,name)
        if profile in ('synthesis_reference','synthesis_all_clean'):assert sha(R/item['source'])==item['sha256'],('final build source',profile,name)
    log=(D/'console.txt').read_text(encoding='utf-8',errors='replace');assert 'ERROR (' not in log and 'GowinSynthesis finish' in log
    if profile=='synthesis_all_clean':
        for line in log.splitlines():
            assert not ('WARN' in line and 'EX3791' in line and any(x in line for x in ('finger_pitch.v','note_map_owned.v','left_contact_bridge.v'))),line
    html=(D/'impl/gwsynthesis/probe_syn.rpt.html').read_text(encoding='utf-8',errors='replace')
    metrics={key:int(re.search('>'+key+r'</td>\s*<td>(\d+)',html)[1]) for key in ('Logic','BSRAM')}
    xml=ET.parse(D/'impl/gwsynthesis/probe_syn_rsc.xml').getroot()
    metrics['Register']=int(xml.get('T_Register').split('(')[0]);assert metrics==record['metrics']
    resources[profile]=dict(status='已验证：仅综合',metrics=metrics,pnr_tested=False)
assert resources['synthesis_reference']['metrics']==dict(Logic=20668,BSRAM=43,Register=12604)
assert resources['synthesis_all_clean']['metrics']==dict(Logic=19892,BSRAM=43,Register=11120)
ref=read(R/'synthesis_reference/run.json');sel=read(R/'synthesis_all_clean/run.json')
assert ref['project_sha256']==sel['project_sha256']
assert set(ref['inputs'])==set(sel['inputs'])
changed={name for name in ref['inputs'] if ref['inputs'][name]['sha256']!=sel['inputs'][name]['sha256']}
assert changed=={'finger_pitch.v','note_map_owned.v','left_contact_bridge.v'},changed
refxml=ET.parse(R/'synthesis_reference/impl/gwsynthesis/probe_syn_rsc.xml').getroot();selxml=ET.parse(R/'synthesis_all_clean/impl/gwsynthesis/probe_syn_rsc.xml').getroot()
assert {k:v for k,v in refxml.attrib.items() if k.startswith('T_MULT')}=={k:v for k,v in selxml.attrib.items() if k.startswith('T_MULT')}
origin=read(U/'delivery.json')['source_engine'];engine=Path(origin['root'])
jobs=[('main',P,['tools/scripts/project_baseline.py','--check','notes/baselines/main-2026-10-09-board-diag.json']),('engine',engine,['tools/scripts/project_version.py','check','project/versions/engine-safety-20261014-01.json'])]
def identity(job):
    label,cwd,args=job
    out=subprocess.run([sys.executable,*args],cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace');(E/('identity-'+label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8')
    assert out.returncode==0,(label,out.stdout,out.stderr)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:list(executor.map(identity,jobs))
source_files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and not any(x in p.relative_to(R).parts for x in ('impl','evidence','__pycache__')) and p.name not in ('delivery.json','run.json','console.txt') and p.suffix in ('.v','.vh','.hex','.py','.md','.json','.gprj','.tcl')}
evidence={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and p.suffix in ('.log','.json','.txt','.html','.xml','.vg') and (p.parent==E or p.name in ('console.txt','run.json') or 'impl' in p.relative_to(R).parts)}
docs={p.relative_to(P).as_posix():sha(p) for prefix in ('38-','39-','49-','71-') for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
delivery=dict(version='resource-safety-20261016-v0',status='部分实现',optimization_status='已验证：记录的数字场景与综合',selected_variant='all',hardware_tested=False,pnr_tested=False,source_engine=origin,upstream_delivery_sha256=up['delivery_sha256'],backup=dict(directory=str(b),files=len(backup),zip_sha256=sha(b/'before.zip')),protected_counts=counts,gates=gates,resources=resources,savings=dict(logic=776,register=1484,bsram=0),remaining=dict(logic=844,bsram=3,full_product_capacity_verified=False),source_files=source_files,evidence=evidence,design_documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},next='逐层完整包络/设备配置能力、非易失与TF/SDRAM录放接合')
(R/'delivery.json').write_text(json.dumps(delivery,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS current gates/provenance only',source_files=len(source_files),protected_counts=counts,resources=resources['synthesis_all_clean'],savings=delivery['savings'],hardware_tested=False),ensure_ascii=True))
