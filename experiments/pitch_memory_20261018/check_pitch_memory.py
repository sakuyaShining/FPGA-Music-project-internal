from common import *
old=R/'reference/pitch_mod.v';ref=E/'pitch_mod_reference.v'
ref.write_text(old.read_text(encoding='utf-8').replace('module pitch_mod #(','module pitch_mod_reference #(',1),encoding='utf-8')
files=[R/'engine/src/pitch_mod.v',ref,R/'tb/tb_pitch_memory.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[old,Path(__file__).resolve(),R/'common.py']};results={}
for ng,qw,seed in ((2,18,91),(8,18,113),(32,18,17),(32,20,99)):
 name='pitch-%d-%d'%(ng,qw);cmd=[IV,'-g2012','-s','tb_pitch_memory','-Ptb_pitch_memory.NG='+str(ng),'-Ptb_pitch_memory.QW='+str(qw),'-Ptb_pitch_memory.SEED='+str(seed),'-o',str(E/(name+'.vvp')),*map(str,files)]
 run(cmd,'compile-'+name);results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name)
text=files[0].read_text(encoding='utf-8');faults={
 'lost-command-priority':('from_command[gw_note]<=1','from_command[gw_note]<=0','logical storage mismatch'),
 'leaked-reset-data':("(from_command[rd_note]?command_mem[rd_note]:materialized_mem[rd_note]):{QW{1'b0}}", "(from_command[rd_note]?command_mem[rd_note]:materialized_mem[rd_note]):command_mem[rd_note]",'pitch output mismatch')}
detected={}
for label,(before,after,reason) in faults.items():
 assert text.count(before)==1,label
 f=E/(label+'.v');f.write_text(text.replace(before,after),encoding='utf-8')
 run([IV,'-g2012','-s','tb_pitch_memory','-o',str(E/(label+'.vvp')),str(f),str(ref),str(files[2])],'compile-'+label)
 out=subprocess.run([VVP,str(E/(label+'.vvp'))],cwd=R,capture_output=True,text=True,timeout=120)
 (E/(label+'.log')).write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode!=0 and reason in out.stdout,(label,out.stdout)
 detected[label]=out.stdout
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'pitch-memory.json').write_text(json.dumps(dict(status='PASS old-source cycle/all-group storage equivalence, input races/reset, two faults detected',results=results,detected_faults=detected,inputs=inputs,hardware_tested=False),indent=2),encoding='utf-8')
print('PASS all pitch-bank cases and two fault mutations')
