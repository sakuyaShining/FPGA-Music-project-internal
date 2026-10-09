"""Required joined regressions, including preservation of the newer source queues."""
import json
from pathlib import Path
import subprocess
import sys
import regress_all as r

ROOT=Path(r.ROOT)
OUT=ROOT/'sim_build/closure'


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    r.BUILD=str(OUT/'rtl')
    top=[str(p) for p in (ROOT/'src/rtl').glob('*.v')]
    checks=[]
    for tb, marker in [('protocol_join','RESULT protocol_join=PASS'),
                       ('padfast','RESULT padfast=PASS'),
                       ('event_sources','RESULT event_sources=PASS'),
                       ('evhold_stream','RESULT evhold_stream=PASS'),
                       ('i2c_master','RESULT i2c_basic=PASS'),
                       ('i2c_contract','RESULT i2c_contract=PASS')]:
        source=top+[str(ROOT/'src/sim'/('tb_'+tb+'.v'))]
        if tb.startswith('i2c'): source.append(str(ROOT/'src/sim/mpr121_model.v'))
        log,err=r.compile_and_run(tb,source,defines=('SIM_INIT',),need_hex=True)
        content=err or log or ''
        (OUT/(tb+'.txt')).write_text(content,encoding='utf-8')
        ok=not err and marker in content and 'FAIL' not in content
        checks.append(dict(name=tb,passed=ok));print(tb,'PASS' if ok else 'FAIL',flush=True)
    for name,command in [('host',[sys.executable,'-m','unittest','discover','-s','tools/host','-p','test_*.py']),
                         ('finger',[sys.executable,'tools/scripts/finger_pitch_check.py']),
                         ('gui',[sys.executable,'tools/host/dsp_gui.py','--selftest'])]:
        result=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (OUT/(name+'.txt')).write_bytes(result.stdout)
        checks.append(dict(name=name,passed=result.returncode==0))
        print(name,'PASS' if result.returncode==0 else 'FAIL',flush=True)
    (OUT/'results.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf-8')
    return int(not all(c['passed'] for c in checks))


if __name__=='__main__':raise SystemExit(main())
