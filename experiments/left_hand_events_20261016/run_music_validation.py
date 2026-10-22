"""Owned frames into the real engine, plus original PCM/I2S compatibility."""
from pathlib import Path
import hashlib,json
from run_validation import ROOT,E,IV,VVP,run
files=list((ROOT/'engine').glob('*.v'))+list((ROOT/'candidate').glob('*.v'))+list((ROOT/'rtl').glob('*.v'))
results={}
for name,top,tb in [('compat','tb_music','tb_compat_music.v'),('left_music','tb_left_music','tb_left_music.v')]:
    run([IV,'-g2012','-I',str(ROOT/'rtl'),'-s',top,'-o',str(E/(name+'.vvp')),*[str(p) for p in files],str(ROOT/tb)],'compile-'+name)
    results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name,cwd=ROOT/'engine')
    assert 'PASS ' in results[name]
inputs=files+list((ROOT/'engine').glob('*.hex'))+list((ROOT/'rtl').glob('*.vh'))+[ROOT/'tb_compat_music.v',ROOT/'tb_left_music.v',ROOT/'prepare_compat_test.py',Path(__file__).resolve()]
(E/'music-validation.json').write_text(json.dumps(dict(status='PASS real digital music and legacy PCM/I2S compatibility',hardware_tested=False,optimized_glide_selected=False,results=results,inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}),indent=2),encoding='utf-8')
