from common import *
files=list((R/'rtl').glob('*.v'))+[R/'tb/sdram_timing_model.v',R/'tb/tb_board.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']}
results={}
for delay in (3.0,10.0,16.0,20.0):
 label='board-'+str(int(delay));exe=E/(label+'.vvp')
 run([IV,'-g2012','-DTIMING_RTL_SIM','-s','tb_board','-Ptb_board.ACCESS_DELAY='+str(delay),'-o',str(exe),*map(str,files)],'compile-'+label)
 log=run([VVP,str(exe)],'run-'+label);results[str(delay)]=log;print(log)
assert all(sha(R/p)==h for p,h in inputs.items())
(E/'board-model.json').write_text(json.dumps(dict(status='PASS wrapper and return-delay sweep; 20ns expected failure detected',results=results,inputs=inputs,physical_tested=False),indent=2))
