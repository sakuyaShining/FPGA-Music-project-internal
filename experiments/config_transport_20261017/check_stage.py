"""Freeze source identities across the final verification groups."""
from common import *
import sys,os,time
group=sys.argv[1]
commands={
 'serial':[['check_host.py'],['check_transport.py'],['check_transport_host.py'],['check_serial_config.py'],['check_serial_config.py','nominal'],['check_serial_config.py','dual']],
 'core':[[name+'.py'] for name in ('check_engine_compat','check_enabled_compat','check_envelope','check_phase_wrap','check_music','check_faults')],
 'gui':[['-m','unittest','discover','-s','gui','-p','test_*.py']],
}[group]
tracked=list((R/'src').glob('*'))+list((R/'rtl').glob('*'))+list((R/'host').glob('*.py'))+list((R/'gui').glob('*.py'))+list(R.glob('*.py'))+list(R.glob('*.hex'))+list(R.glob('*.vh'))
before={p.relative_to(R).as_posix():sha(p) for p in tracked if p.is_file()}
env=dict(os.environ,PYTHONIOENCODING='utf-8',QT_QPA_PLATFORM='offscreen',PYTHONPATH=str(R/'scripts'))
results=[]
with (E/('matrix-'+group+'.log')).open('w',encoding='utf-8') as f:
 for args in commands:
    start=time.monotonic();command=[sys.executable,*args]
    out=subprocess.run(command,cwd=R,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',timeout=900)
    f.write('COMMAND '+repr(command)+'\n'+out.stdout+'\n');f.flush()
    results.append(dict(command=command,returncode=out.returncode,seconds=round(time.monotonic()-start,3)))
    print(group,args,'PASS' if out.returncode==0 else 'FAILED',flush=True)
    assert out.returncode==0,out.stdout
assert all(sha(R/p)==h for p,h in before.items()),'source changed during verification'
(E/('matrix-'+group+'.json')).write_text(json.dumps(dict(status='PASS exact recorded source identities',group=group,results=results,inputs=before),indent=2),encoding='utf-8')
