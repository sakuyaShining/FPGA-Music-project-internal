"""Close only verified stage facts; never rewrite a historical product snapshot."""
from pathlib import Path
import hashlib,json,re,zipfile
import xml.etree.ElementTree as ET
N=Path(__file__).resolve().parent;P=N.parents[1];R=P/'experiments/system_integration_20261016'
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
upstream=read(R/'upstream.json')
for name,digest in upstream['inputs'].items():assert sha(P/name)==digest,name
origin=read(R/'source-engine.json')
for name,digest in origin['files'].items():
    assert sha(Path(origin['root'])/name)==digest,name
    assert sha(R/'engine'/Path(name).name)==digest,name

records={}
for name,tokens in [('validation.json',['scanner','positions','sensor','scan_budget']),('joint-validation.json',['compat','joint']),('serial-glide-validation.json',[]),('serial-joint-validation.json',[])]:
    item=read(R/'evidence'/name)
    for path,digest in item['inputs'].items():assert sha(R/path)==digest,(name,path)
    if tokens:
        for token in tokens:assert 'PASS ' in item['results'][token],(name,token)
    else:assert 'PASS ' in item['log'],name
    records[name]=item
vector=read(R/'vector-reference.json')
assert vector['generator_sha256']==sha(R/'generate_vectors.py')
for name,digest in vector['vectors'].items():assert sha(R/name)==digest,name

# Original reference copies differ only in module/instance names.
O=R/'optimization'
expected_ref=(R/'engine/pitch_mod.v').read_text(encoding='utf-8').replace('module pitch_mod #(','module pitch_mod_reference #(')
assert expected_ref==(O/'pitch_mod_reference.v').read_text(encoding='utf-8')
expected_ref=(R/'engine/tdm_engine.v').read_text(encoding='utf-8').replace('module tdm_engine #(','module tdm_engine_reference #(').replace('    pitch_mod #(','    pitch_mod_reference #(')
assert expected_ref==(O/'tdm_engine_reference.v').read_text(encoding='utf-8')
expected_ref=(R/'engine/tdm_top.v').read_text(encoding='utf-8').replace('module tdm_top #(','module tdm_top_reference #(').replace('    tdm_engine #(','    tdm_engine_reference #(')
assert expected_ref==(O/'tdm_top_reference.v').read_text(encoding='utf-8')

resources={}
for profile,wanted in [('sensor',(1545,1445,2)),('joint',(20175,9652,41)),('joint_serial',(17234,9706,41))]:
    D=R/'synthesis'/profile;inputs=read(D/'inputs.json');run=read(D/'run.json')
    assert run['exit_code']==0,profile
    assert run['inputs_manifest_sha256']==sha(D/'inputs.json'),profile
    for name,digest in inputs.items():
        assert sha(D/name)==digest,(profile,name)
        if profile=='joint_serial' and name=='pitch_mod.v':source=O/name
        else:source=(R/'engine'/name) if (R/'engine'/name).exists() else R/'rtl'/name
        assert sha(source)==digest,(profile,'source',name)
    text=(D/'synthesis-console.txt').read_text(encoding='utf-8',errors='replace')
    assert 'GowinSynthesis finish' in text and 'ERROR (' not in text,profile
    # No newly introduced implicit-size truncation warnings in sensor modules.
    for line in text.splitlines():
        if 'WARN' in line and any(s in line for s in ['rc_delta_store.v','rc_strip_positions.v','rc_mux_scan.v','scan_shift595.v']):
            raise AssertionError(line)
    html=(D/'impl/gwsynthesis/probe_syn.rpt.html').read_text(encoding='utf-8',errors='replace')
    logic=int(re.search(r'>Logic</td>\s*<td>(\d+)',html)[1]);ram=int(re.search(r'>BSRAM</td>\s*<td>(\d+)',html)[1])
    reg=int(ET.parse(D/'impl/gwsynthesis/probe_syn_rsc.xml').getroot().attrib['T_Register'].split('(')[0])
    assert (logic,reg,ram)==wanted,(profile,logic,reg,ram)
    resources[profile]=dict(logic=logic,register=reg,bsram=ram,pnr_tested=False,resource_limit_logic=20736)

source_files={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and not any(x in ('impl','__pycache__','evidence') for x in p.relative_to(R).parts) and p.suffix in ('.v','.vh','.hex','.json','.py','.md','.gprj','.tcl') and p.name not in ('delivery.json','run.json')}
evidence={p.relative_to(R).as_posix():sha(p) for p in R.rglob('*') if p.is_file() and ((p.parent==R/'evidence' and p.suffix in ('.json','.log')) or ('impl' in p.relative_to(R).parts and p.suffix in ('.log','.html','.xml','.vg')) or p.name in ('synthesis-console.txt','run.json'))}
docs={p.relative_to(P).as_posix():sha(p) for prefix in ['39-','49-','68-'] for p in (P/'docs/02-技术方案').glob(prefix+'*.md')}
data=dict(status='部分实现',digital_stage_verified=True,physical_hardware_tested=False,pnr_tested=False,sensor_to_note_bridge=False,original_sources_preserved=True,source_engine=origin,protected_counts={k:len(v['files']) for k,v in backup.items()},backup=str(b),resource_results=resources,scan_budget=dict(grant_delay0_cycles=50192,grant_delay64_cycles=54288,clock_hz=27000000,two_ms_target_pass_for_delay64=False,end_to_end_latency_tested=False),source_files=source_files,evidence=evidence,design_documents=docs,stage_scripts={p.relative_to(P).as_posix():sha(p) for p in N.glob('*.py')},initial_resource_archive_sha256=sha(N/'initial-resource-probe.zip'),next='输入实例与接收/分配反馈，再配置/分层及存储资源接合')
(R/'delivery.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS stage provenance and recorded checks only',protected_counts=data['protected_counts'],resources=resources,source_files=len(source_files),product_status=data['status']),ensure_ascii=False))
