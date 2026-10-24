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
import zipfile

ROOT = Path('C:/Users/Sakuya/.codex/worktrees/4d37/FPGA-Music-project')
AREA = ROOT / 'experiments/note_resource_20261024/audio/renderer'
REVIEW = ROOT / 'project/reviews/20261024-note-partial-renderer'
EXPORT = Path('D:/FPGA-Project/review')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if '--resume-exact' in sys.argv and target.read_bytes() == source.read_bytes():
            return
        raise ValueError('Never overwrite evidence: ' + str(target))
    target.write_bytes(source.read_bytes())


if (REVIEW / 'validation').exists() and '--resume-exact' not in sys.argv:
    raise ValueError('Never overwrite captured validation')
final = load(EXPORT / 'note-partial-renderer-20261024-03/results.json')
integrated = load(EXPORT / 'rendered-instrument-audio-20261024-03/results.json')
synthesis = load(EXPORT / 'rendered-instrument-synthesis-20261024-03/results.json')
for result in (final, integrated, synthesis):
    assert result['status'] in ('PASS', 'PASS_SYNTHESIS_ONLY') and not result['source_changes']
    for name, expected in result['inputs'].items():
        assert sha(ROOT / name) == expected, name
observation = load(REVIEW / 'observation-followup.json')
producer = next(item for item in load(ROOT / 'project/producers.json')['producers'] if item['id']=='hardware')
hardware_root = Path(producer['root'])
state_name = 'u8-power-corridor-20261022/address3-local-recovery/retained-control-recovery/u9-layout/construction-state.json'
assert sha(hardware_root / state_name)==observation['producers']['hardware']['files'][state_name]['sha256'],'Owner context changed; capture/review a new observation, never renew stale evidence'
state = load(hardware_root / state_name)

for number in (1, 2, 3):
    source = EXPORT / ('note-partial-renderer-20261024-%02d' % number)
    target = REVIEW / ('validation/renderer%02d' % number)
    result = load(source / 'results.json')
    assert result['status'] == 'PASS'
    for name in ('results.json', 'INPUTS.json'):
        copy(source / name, target / name)
    for case in result['results']:
        label = case['case']
        for name in ('compile.log', 'run.log', 'trace.tsv.gz', 'note_partial_renderer.v', 'vel_shape_scaled.v', 'vel_wtab.hex'):
            if (source / label / name).is_file():
                copy(source / label / name, target / label / name)
        for name in ('commands.txt', 'expected.json'):
            path = target / label / (name + '.gz')
            path.write_bytes(gzip.compress((source / label / name).read_bytes(), mtime=0))
        assert hashlib.sha256(gzip.decompress((target / label / 'trace.tsv.gz').read_bytes())).hexdigest() == case['trace_sha256']
    source = EXPORT / ('rendered-instrument-audio-20261024-%02d' % number)
    target = REVIEW / ('validation/instrument%02d' % number)
    for name in ('results.json', 'INPUTS.json', 'compile.log', 'run.log', 'trace.tsv.gz'):
        if (source / name).is_file():
            copy(source / name, target / name)
    source = EXPORT / ('rendered-instrument-synthesis-20261024-%02d' % number)
    target = REVIEW / ('synthesis/attempt%02d' % number)
    for name in ('results.json', 'console.log', 'instrument.gprj', 'synthesize.tcl',
                 'impl/gwsynthesis/instrument_syn.rpt.html', 'impl/gwsynthesis/instrument_syn_resource.html'):
        copy(source / name, target / name)

