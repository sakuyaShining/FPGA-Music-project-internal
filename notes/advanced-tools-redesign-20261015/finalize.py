import difflib
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT=Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')
OUT=Path(__file__).resolve().parent
RELEASE=Path('D:/FPGA-Project/host-workbench-20261015-11')
EVIDENCE=RELEASE/'evidence'
EVIDENCE.mkdir(exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

backup=Path((OUT/'latest-backup.txt').read_text(encoding='utf-8'))
if not backup.is_absolute():backup=Path('C:/Users/Sakuya/FPGA-Music-project')/backup
before=json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
identity=json.loads((ROOT/'tools/host/host_version.json').read_text(encoding='utf-8'))
assert all(sha(ROOT/name)==digest for name,digest in identity['inputs'].items())
protected={n:h for n,h in before['files'].items() if n.startswith(('src/','project/','tools/scripts/'))}
assert all(sha(ROOT/name)==digest for name,digest in protected.items())
assert 'RESULT build_exe=PASS' in (RELEASE/'build.log').read_text(encoding='utf-8')
for name in ('gui_preview.png','selftest_report.txt','normal-startup.json','normal-startup.png',
             'workbench-selftest.json','advanced-tools-preview.png'):
    shutil.copy2(ROOT/'sim_build/gui'/name,EVIDENCE/name)
for name in ('normal-startup.json','workbench-selftest.json'):
    assert json.loads((EVIDENCE/name).read_text(encoding='utf-8'))['status']=='PASS'
assert json.loads((EVIDENCE/'workbench-selftest.json').read_text(encoding='utf-8'))['advanced_dialog']
for path in OUT.iterdir():
    if path.is_file() and path.suffix in ('.py','.json','.log','.txt'):
        shutil.copy2(path,EVIDENCE/path.name)
patch=[]
with zipfile.ZipFile(backup/'before.zip') as z:
    for name in ('tools/host/workbench.py','tools/host/config_editor.py'):
        patch.extend(difflib.unified_diff(z.read(name).decode('utf-8').splitlines(True),
            (ROOT/name).read_text(encoding='utf-8').splitlines(True),fromfile='before/'+name,tofile='after/'+name))
(EVIDENCE/'ui-changes.patch').write_text(''.join(patch),encoding='utf-8')
source=RELEASE/'host-source-11.zip'
with zipfile.ZipFile(source,'w',zipfile.ZIP_DEFLATED) as z:
    for path in (ROOT/'tools/host').rglob('*'):
        if path.is_file() and not any(p in ('__pycache__','build','dist') for p in path.relative_to(ROOT).parts):
            z.write(path,path.relative_to(ROOT).as_posix())
    for name in identity['inputs']:
        if not name.startswith('tools/host/'):
            z.write(ROOT/name,name)
    for name in ('docs/02-技术方案/regmap_baseline.csv','docs/05-上位机/高级工具窗口重设计-20261015.md'):
        z.write(ROOT/name,name)
with zipfile.ZipFile(source) as z:assert z.testzip() is None
copied=[]
for relative in ('instrument.json','sim_build/gui/display_preferences.json'):
    old=Path('D:/FPGA-Project/host-workbench-20261015-10')/relative
    new=RELEASE/relative
    if old.exists() and not new.exists():
        new.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(old,new)
        assert sha(old)==sha(new)
        copied.append(relative)
record=dict(version=identity['version'],source_head=before['head'],source_worktree=str(ROOT),
    source_is_uncommitted=True,exe=str(RELEASE/'dist/fpga_workbench.exe'),
    exe_sha256=sha(RELEASE/'dist/fpga_workbench.exe'),source_zip=str(source),source_zip_sha256=sha(source),
    source_inputs_verified=True,protected_files=len(protected),protected_unchanged=True,
    main_baseline='192 inputs PASS, no changes',backup=str(backup),
    checks=json.loads((OUT/'checks.json').read_text(encoding='utf-8')),
    frozen_selftest='PASS',frozen_workbench_selftest='PASS including advanced dialog',frozen_normal_startup='PASS',
    copied_saved_files=copied,interactive_session_replaced=False,
    hardware_or_audio_tested_this_release=False,
    limitations=['完整激励/包络/物理单位效果配置仍未接入','设备非易失保存未实现','未执行新板测或模拟输出试听'])
(OUT/'delivery.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
(EVIDENCE/'delivery.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:record[k] for k in ('version','exe','exe_sha256','protected_files','protected_unchanged','copied_saved_files')},ensure_ascii=False))
