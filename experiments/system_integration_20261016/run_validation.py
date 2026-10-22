"""Isolated digital tests; does not access a device or analog hardware."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent
E=ROOT/'evidence';E.mkdir(exist_ok=True)
IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
def run(cmd,name,cwd=ROOT,timeout=120):
    r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    (E/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
    assert r.returncode==0,(name,r.stdout+r.stderr)
    if name.startswith('run-'):print(r.stdout.strip(),flush=True)
    return r.stdout
if __name__=='__main__':
    results={}
    sensor_files=['scan_shift595.v','rc_mux_scan.v','rc_delta_store.v','rc_strip_positions.v','instrument_sensor_probe.v']
    for name,files in [('scanner',['scan_shift595.v','rc_mux_scan.v']),('positions',['rc_delta_store.v','rc_strip_positions.v']),('sensor',sensor_files),('scan_budget',sensor_files)]:
        tb=ROOT/('tb_'+name+'.v')
        if not tb.exists():continue
        run([IV,'-g2012','-Wall','-s','tb_'+name,'-o',str(E/(name+'.vvp')),*[str(ROOT/'rtl'/f) for f in files],str(tb)],'compile-'+name)
        results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name)
        assert 'PASS '+name in results[name]
    inputs=list((ROOT/'rtl').glob('*.v'))+list(ROOT.glob('tb_*.v'))+[Path(__file__).resolve()]+list(ROOT.glob('*vectors*.hex'))
    (E/'validation.json').write_text(json.dumps(dict(scope='digital tests only',hardware_tested=False,results=results,inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}),indent=2),encoding='utf-8')
