"""Bind source, actual tests/synthesis and unchanged protected product inputs."""
import hashlib,json,re,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
FEATURE=PROJECT/'experiments/right_hand_faders_20261016'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
backup=Path((ROOT/'latest-backup.txt').read_text(encoding='utf-8'))
original=json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
protected={}
for label,entry in original.items():
 repo=Path(entry['root'])
 assert sha(Path(entry['zip']))==entry['zip_sha256']
 drift=[name for name,value in entry['files'].items() if not (repo/name).exists() or sha(repo/name)!=value]
 assert not drift,(label,drift)
 protected[label]=dict(root=str(repo),head=entry['head'],files=len(entry['files']),original_files_unchanged=True)
verification=json.loads((FEATURE/'evidence/validation.json').read_text(encoding='utf-8'))
assert all(sha(FEATURE/name)==value for name,value in verification['input_sha256'].items())
ui=json.loads((FEATURE/'evidence/ui-validation.json').read_text(encoding='utf-8'))
assert ui['status'].startswith('PASS') and len(ui['checks'])==11
assert all(p['frames']==620 for p in verification['profiles'].values())
resources={}
for profile in ('generic','panel'):
 folder=FEATURE/'synthesis'/profile
 assert all(sha(folder/p.name)==sha(p) for p in (FEATURE/'rtl').glob('*.v'))
 console=(folder/'synthesis-console.txt').read_text(encoding='utf-8-sig',errors='replace')
 assert 'GowinSynthesis finish' in console and 'ERROR' not in console
 report=folder/'impl/gwsynthesis/faders_syn.rpt.html'
 text=report.read_text(encoding='utf-8')
 hierarchy=folder/'impl/gwsynthesis/faders_syn_rsc.xml'
 data=ET.parse(hierarchy).getroot().attrib
 resources[profile]=dict(logic=int(re.search(r'>Logic</td>\s*<td>(\d+)',text)[1]),registers=int(data['T_Register'].split('(')[0]),bsram=int(re.search(r'>BSRAM</td>\s*<td>(\d+)',text)[1]),report_sha256=sha(report),hierarchy_sha256=sha(hierarchy),physical_pins_or_pnr_verified=False)
inputs={p.relative_to(FEATURE).as_posix():sha(p) for p in FEATURE.rglob('*') if p.is_file() and p.suffix in ('.py','.v','.mjs','.html','.md') and not any(s in ('evidence','synthesis','__pycache__') for s in p.relative_to(FEATURE).parts)}
captures={p.relative_to(FEATURE).as_posix():sha(p) for p in (FEATURE/'evidence').iterdir() if p.is_file()}
for profile in ('generic','panel'):
 for name in ('faders.gprj','synth.tcl','synthesis-console.txt'):
  p=FEATURE/'synthesis'/profile/name;captures[p.relative_to(FEATURE).as_posix()]=sha(p)
docs=[p for p in (PROJECT/'docs/02-技术方案').glob('66-*.md')]
result=dict(version='right-hand-faders-20261016-01',status='Isolated digital and browser prototype verified; product integration partial',backup=str(backup),protected=protected,inputs=inputs,captures=captures,notes_inputs={p.name:sha(p) for p in ROOT.glob('*.py')},documentation={str(p):sha(p) for p in docs},actual_validation=dict(rule_unit_tests=11,rtl_reference_frames=2480,browser_model_same_input_cases=2480,browser_ui_checks=11,profiles=verification['profiles']),standalone_synthesis=resources,prototype_semantics=dict(sides_and_midpoint='user confirmed',per_fader_partition='user required',horizontal_distance='explicit prototype interpretation',range='adjustable and clipped to disjoint zone in prototype',cross_zone_range_policy='follow-up clarification pending'),not_verified=['real touch module/driver','audio mapping and smoothing','live layers/backing and tail scope','joint synthesis and PnR','physical pinout/power/noise','physical touch-to-sound latency'],board_downloaded=False,old_engine_modified=False,existing_gui_replaced=False,preview='http://127.0.0.1:8766/')
(FEATURE/'delivery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(protected={k:v['files'] for k,v in protected.items()},unchanged=True,resources=resources,source_files=len(inputs),rtl_frames=2480,ui_checks=11,physical_product_verified=False),ensure_ascii=True))
