import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('C:/Users/Sakuya/.codex/worktrees/ca03/FPGA-Music-project')
OUT = Path(__file__).resolve().parent
RELEASE = Path('D:/FPGA-Project/host-workbench-20261015-11')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

checks = json.loads((OUT/'checks.json').read_text(encoding='utf-8'))
assert checks['status'] == 'PASS'
backup = Path((OUT/'latest-backup.txt').read_text(encoding='utf-8'))
if not backup.is_absolute():
    backup = Path('C:/Users/Sakuya/FPGA-Music-project') / backup
before = json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
allowed = {'tools/host/workbench.py', 'tools/host/config_editor.py'}
changed = [name for name,h in before['files'].items() if not (ROOT/name).exists() or sha(ROOT/name) != h]
assert set(changed) <= allowed, changed
protected = {name:h for name,h in before['files'].items() if name.startswith(('src/','project/','tools/scripts/'))}
assert all(sha(ROOT/name)==h for name,h in protected.items())
assert not RELEASE.exists(), 'Refuse to overwrite a release'
RELEASE.mkdir(parents=True)
identity_path = ROOT/'tools/host/host_version.json'
identity = json.loads(identity_path.read_text(encoding='utf-8'))
identity['previous_version'] = identity['version']
identity['version'] = RELEASE.name
identity['change_scope'] = '高级工具窗口自适应、固定关闭/部分应用、草稿文件菜单及状态；不改变RTL或音频协议'
identity['verification'] = dict(offline_host_tests=100, layout_dpi=[1,1.25,1.5,2],
    device_tested_this_release=False, scope=checks['scope'], protected_files=len(protected))
for name in list(identity['inputs']):
    identity['inputs'][name] = sha(ROOT/name)
for path in (ROOT/'tools/host').glob('*.py'):
    identity['inputs'][path.relative_to(ROOT).as_posix()] = sha(path)
identity_path.write_text(json.dumps(identity,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'source-review.json').write_text(json.dumps(dict(changed_existing=changed,
    protected_files=len(protected), protected_unchanged=True,
    backup=str(backup), source_identity=identity),ensure_ascii=False,indent=2),encoding='utf-8')
env = dict(os.environ, FPGA_HOST_BUILD_ROOT=str(RELEASE), QT_QPA_PLATFORM='offscreen',
           QT_QPA_FONTDIR='C:/Windows/Fonts', PYTHONIOENCODING='utf-8')
with (RELEASE/'build.log').open('wb') as log:
    result = subprocess.run([sys.executable, '-X', 'utf8', 'tools/host/build_exe.py'],cwd=ROOT,
                            env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
print(json.dumps(dict(build_exit=result.returncode, release=str(RELEASE), log=str(RELEASE/'build.log')),ensure_ascii=False))
sys.exit(result.returncode)
