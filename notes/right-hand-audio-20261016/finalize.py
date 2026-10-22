"""Verify provenance, protected sources, tested inputs and all resource outcomes.

This creates a NEW isolated delivery manifest. It does not update product snapshots.
"""
import hashlib,json,re,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
ROOT=PROJECT/'experiments/right_hand_audio_20261016'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
backup=Path((HERE/'latest-backup.txt').read_text(encoding='utf-8').strip())
protected=read(backup/'manifest.json')
for item in protected.values():
    assert sha(Path(item['archive']))==item['archive_sha256']
    with zipfile.ZipFile(item['archive']) as z:
        assert z.testzip() is None
        for name,digest in item['files'].items():
            assert hashlib.sha256(z.read(name)).hexdigest()==digest,name
            assert sha(Path(item['root'])/name)==digest,name

origin=read(ROOT/'source-engine.json')
for name,digest in origin['files'].items():
    assert sha(Path(origin['root'])/name)==digest,name
    assert sha(ROOT/'engine'/Path(name).name)==digest,name

validation=read(ROOT/'evidence/validation.json')
assets=read(ROOT/'evidence/assets-check.json')
assert assets['generated_data_unchanged']
for key,name in [('generator_sha256','generate_assets.py'),('lut_sha256','fader_gain_q8.hex'),('config_sha256','audition-config.json')]:
    assert assets[key]==sha(ROOT/name),name
exceptions=[]
for name,digest in validation['inputs'].items():
    if sha(ROOT/name)!=digest:
        assert name=='generate_assets.py',name
        assert assets['lut_sha256']==validation['inputs']['fader_gain_q8.hex']
        exceptions.append(dict(path=name,reason=assets['reason'],verification='evidence/assets-check.json'))
for name,token in [('control','PASS control'),('engine','PASS engine'),('music','PASS music')]:
    assert token in (ROOT/f'evidence/run-{name}.log').read_text(encoding='utf-8')

external=ROOT/'synthesis/external_input_visualizer'
overlay=read(external/'overlay.json')
assert overlay['preserved_candidate_unchanged']
assert overlay['before_sha256']==sha(ROOT/'engine/tdm_top_rh.v')
assert overlay['after_sha256']==sha(external/'tdm_top_rh.v')
before=(ROOT/'engine/tdm_top_rh.v').read_text(encoding='utf-8')
assert before.count(overlay['removed'])==1
assert before.replace(overlay['removed'],overlay['inserted'])==(external/'tdm_top_rh.v').read_text(encoding='utf-8')
ext_validation=read(ROOT/'evidence/external-input-validation.json')
assert ext_validation['overlay_sha256']==sha(external/'overlay.json')
assert ext_validation['new_physical_left_frontend_included'] is False
for name,digest in ext_validation['inputs'].items():assert sha(ROOT/name)==digest,name
assert 'PASS music' in (ROOT/'evidence/run-external-input-music.log').read_text(encoding='utf-8')

# Verify copied synthesis inputs against the actual originating bytes.
source_by_name={p.name:p for p in (ROOT/'engine').glob('*') if p.suffix in ('.v','.hex')}
for folder in [ROOT/'rtl',PROJECT/'experiments/right_hand_faders_20261016/rtl',PROJECT/'experiments/music_visualizer_20261015/rtl']:
    source_by_name.update({p.name:p for p in folder.glob('*') if p.suffix in ('.v','.vh')})
source_by_name.update({p.name:p for p in (PROJECT/'experiments/music_visualizer_20261015').glob('*1024.hex')})
source_by_name['rh_music_visualizer_probe.v']=ROOT/'rh_music_visualizer_probe.v'
source_by_name['fader_gain_q8.hex']=ROOT/'fader_gain_q8.hex'
for profile in ['control','music','music_visualizer','external_input_visualizer']:
    for p in (ROOT/'synthesis'/profile).iterdir():
        if p.suffix not in ('.v','.vh','.hex'):continue
        if profile=='external_input_visualizer' and p.name=='tdm_top_rh.v':continue
        assert p.name in source_by_name,p
        assert sha(p)==sha(source_by_name[p.name]),p

resources={}
for profile,expected in [('control',(1407,1210,1)),('music',(18595,7366,32)),('external_input_visualizer',(18292,8207,39))]:
    folder=ROOT/'synthesis'/profile
    report=folder/'impl/gwsynthesis/probe_syn.rpt.html'
    html=report.read_text(encoding='utf-8',errors='replace')
    logic=int(re.search(r'>Logic</td>\s*<td>(\d+)',html)[1])
    ram=int(re.search(r'>BSRAM</td>\s*<td>(\d+)',html)[1])
    reg=int(ET.parse(folder/'impl/gwsynthesis/probe_syn_rsc.xml').getroot().attrib['T_Register'].split('(')[0])
    assert (logic,reg,ram)==expected,profile
    log=(folder/'synthesis-console.txt').read_text(encoding='utf-8',errors='replace')
    assert 'GowinSynthesis finish' in log and 'ERROR (' not in log,profile
    resources[profile]=dict(status='synthesis_complete_only',logic=logic,register=reg,bsram=ram,pnr_tested=False)
resources['external_input_visualizer']['new_physical_left_frontend_included']=False
failure=(ROOT/'synthesis/music_visualizer/synthesis-console.txt').read_text(encoding='utf-8',errors='replace')
assert 'RP0006' in failure and '21658' in failure and '20736' in failure
resources['music_visualizer']=dict(status='FAILED_RP0006',logic=21658,limit=20736,excess=922,pnr_tested=False)

sources={p.relative_to(ROOT).as_posix():sha(p) for p in ROOT.rglob('*') if p.is_file() and not any(s in ('impl','evidence','__pycache__') for s in p.relative_to(ROOT).parts) and p.suffix in ('.v','.vh','.hex','.py','.json','.md','.gprj','.tcl') and p.name!='delivery.json'}
dependencies={p.relative_to(PROJECT).as_posix():sha(p) for p in source_by_name.values() if ROOT not in p.parents}
evidence={p.relative_to(ROOT).as_posix():sha(p) for p in ROOT.rglob('*') if p.is_file() and (('evidence' in p.relative_to(ROOT).parts and p.suffix in ('.json','.log')) or ('impl' in p.relative_to(ROOT).parts and p.suffix in ('.html','.xml','.log','.vg')) or p.name=='synthesis-console.txt')}
notes={p.relative_to(PROJECT).as_posix():sha(p) for p in HERE.glob('*.py')}
docs={p.relative_to(PROJECT).as_posix():sha(p) for prefix in ['39-','49-','67-'] for p in (PROJECT/'docs/02-技术方案').glob(prefix+'*.md')}
record=dict(status='partially_implemented_product; isolated_digital_behavior_verified; legacy_combined_resource_failed',physical_hardware_tested=False,pnr_tested=False,original_sources_preserved=True,source_engine=origin,backup=str(backup),protected_counts={k:len(v['files']) for k,v in protected.items()},verified_input_exceptions=exceptions,resource_results=resources,source_files=sources,upstream_dependencies=dependencies,evidence=evidence,implementation_scripts=notes,design_documents=docs)
(ROOT/'delivery.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS delivery/provenance only',protected_counts=record['protected_counts'],source_files=len(sources),resource_results=resources),ensure_ascii=False))
