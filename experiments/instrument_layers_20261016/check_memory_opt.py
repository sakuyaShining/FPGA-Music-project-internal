from run_validation import *
results={}
files=sources()
# Same testbench and entire music chain; only payload reset implementation differs.
ref=[R/'reference/layer_dispatch.v' if p==R/'rtl/layer_dispatch.v' else p for p in files]
for name,top,tb in [('layers','tb_layers','tb_layers.v'),('sensor_layers','tb_sensor_layers','tb_sensor_layers.v')]:
    logs=[]
    for variant,src in [('selected',files),('reset_reference',ref)]:
        tag=name+'-'+variant
        run([IV,'-g2012','-I',str(R/'rtl'),'-s',top,'-o',str(E/(tag+'.vvp')),*map(str,src),str(R/tb)],'compile-'+tag)
        log=run([VVP,str(E/(tag+'.vvp'))],'run-'+tag,R/'engine')
        logs.append(log)
    assert logs[0]==logs[1],name
    results[name]=logs[0]
inputs=files+ref+list(R.glob('*.hex'))+list((R/'engine').glob('*.hex'))+list((R/'rtl').glob('*.vh'))+[R/'tb_layers.v',R/'tb_sensor_layers.v',Path(__file__).resolve()]
(E/'memory-opt.json').write_text(json.dumps(dict(status='PASS real music scenarios equivalent',results=results,inputs={p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}),indent=2),encoding='utf-8')
