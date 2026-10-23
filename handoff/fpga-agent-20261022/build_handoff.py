"""Assemble a new FPGA handoff; never mutates main, 06df or the sealed candidate."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,zipfile

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
C=ROOT/'experiments/nano20k_feasibility_20261021'
MAIN=Path('C:/Users/Sakuya/FPGA-Music-project')
HW=Path('C:/Users/Sakuya/.codex/worktrees/06df/FPGA-Music-project/hardware/review-manufacturing-20261019')
OUT=Path('D:/FPGA-Project/codex-deliverables/fpga-agent-handoff-20261022-v1')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
J=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
origins={}
def cp(src,rel):
    src=Path(src);dst=OUT/rel;assert src.is_file(),str(src)
    b=src.read_bytes();dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(b)
    origins[dst.relative_to(OUT).as_posix()]=dict(path=str(src),sha256=hashlib.sha256(b).hexdigest())
def seal():
    files={}
    for p in sorted(OUT.rglob('*')):
        if p.is_file() and p.name!='MANIFEST.json' and '__pycache__' not in p.parts:
            files[p.relative_to(OUT).as_posix()]=dict(sha256=sha(p),bytes=p.stat().st_size)
    data=dict(package='fpga-agent-handoff-20261022-v1',scope='FPGA source work, no hardware programming',
              files=files,excluded=['Gowin/Icarus installers','generated .fs/.vg/.vvp','other chats native PCB project/session ownership'],
              product_complete=False,product_qualified=False,bench_gate=False)
    (OUT/'MANIFEST.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('SEALED',len(files),'files',sum(v['bytes'] for v in files.values()),'bytes')

ap=argparse.ArgumentParser();ap.add_argument('action',choices=('assemble','seal','archive'));a=ap.parse_args()
if a.action=='assemble':
    assert not OUT.exists(),'Refuse to overwrite an existing handoff'
    OUT.mkdir(parents=True)
    d=J(C/'delivery.json')
    for rel,h in d['source_files'].items():
        assert sha(C/rel)==h,('Sealed source drift',rel)
        cp(C/rel,Path('candidate_source')/rel)
    # The old delivery's source_files list omitted constraints (its build_files
    # and source-identity still bind them). Include and cross-check them here.
    run=J(C/'build_nominal_v0/run.json')
    source_identity=J(C/'source-identity.json')['files']
    for p in (C/'constraints').rglob('*'):
        if p.is_file():
            rel=p.relative_to(C).as_posix();assert sha(p)==source_identity[rel]
            cp(p,Path('candidate_source')/rel)
    for name,v in run['inputs'].items():
        assert sha(OUT/'candidate_source'/v['source'])==v['sha256'],('Missing or changed actual build input',name)
    cp(C/'delivery.json','state/original-delivery.json')
    for p in HERE.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:cp(p,p.relative_to(HERE))
    for p in (MAIN/'docs/02-技术方案').glob('*.md'):
        prefix=p.name.split('-',1)[0]
        if prefix.isdigit() and 38<=int(prefix)<=86:cp(p,Path('docs')/p.name)
    for n in (87,88):
        p=next((ROOT/'docs/02-技术方案').glob(str(n)+'-*.md'));cp(p,Path('docs')/p.name)
    for name in ('results.json','budget.json','critical-paths.json','resource-allocations.csv','setup-critical-path.csv','hold-critical-path.csv','source-identity.json'):
        cp(C/name,Path('state')/name)
    cp(ROOT/'notes/nano20k-next-stage-20261022/verilog-size.json','state/verilog-size.json')
    for rel,h in d['evidence_files'].items():
        assert sha(C/rel)==h,('Sealed evidence drift',rel)
        p=C/rel
        if p.suffix in ('.json','.log','.tsv'):cp(p,Path('baseline_evidence')/p.name)
    B=C/'build_nominal_v0'
    for rel,h in d['build_files'].items():
        p=C/rel;assert sha(p)==h,('Sealed build drift',rel)
        if p.name in ('board.gprj','build.tcl','run.json','console.log','board_syn_rsc.xml','board_syn.rpt.html','board.rpt.txt','board.pin.html','board_tr_content.html','board.log','sdram_board.cst','sdram_board.sdc'):
            cp(p,Path('baseline_build')/p.relative_to(B))
    U=MAIN/'experiments/resource_safety_20261016';gold=J(U/'evidence/music-equivalence-all.json')
    for name in ('sustain.hex','strike.hex','tb_compat_music.v','tb_layers.v','tb_sensor_layers.v','evidence/music-equivalence-all.json'):
        cp(U/name,Path('support/resource_safety_20261016')/name)
    for name in ('compat','layers','sensor'):
        p=U/'evidence'/(name+'-all.tsv');assert sha(p)==gold['traces'][name+'-all']['sha256']
        cp(p,Path('support/resource_safety_20261016/evidence')/p.name)
    cp(MAIN/'experiments/pitch_memory_20261018/tb/tb_pitch_memory.v','support/pitch_memory_20261018/tb/tb_pitch_memory.v')
    for name in ('row_vectors.hex','meta_vectors.hex','expected_vectors.hex','tb_positions.v','tb_sensor.v','tb_scan_budget.v'):
        cp(MAIN/'experiments/system_integration_20261016'/name,Path('support/system_integration_20261016')/name)
    U=MAIN/'experiments/register_memory_20261018'
    for name in ('check_envelope.py','check_phase_wrap.py','tb_envelope.v','tb_phase_wrap.v'):
        cp(U/name,Path('support/additional_tests')/name)
    # Save a current pointer as a snapshot; pending native transactions remain
    # owned by the hardware chat, never resolved or restored by this builder.
    pointer=HW/'REGIONAL-WORK-IN-PROGRESS.json';pointer_bytes=pointer.read_bytes();h=json.loads(pointer_bytes)
    cp(pointer,'hardware/latest-entry.json')
    for key in ('source_capture','readme','review','drc'):
        p=Path(h[key]);cp(p,Path('hardware/checkpoint')/p.name)
    for name in ('expected-pin-nets.json','harness-contract.csv','供电与模块接口-v2.md','屏幕出货配置核对-20261020.md','ACTIVE-ROUTING-CANDIDATE.json'):
        cp(HW/name,Path('hardware')/name)
    for p in (HW/'hardware-contract-20261021-r1').iterdir():
        if p.is_file():cp(p,Path('hardware/interface-adapters')/p.name)
    capture=J(Path(h['source_capture']));pads={(p['ref'],str(p['n'])):p['net'] for p in capture['pads']}
    expected=J(HW/'expected-pin-nets.json');checked=[]
    for ref in ('J5','J6','U8','U9','U10','U11','U12','U14','U15','U16'):
        for n,net in expected[ref].items():
            assert pads[(ref,n)]==(net or ''),(ref,n)
            checked.append(dict(reference=ref,pin=n,net=net))
    (OUT/'hardware/pin-contract-audit.json').write_text(json.dumps(dict(status='PASS current captured pin/net ABI only',pins=checked,
        pcb_checkpoint_sha256=h['pcb_sha256'],not_signal_integrity_or_manufacturing=True),ensure_ascii=False,indent=2),encoding='utf-8')
    native=Path(h['project'])/'pcb/PCB1.epcb2';native_sha=sha(native) if native.is_file() else None
    status=dict(checkpoint_declared_sha256=h['pcb_sha256'],checkpoint_declared_drc=h['native_drc'],
        native_path=str(native),native_read_sha256=native_sha,native_matches_declared_checkpoint=native_sha==h['pcb_sha256'],
        pointer_sha256=hashlib.sha256(pointer_bytes).hexdigest(),pending_trial=h.get('pending_trial'),
        rule='Pointer snapshot and pending trial are distinct. Do not promote, restore, re-run or edit another hardware transaction. ABI audit covers captured pins, not live geometry.',
        old87_checkpoint_sha256=J(C/'budget.json')['hardware_checkpoint']['pcb_sha256'],manufacturing_release=False)
    if h.get('pending_trial'):
        p=Path(h['pending_trial']['entry'])
        if p.is_file():cp(p,'hardware/pending-native-state.json')
        archive=Path(h['pending_trial']['source_archive'])
        if archive.is_file():status['verified_checkpoint_archive']=dict(path=str(archive),sha256=sha(archive))
    (OUT/'hardware/hardware-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    assert pointer.read_bytes()==pointer_bytes,'Hardware pointer changed while copying; keep this failed package and make a new version'
    catalog={}
    for folder in ('instrument_config_20261017','config_transport_20261017','envelope_resources_20261017','register_memory_20261018','sdram_timing_20261018','sdram_stream_board_20261018'):
        root=MAIN/'experiments'/folder
        catalog[folder]=dict(root=str(root),checks={p.name:sha(p) for p in root.glob('check*.py')},
                            warning='Supplementary source-version-specific suites. Not all external dependencies copied; review before adapting to current DUT.')
    toolpaths=['C:/Program Files/python/python.exe','D:/iverilog/bin/iverilog.exe','D:/iverilog/bin/vvp.exe',
        'D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe']
    source_map=dict(origin_workspace=str(ROOT),main=str(MAIN),hardware_root=str(HW),
        git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        worktree_warning='87/88/candidate are untracked local work at handoff; HEAD alone does not contain them.',
        tools={p:dict(exists=Path(p).is_file(),sha256=sha(Path(p)) if Path(p).is_file() else None) for p in toolpaths},
        extra_regression_catalog=catalog,original_inputs=origins,
        limitation='M1 core sources, models, goldens and selected supplementary tests are self-contained; host GUI/whole vendor installation/full historical test suites/native CAD recovery packages remain external and are catalogued, not claimed bundled.')
    (OUT/'source-map.json').write_text(json.dumps(source_map,ensure_ascii=False,indent=2),encoding='utf-8')
    seal()
elif a.action=='seal':
    assert OUT.is_dir();seal()
else:
    assert OUT.is_dir();manifest=J(OUT/'MANIFEST.json')
    for rel,v in manifest['files'].items():assert sha(OUT/rel)==v['sha256'],rel
    archive=OUT.parent/(OUT.name+'.zip');assert not archive.exists(),'Refuse to overwrite archive'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for rel in manifest['files']:z.write(OUT/rel,rel)
        z.write(OUT/'MANIFEST.json','MANIFEST.json')
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for rel,v in manifest['files'].items():assert hashlib.sha256(z.read(rel)).hexdigest()==v['sha256'],rel
    checksum=dict(archive=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,files=len(manifest['files'])+1)
    (archive.parent/(OUT.name+'-sha256.json')).write_text(json.dumps(checksum,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checksum,ensure_ascii=False))
