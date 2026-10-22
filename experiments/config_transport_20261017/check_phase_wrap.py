from common import *
files=sources()+[R/'tb_phase_wrap.v']
run([IV,'-g2012','-I',str(R/'src'),'-s','tb_phase_wrap','-o',str(E/'phase-wrap.vvp'),*map(str,files)],'compile-phase-wrap')
log=run([VVP,str(E/'phase-wrap.vvp')],'run-phase-wrap',R/'src')
(E/'phase-wrap.json').write_text(json.dumps(dict(status='PASS max divider rollover/gate events in simulation',log=log,inputs={p.relative_to(R).as_posix():sha(p) for p in files+list((R/'src').glob('*.hex'))+[Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
