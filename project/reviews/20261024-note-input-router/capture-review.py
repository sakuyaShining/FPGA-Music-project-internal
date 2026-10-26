from pathlib import Path
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys

ROOT=Path('C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project')
EXPORT=Path('D:/FPGA-Project/review')
REVIEW=ROOT/'project/reviews/20261024-note-input-router'
AREA=ROOT/'experiments/note_resource_20261024/input'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes((json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


def copy(source,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():
        raise ValueError('Never overwrite evidence: '+str(target))
    target.write_bytes(source.read_bytes())


if REVIEW.exists():
    raise ValueError('Use a fresh review')
if shutil.disk_usage(ROOT).free<8*1024*1024:
    raise ValueError('System disk below8MiB; final sources/results remain on D, do not delete history')
final_paths=[EXPORT/'note-input-router-20261024-01/results.json',EXPORT/'note-duet-audio-20261024-05/results.json',
             EXPORT/'note-duet-cancel-fault-20261024-01/results.json',EXPORT/'note-duet-synthesis-20261024-03/results.json']
for path in final_paths:
    result=load(path)
    assert result['status'].startswith('PASS') and not result['source_changes'],str(path)
    for name,expected in result['inputs'].items():
        assert sha(ROOT/name)==expected,name
observation=load(EXPORT/'input-route-observation-20261024-02.json')
previous=load(ROOT/'project/reviews/20261024-note-partial-renderer/observation-followup.json')
producer=next(item for item in load(ROOT/'project/producers.json')['producers'] if item['id']=='hardware')
hardware=Path(producer['root'])
changes={}
for name,current in observation['producers'].items():
    before,after=previous['producers'][name]['files'],current['files']
    changes[name]=dict(added=sorted(set(after)-set(before)),removed=sorted(set(before)-set(after)),
        modified=[path for path in after if path in before and before[path]['sha256']!=after[path]['sha256']])
for name in changes['hardware']['modified']:
    assert sha(hardware/name)==observation['producers']['hardware']['files'][name]['sha256'],name
state_name='u8-power-corridor-20261022/address3-local-recovery/retained-control-recovery/u9-layout/construction-state.json'
state=load(hardware/state_name)
supplement=hardware/'u8-power-corridor-20261022/address3-local-recovery/retained-control-recovery/u9-layout/address1-joint-fanout/calibrated-local-next.json'
calibrated=load(supplement)
copy(EXPORT/'input-route-observation-20261024-01.json',REVIEW/'observation-initial.json')
copy(EXPORT/'input-route-observation-20261024-02.json',REVIEW/'observation.json')
write(REVIEW/'producer-changes.json',changes)
write(REVIEW/'hardware-context.json',dict(changed_sources={name:observation['producers']['hardware']['files'][name] for name in changes['hardware']['modified']},
    selected_state={key:state.get(key) for key in ('updated_at','phase','pcb_sha256','drc','open_nets','actual_vias','physical_tests','manufacturing_release','native_changed_this_heartbeat','all_current_routing_jobs_terminal')},
    supplemental_source=dict(relative=supplement.relative_to(hardware).as_posix(),sha256=sha(supplement),observed_at=datetime.now(timezone.utc).isoformat(),
        selected={key:calibrated.get(key) for key in ('updated_at','state','source_pcb_sha256','native_changed','native_connections','native_open_nets','summary','local_review_pass','ADDR2_trunk_complete','full_board_review_pass','native_import_allowed','manufacturing_release','physical_tests')}),
    assessment='Native a3a258/49issues/13nets/620vias unchanged. Owner corrected offline removed-via ground-antipad reconstruction and reports a locally admissible U1 ADDR3/ADDR2 escape candidate; ADDR2 still7 pad islands, no native import/full-board acceptance. Historical failures are not all attributed to this model defect. All existing manufacturing gates remain. Reviewer read selected provenance only, no CAD/DRC or PCB edits.',
    privacy='No live session handles/full conversations copied; supplemental file is a frozen technical observation outside the registry watch scope.',new_cad_operations=False,manufacturing_release=False))

source=EXPORT/'note-input-router-20261024-01'
copy(source/'results.json',REVIEW/'validation/router/results.json')
copy(source/'INPUTS.json',REVIEW/'validation/router/INPUTS.json')
router=load(source/'results.json')
for case in router['results']:
    label=case['case']
    for name in ('compile.log','run.log','trace.tsv.gz','note_event_router.v'):
        copy(source/label/name,REVIEW/'validation/router'/label/name)
    assert hashlib.sha256(gzip.decompress((source/label/'trace.tsv.gz').read_bytes())).hexdigest()==case['trace_sha256']
for name in ('inputs.hex','expected.hex'):
    (REVIEW/'validation/router'/('candidate-'+name+'.gz')).write_bytes(gzip.compress((source/'candidate'/name).read_bytes(),mtime=0))
for number in (1,2,3,4,5):
    source=EXPORT/('note-duet-audio-20261024-%02d'%number)
    target=REVIEW/('validation/audio%02d'%number)
    for name in ('results.json','INPUTS.json','compile.log','run.log','trace.tsv.gz','note_duet_probe-before-fix.v',
                 'tb_duet_audio.v','tb_duet_audio-before-settle-fix.v','verify_audio.py','verify_audio-before-fault-guard.py','tb_duet_audio-before-fault-guard.v'):
        if (source/name).is_file():
            copy(source/name,target/name)
source=EXPORT/'note-duet-cancel-fault-20261024-01'
for name in ('results.json','INPUTS.json','compile.log','run.log','trace.tsv.gz','note_duet_probe.v'):
    copy(source/name,REVIEW/'validation/queued-cancel-fault'/name)
for source_name,target_name in [('input-before-queued-cancel-fix-20261024','before-queued-cancel')]:
    source=EXPORT/source_name
    for path in source.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts:
            copy(path,REVIEW/'historical-tools'/target_name/path.relative_to(source))
old_build=(AREA/'build.py').read_text(encoding='utf-8').replace("    shutil.copyfile(Path(__file__).resolve(),output/'build-tool.py')\n",'')
(REVIEW/'historical-tools/build-before-self-capture.py').write_bytes(old_build.encode())
timing=[]
for mode,count,prefix in [('timing',4,'note-input-router-timing'),('synthesis',3,'note-duet-synthesis')]:
    for number in range(1,count+1):
        source=EXPORT/('%s-20261024-%02d'%(prefix,number))
        target=REVIEW/('build/%s%02d'%(mode,number))
        result=load(source/'results.json')
        for name in ('results.json','console.log','router.gprj','build.tcl','build-tool.py','note_router_timing_probe.v','router_probe.sdc','router_probe.cst',
                     'impl/pnr/router.log','impl/gwsynthesis/router_syn.rpt.html','impl/gwsynthesis/router_syn_resource.html'):
            if (source/name).is_file():
                copy(source/name,target/name)
        if mode=='timing':
            assert not result['status'].startswith('PASS')
            timing.append(dict(attempt=number,status=result['status'],returncode=result['returncode'],slack_ns=result['slack_ns']))
primary=(EXPORT/'note-duet-synthesis-20261024-03/impl/gwsynthesis/router_syn.rpt.html').read_text(encoding='utf-8')
logic=re.search(r'<td>(\d+)\((\d+) LUT, (\d+) ALU, (\d+) RAM16\) /',primary)
registers=re.search(r'>Register</td>\s*<td>(\d+) /',primary)
bsram=re.search(r'>BSRAM</td>\s*<td>(\d+) /',primary)
assert logic and registers and bsram
resources=dict(zip(('logic','LUT','ALU','RAM16'),map(int,logic.groups())))
resources.update(REG=int(registers.group(1)),BSRAM=int(bsram.group(1)))
write(REVIEW/'build/summary.json',dict(resources=resources,integrated_synthesis='Final03 same inputs PASS only',timing_attempts=timing,
    diagnosis='01/02 wrapper syntax errors;03/04 router process0xC0000005 at80% despite fixed-pin/four-bit method change. No routed timing reports; no valid STA or complete product qualification. Do not infer a resource-fit cause from this crash.',
    integrated02_rejection='Vendor run exit0 but helper changed during execution, so source-change guard correctly returnedFAIL;03 rerun without changes.',full_product_fit=False,pnr=False,valid_sta=False,programming_allowed=False))
environment=dict(os.environ,GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='safe.directory',GIT_CONFIG_VALUE_0=str(ROOT),PYTHONIOENCODING='utf-8',TEMP=str(EXPORT/'input-gowin-temp-20261024-02'),TMP=str(EXPORT/'input-gowin-temp-20261024-02'))
suites=[]
for name,directory,pattern,expected in [('governance','tools/tests','test_design_governance.py',20),('engineering','tools/tests','test_engineering.py',6),
    ('profiles','tools/tests','test_music_profiles.py',14),('resource','experiments/note_resource_20261024/tests','test_reference.py',8),
    ('audio','experiments/note_resource_20261024/audio/tests','test_audio_guards.py',5),('renderer','experiments/note_resource_20261024/audio/renderer/tests','test_renderer.py',7),
    ('input','experiments/note_resource_20261024/input/tests','test_input_router.py',8)]:
    command=[sys.executable,'-m','unittest','discover','-s',directory,'-p',pattern,'-v']
    process=subprocess.run(command,cwd=ROOT,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    target=REVIEW/'validation/unit'/(name+'.log');target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(process.stdout)
    assert process.returncode==0 and ('Ran %d tests'%expected).encode() in process.stdout,name
    suites.append(dict(name=name,command=command,tests=expected,returncode=0,log=target.relative_to(ROOT).as_posix(),sha256=sha(target)))
write(REVIEW/'validation/unit/results.json',dict(status='PASS',tests=68,suites=suites))
write(REVIEW/'capture-results.json',dict(status='CAPTURED',resources=resources,tests=68,product_acceptance=False))
copy(Path(__file__).resolve(),REVIEW/'capture-review.py')
print(json.dumps(dict(status='CAPTURED',resources=resources,tests=68)))
