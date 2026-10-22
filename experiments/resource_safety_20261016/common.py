from pathlib import Path
import subprocess,hashlib,json
R=Path(__file__).resolve().parent;E=R/'evidence';E.mkdir(exist_ok=True)
IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def sources(variant='all'):
    files=[p for p in (R/'engine').glob('*.v') if p.name!='pitch_mod.v']+list((R/'rtl').glob('*.v'))+list((R/'candidate').glob('*.v'))+[R/'optimization/pitch_mod.v',R/'optimization/note_map_owned.v']
    replacements={}
    if variant in ('anchor','both','all'):replacements['finger_pitch.v']=R/'selected/finger_pitch.v'
    if variant in ('identity','both','all'):replacements['note_map_owned.v']=R/'selected/note_map_owned.v'
    if variant=='all':replacements['left_contact_bridge.v']=R/'selected/left_contact_bridge.v'
    return [replacements.get(p.name,p) for p in files]
def run(cmd,name,cwd=R):
    result=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
    log=result.stdout+result.stderr;(E/(name+'.log')).write_text(log,encoding='utf-8')
    assert result.returncode==0,(name,log)
    if name.startswith('run'):print(log.strip(),flush=True)
    return log
def record(name,data,files):
    data['inputs']={p.relative_to(R).as_posix():sha(p) for p in set(files)}
    (E/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
