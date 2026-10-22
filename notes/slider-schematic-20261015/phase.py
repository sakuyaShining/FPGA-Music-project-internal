"""Auditable EasyEDA prototype updates; no product RTL modifications."""
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'notes/hardware-selection-resume-20261015'))
import cli_runner
cli_runner.ROOT = ROOT
call = cli_runner.call
PROJECT = Path('C:/Users/Sakuya/Documents/LCEDA-Pro/projects/FPGA-Music-Slider-Prototype-20261015')

def invoke(name, code, args=None, timeout=75):
    session=json.loads((ROOT/'evidence/open.json').read_text(encoding='utf-8'))['value']['sessionId']
    return call(name,['invoke','--session',session,'--ext-uuid','eda','--code',code,
                     '--args',json.dumps(args or {}),'--timeout','60000'],timeout)

def start():
    evidence=ROOT/'evidence'; evidence.mkdir(parents=True,exist_ok=True)
    backup=evidence/'before-schematic.zip'
    if backup.exists(): raise RuntimeError('Do not overwrite pre-edit backup')
    files=[p for p in PROJECT.rglob('*') if p.is_file() and 'exports' not in p.as_posix()]
    with zipfile.ZipFile(backup,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(p,p.relative_to(PROJECT))
    with zipfile.ZipFile(backup) as z:assert z.testzip() is None
    manifest={'archive_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),
              'files':{p.relative_to(PROJECT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (evidence/'before-schematic.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(call('doctor',['doctor','--json']),ensure_ascii=True))
    print(json.dumps(call('sessions',['session','list']),ensure_ascii=True))
    print(json.dumps(call('open',['open','--path',str(PROJECT/(PROJECT.name+'.eprj3')),'--headless','true'],90),ensure_ascii=True))

if __name__=='__main__':start()
