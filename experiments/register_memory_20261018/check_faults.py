from common import *
F=R/'faults';F.mkdir(exist_ok=True)
cases=[('global-envelope','tdm_engine_rh.v','wire custom=eff_env[35];',"wire custom=1'b0;",'independent attack'),('replace-release','tdm_engine_rh.v','wire release_only = consume & gc1 & ~pg1;',"wire release_only = 1'b0;",'independent release or hanging gate'),('partial-commit','instrument_table.v','if(&written[slot])begin',"if(1'b1)begin",'incomplete/reserved configuration published')]
results={};inputs=sources()+[R/'tb_config_music.v']
for name,filename,old,new,expected in cases:
    p=R/'src'/filename;text=p.read_text(encoding='utf-8');assert text.count(old)==1
    mutant=F/(name+'.v');mutant.write_text(text.replace(old,new),encoding='utf-8');files=[mutant if x==p else x for x in sources()]+[R/'tb_config_music.v']
    run([IV,'-g2012','-I',str(R/'src'),'-s','tb_config_music','-o',str(E/(name+'.vvp')),*map(str,files)],'compile-fault-'+name)
    trace=E/(name+'-fault.tsv');out=subprocess.run([VVP,str(E/(name+'.vvp')),'+trace='+trace.as_posix()],cwd=R/'src',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180);log=out.stdout+out.stderr;(E/('fault-'+name+'.log')).write_text(log,encoding='utf-8')
    assert out.returncode!=0 and expected in log,(name,log)
    results[name]=dict(expected_failure=expected,returncode=out.returncode,mutant_sha256=sha(mutant),log_sha256=sha(E/('fault-'+name+'.log')));inputs.append(mutant);print('PASS regression caught:',name,flush=True)
(E/'fault-validation.json').write_text(json.dumps(dict(status='PASS three deliberate regressions rejected',results=results,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs+list(R.glob('*.hex'))+list((R/'src').glob('*.hex'))+[Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
