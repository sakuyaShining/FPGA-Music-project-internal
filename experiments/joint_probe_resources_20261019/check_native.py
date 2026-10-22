from common import *
files=[R/'engine/src/pitch_native_store.v',R/'tb/vendor_ram16sdp4.v',R/'tb/tb_native.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']};results={}
for ng,qw in ((2,8),(32,18),(32,20),(128,20)):
    name='native-%d-%d'%(ng,qw)
    run([IV,'-g2012','-s','tb_native','-Ptb_native.NG='+str(ng),'-Ptb_native.QW='+str(qw),'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
    results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name)
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'native-model.json').write_text(json.dumps(dict(status='PASS replicated native store versus independent word array; complete asynchronous address sweeps',results=results,inputs=inputs,hardware_tested=False),indent=2),encoding='utf-8')