for label, source in [('before-velocity-fix', EXPORT / 'renderer-before-velocity-fix-20261024'),
                      ('before-config-priority-fix', EXPORT / 'renderer-before-config-priority-fix-20261024')]:
    files = {}
    for path in sorted(source.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            relative = path.relative_to(source)
            copy(path, REVIEW / 'historical-tools' / label / relative)
            files[relative.as_posix()] = sha(path)
    write(REVIEW / 'historical-tools' / (label + '.json'), dict(source=str(source), files=files,
        role='Exact pre-fix reproduction, not current acceptance; original test PASS did not cover the subsequently found defect.'))

source = EXPORT / 'velocity-scaling-20261024-02'
velocity = load(source / 'results.json')
assert velocity['status'] == 'PASS' and not velocity['source_changes']
for name, expected in velocity['inputs'].items():
    assert sha(ROOT / name) == expected, name
for name in ('results.json', 'INPUTS.json', 'compile.log', 'run.log', 'vel_shape.v', 'vel_shape_scaled.v', 'tb_velocity_scaling.v', 'vel_wtab.hex'):
    copy(source / name, REVIEW / 'validation/velocity02' / name)
for name in ('run.log',):
    copy(EXPORT / 'velocity-scaling-20261024-01' / name, REVIEW / 'validation/velocity01' / name)
write(REVIEW / 'validation/velocity01/limit.json', dict(role='Initial manual run; logs retained but no start-time source receipt. Final02 reruns the same component coverage with explicit source/tool hashes and commands.'))

guard = EXPORT / 'renderer-config-priority-counterexample-20261024-01'
assert not guard.exists()
guard.mkdir()
before = EXPORT / 'note-partial-renderer-20261024-02/captured/note_partial_renderer.v'
copy(before, guard / 'note_partial_renderer.v')
copy(AREA / 'tb/tb_partial_renderer.v', guard / 'tb_partial_renderer.v')
for name in ('commands.txt', 'note_inc.hex', 'preset_part.hex', 'tilt_wtab.hex', 'vel_wtab.hex'):
    copy(EXPORT / 'note-partial-renderer-20261024-03/captured' / name, guard / name)
guard_inputs = {path.name:sha(path) for path in guard.iterdir() if path.is_file()}
write(guard / 'INPUTS.json', guard_inputs)
compiler = Path('D:/iverilog/bin/iverilog.exe')
simulator = Path('D:/iverilog/bin/vvp.exe')
binary = guard / 'priority.vvp'
commands = [[str(compiler), '-g2012', '-s', 'tb_partial_renderer', '-o', str(binary),
             str(guard / 'note_partial_renderer.v'), str(AREA / 'rtl/vel_shape_scaled.v'),
             str(guard / 'tb_partial_renderer.v'), str(ROOT / 'fpga/current/engine/src/instrument_table.v')],
            [str(simulator), str(binary), '+commands='+(guard / 'commands.txt').as_posix(), '+trace='+(guard / 'trace.tsv').as_posix()]]
codes = []
for name, command in zip(('compile.log', 'run.log'), commands):
    process = subprocess.run(command, cwd=guard, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    (guard / name).write_bytes(process.stdout)
    codes.append(process.returncode)
assert codes[0] == 0 and codes[1] != 0 and b'configuration priority deadlock' in (guard / 'run.log').read_bytes()
write(guard / 'results.json', dict(status='DETECTED_AT_DESIGNATED_ASSERTION', commands=commands, returncodes=codes,
    inputs=guard_inputs, additional_inputs={str(path):sha(path) for path in (AREA / 'rtl/vel_shape_scaled.v',ROOT / 'fpga/current/engine/src/instrument_table.v')},
    tools={str(path):sha(path) for path in (compiler,simulator)}, reason='Old isolated renderer rejected both configuration and note when both valid; final03 accepts configuration first. Wrapper guarded this combination, but direct renderer contract was incorrect.'))
for name in ('INPUTS.json', 'results.json', 'compile.log', 'run.log', 'note_partial_renderer.v', 'tb_partial_renderer.v'):
    copy(guard / name, REVIEW / 'validation/config-priority-counterexample' / name)

traces = {str(number):load(EXPORT / ('rendered-instrument-audio-20261024-%02d/results.json' % number))['trace_sha256'] for number in (1,2,3)}
assert len(set(traces.values())) == 1
write(REVIEW / 'validation/default-trace-equality.json', dict(trace_sha256=traces,
    scope='Complete default-scale synthetic logical-note/config/PCM trace exactly unchanged across both fixes; not an independent PCM oracle or all control values.'))
primary = (EXPORT / 'rendered-instrument-synthesis-20261024-03/impl/gwsynthesis/instrument_syn.rpt.html').read_text(encoding='utf-8')
logic = re.search(r'<td>(\d+)\((\d+) LUT, (\d+) ALU, (\d+) RAM16\) /', primary)
registers = re.search(r'>Register</td>\s*<td>(\d+) /', primary)
bsram = re.search(r'>BSRAM</td>\s*<td>(\d+) /', primary)
assert logic and registers and bsram
resources = dict(zip(('logic','LUT','ALU','RAM16'),map(int,logic.groups())))
resources.update(REG=int(registers.group(1)),BSRAM=int(bsram.group(1)))
write(REVIEW / 'synthesis/summary.json', dict(resources=resources, scope=synthesis['scope'],
    dsp_note='Hierarchy reports local DSP contributions; do not add a standalone module resource count to claim complete-product fit. Consult primary exact report.',
    pnr=False, valid_sta=False, bitstream=False, complete_product_fit=False))

unit = []
environment = dict(os.environ, GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='safe.directory', GIT_CONFIG_VALUE_0=str(ROOT), PYTHONIOENCODING='utf-8')
for name, directory, pattern, expected in [('governance','tools/tests','test_design_governance.py',20),
    ('engineering','tools/tests','test_engineering.py',6),('music-profiles','tools/tests','test_music_profiles.py',14),
    ('resource','experiments/note_resource_20261024/tests','test_reference.py',8),
    ('audio','experiments/note_resource_20261024/audio/tests','test_audio_guards.py',5),
    ('renderer','experiments/note_resource_20261024/audio/renderer/tests','test_renderer.py',7)]:
    command = [sys.executable,'-m','unittest','discover','-s',directory,'-p',pattern,'-v']
    process = subprocess.run(command,cwd=ROOT,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=180)
    target = REVIEW / 'validation/unit' / (name+'.log')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(process.stdout)
    assert process.returncode == 0 and ('Ran %d tests'%expected).encode() in process.stdout,name
    unit.append(dict(name=name,command=command,tests=expected,returncode=0,log=target.relative_to(ROOT).as_posix(),sha256=sha(target)))
write(REVIEW / 'validation/unit/results.json',dict(status='PASS',tests=60,suites=unit))

observation = load(REVIEW / 'observation-followup.json')
previous = load(ROOT / 'project/reviews/20261024-note-resource-audio/observation-attempt02.json')
changes = {}
for name, current in observation['producers'].items():
    before, after = previous['producers'][name]['files'],current['files']
    changes[name] = dict(added=sorted(set(after)-set(before)),removed=sorted(set(before)-set(after)),
        modified=[path for path in after if path in before and before[path]['sha256']!=after[path]['sha256']])
write(REVIEW / 'producer-changes.json',changes)
archive_name = next(name for name in changes['hardware']['modified'] if name.endswith('construction-native-NOT-FOR-FAB.zip'))
archive = EXPORT / 'addr1-native-observation-20261024-a3.zip'
assert sha(archive)==observation['producers']['hardware']['files'][archive_name]['sha256']
copy(archive,REVIEW / 'hardware/construction-native-a3-NOT-FOR-FAB.zip')
with zipfile.ZipFile(archive) as zipped:
    assert zipped.testzip() is None
    entries = {name:dict(bytes=len(zipped.read(name)),sha256=hashlib.sha256(zipped.read(name)).hexdigest()) for name in zipped.namelist() if not name.endswith('/')}
assert entries['pcb/PCB1.epcb2']['sha256']==state['pcb_sha256']
write(REVIEW / 'hardware/native-manifest.json',dict(archive_sha256=sha(archive),source_relative=archive_name,entries=entries,
    role='Incremental saved owner-native recovery checkpoint; not a replacement for hardware/current or new CAD/DRC acceptance by this reviewer.'))
write(REVIEW / 'hardware-context.json',dict(schema=1,
    changed_sources={name:observation['producers']['hardware']['files'][name] for name in changes['hardware']['modified']},
    selected_state={name:state.get(name) for name in ('updated_at','phase','pcb_sha256','drc','open_nets','actual_vias','physical_tests','manufacturing_release','accepted_local_fanout_only','whole_board_verified','all_current_routing_jobs_terminal','latest_offline_work_state','offline_candidate_note')},
    assessment='Owner saved/reopened local ADDR1 U8.1/U2.11 fanout, +2signal/+2ground vias. Actual saved native a3a258/49issues/13nets/227components/620vias;49 includes2 pending trunk-via objects, not evidence of pad-island split. ADDR1 still7 pad islands. Trunk routing attempt failed and was not imported; do not retry unchanged bottleneck. Full native closure and manufacturing remain blocked. Original captured e098/47issues stays unchanged.',
    privacy='Selected technical context only, no live CAD/session handles or full private conversations.',
    new_cad_operations=False,manufacturing_release=False))
write(REVIEW / 'capture-results.json',dict(status='CAPTURED',tests=60,resources=resources,product_acceptance=False))
print(json.dumps(dict(status='CAPTURED',resources=resources,tests=60)))
