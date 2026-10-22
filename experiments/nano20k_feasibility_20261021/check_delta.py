from common import *
old=R/'reference/rc_delta_store.v';ref=E/'rc_delta_reference.v'
ref.write_text(old.read_text(encoding='utf-8').replace('module rc_delta_store #(','module rc_delta_reference #(',1),encoding='utf-8')
files=[R/'engine/src/rc_delta_store.v',ref,R/'tb/tb_delta.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[old,Path(__file__).resolve(),R/'common.py']};results={}
for lanes,cw in ((2,8),(6,12),(8,12)):
    name='delta-%d-%d'%(lanes,cw)
    run([IV,'-g2012','-s','tb_delta','-Ptb_delta.LANES='+str(lanes),'-Ptb_delta.CW='+str(cw),'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
    results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name)
text=files[0].read_text(encoding='utf-8');fault=E/'wrong-old-data.v'
assert text.count('collision_q?collision_old:delta_q')==1
fault.write_text(text.replace('collision_q?collision_old:delta_q',"collision_q?(collision_old^{{(CW-1){1'b0}},1'b1}):delta_q"),encoding='utf-8')
run([IV,'-g2012','-s','tb_delta','-o',str(E/'fault-delta.vvp'),str(fault),str(ref),str(files[2])],'compile-fault-delta')
out=subprocess.run([VVP,str(E/'fault-delta.vvp')],cwd=R,capture_output=True,text=True,timeout=60)
(E/'fault-delta.log').write_text(out.stdout+out.stderr,encoding='utf-8')
assert out.returncode!=0 and 'delta old-data mismatch' in out.stdout
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'delta-model.json').write_text(json.dumps(dict(status='PASS old-source rc_delta visible-output equivalence; collision corruption detected',results=results,fault=out.stdout,inputs=inputs,hardware_tested=False),indent=2),encoding='utf-8')
