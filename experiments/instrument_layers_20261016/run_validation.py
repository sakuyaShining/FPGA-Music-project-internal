from pathlib import Path
import subprocess,json,hashlib
R=Path(__file__).resolve().parent;E=R/'evidence';E.mkdir(exist_ok=True)
IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
def sources():
    return [p for p in (R/'engine').glob('*.v') if p.name!='pitch_mod.v']+list((R/'rtl').glob('*.v'))+list((R/'candidate').glob('*.v'))+[R/'optimization/pitch_mod.v',R/'optimization/note_map_owned.v']
def run(cmd,name,cwd=R):
    out=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240)
    text=out.stdout+out.stderr;(E/(name+'.log')).write_text(text,encoding='utf-8')
    assert out.returncode==0,(name,text)
    if name.startswith('run'):print(text.strip(),flush=True)
    return text
if __name__=='__main__':
    results={}
    for name,top,tb in [('compat','tb_music','tb_compat_music.v'),('layers','tb_layers','tb_layers.v'),('sensor_layers','tb_sensor_layers','tb_sensor_layers.v')]:
        run([IV,'-g2012','-I',str(R/'rtl'),'-s',top,'-o',str(E/(name+'.vvp')),*map(str,sources()),str(R/tb)],'compile-'+name)
        results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name,R/'engine');assert 'PASS ' in results[name]
    inputs=sources()+list(R.glob('*.hex'))+list((R/'engine').glob('*.hex'))+list((R/'rtl').glob('*.vh'))+list(R.glob('tb_*.v'))+[Path(__file__).resolve()]
    (E/'validation.json').write_text(json.dumps(dict(status='PASS digital music only',hardware_tested=False,results=results,inputs={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}),indent=2),encoding='utf-8')
