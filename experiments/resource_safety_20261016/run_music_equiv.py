from common import *
import filecmp,sys
target=sys.argv[1] if len(sys.argv)>1 else 'all'
assert target in ('both','all')
results={};inputs=[];traces={}
for name,top,tb in [('compat','tb_music','tb_compat_music.v'),('layers','tb_layers','tb_layers.v'),('sensor','tb_sensor_layers','tb_sensor_layers.v')]:
    logs=[]
    for variant in ('reference',target):
        tag=name+'-'+variant;files=sources(variant)+[R/tb]
        run([IV,'-g2012','-I',str(R/'rtl'),'-s',top,'-o',str(E/(tag+'.vvp')),*map(str,files)],'compile-'+tag)
        log=run([VVP,str(E/(tag+'.vvp')),'+trace='+(E/(tag+'.tsv')).as_posix()],'run-'+tag,R/'engine')
        assert 'PASS ' in log;logs.append(log);inputs+=files
        traces[tag]=dict(sha256=sha(E/(tag+'.tsv')),bytes=(E/(tag+'.tsv')).stat().st_size)
    assert logs[0]==logs[1],('test outcome mismatch',name)
    assert filecmp.cmp(E/(name+'-reference.tsv'),E/(name+'-'+target+'.tsv'),shallow=False),('full cycle trace mismatch',name)
    results[name]=logs[1]
    print('PASS full byte comparison '+name,flush=True)
record('music-equivalence-'+target+'.json',dict(status='PASS full cycle traces identical',variant=target,results=results,traces=traces,hardware_tested=False),inputs+list(R.glob('*.hex'))+list((R/'engine').glob('*.hex'))+list((R/'rtl').glob('*.vh'))+[Path(__file__).resolve(),R/'common.py'])
