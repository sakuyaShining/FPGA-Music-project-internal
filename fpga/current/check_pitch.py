from common import *
import shutil
U=R/'handoff_support/pitch_memory_20261018'
tb=R/'tb/tb_pitch_memory.v';shutil.copyfile(U/'tb/tb_pitch_memory.v',tb)
old=R/'reference/pitch_mod.v';ref=E/'pitch_mod_reference.v'
ref.write_text(old.read_text(encoding='utf-8').replace('module pitch_mod #(','module pitch_mod_reference #(',1),encoding='utf-8')
files=[R/'engine/src/pitch_mod.v',R/'engine/src/pitch_native_store.v',R/'tb/vendor_ram16sdp4.v',ref,tb]
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[old,Path(__file__).resolve(),R/'common.py']};results={}
for ng,qw,seed in ((2,18,91),(8,18,113),(32,18,17),(32,20,99)):
    name='pitch-%d-%d'%(ng,qw)
    run([IV,'-g2012','-s','tb_pitch_memory','-Ptb_pitch_memory.NG='+str(ng),'-Ptb_pitch_memory.QW='+str(qw),'-Ptb_pitch_memory.SEED='+str(seed),'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
    results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name)
text=files[0].read_text(encoding='utf-8');fault=E/'swapped-native-read.v'
before='.qa(materialized_sweep),.qb(materialized_read)';assert text.count(before)==1
fault.write_text(text.replace(before,'.qa(materialized_read),.qb(materialized_sweep)'),encoding='utf-8')
fs=[fault,*files[1:]]
run([IV,'-g2012','-s','tb_pitch_memory','-o',str(E/'fault-pitch.vvp'),*map(str,fs)],'compile-fault-pitch')
out=subprocess.run([VVP,str(E/'fault-pitch.vvp')],cwd=R,capture_output=True,text=True,timeout=120)
(E/'fault-pitch.log').write_text(out.stdout+out.stderr,encoding='utf-8')
assert out.returncode!=0 and any(reason in out.stdout for reason in ('pitch output mismatch','logical storage mismatch'))
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'pitch-model.json').write_text(json.dumps(dict(status='PASS sampled pitch output/epoch equivalence to84, with debug shadow state; swapped native read ports detected',results=results,detected_fault=out.stdout,inputs=inputs,hardware_tested=False),indent=2),encoding='utf-8')
