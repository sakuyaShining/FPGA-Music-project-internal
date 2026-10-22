"""Run owned allocator and bridge tests without hardware."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent;E=ROOT/'evidence';E.mkdir(exist_ok=True)
IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
def run(cmd,name,cwd=ROOT,timeout=180):
    r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    (E/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,(name,r.stdout+r.stderr)
    if name.startswith('run-'):print(r.stdout.strip(),flush=True)
    return r.stdout
if __name__=='__main__':
    results={}
    groups=[('allocator',[ROOT/'candidate/note_map_owned.v',ROOT/'engine/note_map.v',ROOT/'engine/vel_shape.v']),('bridge',[ROOT/'rtl/left_contact_bridge.v'])]
    for name,files in groups:
        tb=ROOT/('tb_'+name+'.v')
        if not tb.exists():continue
        run([IV,'-g2012','-s','tb_'+name,'-o',str(E/(name+'.vvp')),*[str(p) for p in files],str(tb)],'compile-'+name)
        results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name,cwd=ROOT/'engine')
        assert 'PASS '+name in results[name]
    inputs=list((ROOT/'candidate').glob('*.v'))+[ROOT/'rtl/left_contact_bridge.v']+list(ROOT.glob('tb_allocator.v'))+list(ROOT.glob('tb_bridge.v'))+[Path(__file__).resolve(),ROOT/'prepare_owned.py']
    (E/'validation.json').write_text(json.dumps(dict(scope='digital allocator/bridge only',results=results,inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}),indent=2),encoding='utf-8')
