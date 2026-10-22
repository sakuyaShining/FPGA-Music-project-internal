from common import *
files=sources()+[R/'tb_config_music.v']
for name in ('fast','slow','hybrid','strike'):assert (R/('config-'+name+'.hex')).exists(),'run check_host.py first'
run([IV,'-g2012','-I',str(R/'src'),'-s','tb_config_music','-o',str(E/'config-music.vvp'),*map(str,files)],'compile-config-music')
trace=E/'config-music.tsv';log=run([VVP,str(E/'config-music.vvp'),'+trace='+trace.as_posix()],'run-config-music',R/'src')
assert 'PASS config_music' in log
inputs=files+list((R/'src').glob('*.hex'))+list(R.glob('*.hex'))+[Path(__file__).resolve(),R/'common.py']
(E/'config-music.json').write_text(json.dumps(dict(status='PASS compiled document to PCM chain in simulation',log=log,trace_sha256=sha(trace),hardware_tested=False,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs}),indent=2),encoding='utf-8')
