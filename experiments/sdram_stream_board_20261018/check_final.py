from common import *
files=list((R/'rtl').glob('*.v'))+[R/'tb/tb_final_check.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']}
run([IV,'-g2012','-DTIMING_RTL_SIM','-s','tb_final_check','-o',str(E/'final.vvp'),*map(str,files)],'compile-final')
log=run([VVP,str(E/'final.vvp')],'run-final');assert 'PASS 38' in log
(E/'final-check.json').write_text(json.dumps(dict(status='PASS 38 directed default-width final acceptance cases; all32 prefix bits; not a traffic test',log=log,inputs=inputs),indent=2))
print(log)
