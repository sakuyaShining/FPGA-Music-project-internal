from common import *
files=list((R/'rtl').glob('*.v'))+[R/'tb/sdram_timing_model.v',R/'tb/tb_board.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']};results={}
for delay in (3,10,16):
 D=E/('board-delay%d'%delay);D.mkdir(exist_ok=True)
 run([IV,'-g2012','-DTIMING_RTL_SIM','-s','tb_board','-Ptb_board.ACCESS_DELAY='+str(delay),'-o',str(D/'test.vvp'),*map(str,files)],'compile-board%d'%delay)
 out=subprocess.run([VVP,str(D/'test.vvp')],cwd=D,capture_output=True,text=True,timeout=120)
 (D/'run.log').write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,out.stdout+out.stderr
 results[str(delay)]=out.stdout;print(out.stdout)
text=(R/'rtl/sdram_board_top.v').read_text();faults={
 'wrong-record-pattern':('.pcm_data(pattern(rec_count,rec_salt))',".pcm_data(pattern(rec_count,rec_salt)^16'h1)",'bench failed code=1'),
 'wrong-play-pattern':('.feed_data(pattern(feed_count,play_salt))',".feed_data(pattern(feed_count,play_salt)^16'h1)",'bench failed code=2'),
 'wrong-frame-checksum':('snapshot[504+:8]=checksum;','snapshot[504+:8]=checksum^1;', 'frame identity/checksum')}
detected={}
for name,(old,new,reason) in faults.items():
 assert text.count(old)==1
 fault=E/(name+'.v');fault.write_text(text.replace(old,new))
 D=E/name;D.mkdir(exist_ok=True)
 fs=[fault if p.name=='sdram_board_top.v' else p for p in files]
 run([IV,'-g2012','-DTIMING_RTL_SIM','-s','tb_board','-o',str(D/'test.vvp'),*map(str,fs)],'compile-'+name)
 out=subprocess.run([VVP,str(D/'test.vvp')],cwd=D,capture_output=True,text=True,timeout=120)
 (D/'run.log').write_text(out.stdout+out.stderr,encoding='utf-8')
 assert out.returncode!=0 and reason in out.stdout,(name,out.stdout)
 detected[name]=out.stdout
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'board-model.json').write_text(json.dumps(dict(status='PASS stage83 synthetic board wrapper, UART frames, six cases and simulated S2 inflight restart; three faults detected',results=results,detected_faults=detected,inputs=inputs,physical_tested=False,pll_simulated=False),indent=2),encoding='utf-8')
