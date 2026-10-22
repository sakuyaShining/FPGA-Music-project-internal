"""Review-only native EasyEDA work, isolated from the original four-strip project."""
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = Path('C:/Users/Sakuya/FPGA-Music-project')
sys.path.insert(0, str(MAIN/'notes/hardware-selection-resume-20261015'))
import cli_runner
cli_runner.ROOT = ROOT
if os.environ.get('FPGA_EASYEDA_EXE'):
    cli_runner.EXE = Path(os.environ['FPGA_EASYEDA_EXE']).expanduser().resolve()
call = cli_runner.call
ORIGINAL = Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Slider-Prototype-20261015')
PROJECT = ORIGINAL.parent/'FPGA-Music-Dualscreen-Review-20261019'

def invoke(name, code, args=None, timeout=90):
    try:
        executable_available = cli_runner.EXE.is_file()
    except OSError as error:
        raise RuntimeError(
            f'Cannot access EasyEDA executable: {cli_runner.EXE}. '
            'Set FPGA_EASYEDA_EXE to an installed executable accessible to '
            'the current Windows account.') from error
    if not executable_available:
        raise FileNotFoundError(
            f'EasyEDA executable not found: {cli_runner.EXE}. '
            'Set FPGA_EASYEDA_EXE to the installed lceda-pro.exe path; '
            'recover a live session before invoking native operations.')
    session = json.loads((ROOT/'evidence/open.json').read_text(encoding='utf-8'))['value']['sessionId']
    if isinstance(args,dict) and (args.get('page') or args.get('pcb')):
        code="""const __taskTarget=__CLI__.args.page||__CLI__.args.pcb;const __taskCurrent=await eda.dmt_SelectControl.getCurrentDocumentInfo();if(__taskCurrent?.uuid!==__taskTarget){const __taskTab=await eda.dmt_EditorControl.openDocument(__taskTarget);if(!__taskTab)throw new Error('Target document not open');await new Promise(r=>setTimeout(r,1800));}\n"""+code
    if len(code) > 12000:
        code_path = ROOT/'evidence'/(name+'.js')
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text(code, encoding='utf-8')
        source_args = ['--code-file', str(code_path)]
    else:
        source_args = ['--code', code]
    command = ['invoke', '--session', session, *source_args,
               '--args', json.dumps(args or {}, ensure_ascii=True),
               '--timeout', str(min(1800000, int((timeout-10)*1000)))]
    # A fresh Windows profile has no historical extension named "eda".
    # The documented default executes with independent script permission.
    if os.environ.get('FPGA_EASYEDA_EXTENSION_UUID'):
        command += ['--ext-uuid', os.environ['FPGA_EASYEDA_EXTENSION_UUID']]
    return call(name, command, timeout)

def start():
    (ROOT/'evidence').mkdir(parents=True,exist_ok=True)
    if PROJECT.exists():
        raise RuntimeError('Review project already exists; do not overwrite')
    manifest={}
    PROJECT.mkdir()
    for p in ORIGINAL.rglob('*'):
        if not p.is_file() or 'exports' in p.as_posix():
            continue
        rel=p.relative_to(ORIGINAL)
        manifest[rel.as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
        target=PROJECT/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    old=PROJECT/(ORIGINAL.name+'.eprj3')
    data=json.loads(old.read_text(encoding='utf-8'))
    data['name']=PROJECT.name
    data['content']='Dual-screen carrier electrical review candidate. NOT RELEASED FOR FABRICATION.'
    new=PROJECT/(PROJECT.name+'.eprj3')
    new.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    old.unlink()  # only the redundant descriptor in the freshly created clone
    (ROOT/'evidence/original-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(call('doctor',['doctor','--json']))
    print(call('sessions',['session','list']))
    print(call('open',['open','--path',new.as_posix(),'--headless','true'],120))

if __name__=='__main__':
    if len(sys.argv)==1:
        start()
    else:
        request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        print(json.dumps(invoke(request['name'],request['code'],request.get('args'),request.get('timeout',90)),ensure_ascii=True))
