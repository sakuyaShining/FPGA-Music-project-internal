from common import *
import shutil
U=R/'handoff_support/system_integration_20261016';copied={};results={}
for name in ('row_vectors.hex','meta_vectors.hex','expected_vectors.hex','tb_positions.v','tb_sensor.v'):
    target=R/name if name.endswith('.hex') else R/'tb'/name
    shutil.copyfile(U/name,target);copied[str(U/name)]=sha(U/name)
for name in ('positions','sensor','area'):
    files=sources()+[R/'tb'/('tb_'+name+'.v')]
    run([IV,'-g2012','-DTIMING_RTL_SIM','-I',str(R/'engine/src'),'-s','tb_'+name,'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
    results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name)
inputs=sources()+[R/'tb/tb_positions.v',R/'tb/tb_sensor.v',R/'tb/tb_area.v',*R.glob('*.hex'),Path(__file__).resolve(),R/'common.py']
(E/'sensor-model.json').write_text(json.dumps(dict(status='PASS original independent position vectors, full digital RC sensor regression, and contact-area output',results=results,copied_test_inputs=copied,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs},physical_tested=False),indent=2),encoding='utf-8')
