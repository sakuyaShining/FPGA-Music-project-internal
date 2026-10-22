"""Music PCM/I2S oracle with compatible old path and concurrent new sensor path."""
from pathlib import Path
import hashlib,json
from run_validation import ROOT,E,IV,VVP,run
files=list((ROOT/'engine').glob('*.v'))+list((ROOT/'rtl').glob('*.v'))
logs={}
for name,top,tb in [('compat','tb_music','tb_compat_music.v'),('joint','tb_joint','tb_joint.v')]:
    run([IV,'-g2012','-Wall','-I',str(ROOT/'rtl'),'-s',top,'-o',str(E/(name+'.vvp')),*[str(f) for f in files],str(ROOT/tb)],'compile-'+name)
    logs[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name,cwd=ROOT/'engine',timeout=180)
    assert 'PASS music' in logs[name]
    if name=='joint':assert 'PASS joint' in logs[name]
inputs=files+list((ROOT/'engine').glob('*.hex'))+list((ROOT/'rtl').glob('*.vh'))+[ROOT/'tb_joint.v',ROOT/'tb_compat_music.v',ROOT/'generate_joint_test.py',Path(__file__).resolve()]
(E/'joint-validation.json').write_text(json.dumps(dict(status='PASS digital concurrent activity and compatibility only',sensor_to_note_bridge=False,physical_display_tested=False,display_frame_transfer_tested=False,results=logs,inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}),indent=2),encoding='utf-8')
