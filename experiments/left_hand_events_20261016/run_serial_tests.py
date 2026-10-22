"""Revalidate allocator, real voices and raw sensor chain with serial lookup."""
from pathlib import Path
import hashlib,json
from run_validation import ROOT,E,IV,VVP,run
files=[p for p in (ROOT/'engine').glob('*.v') if p.name!='pitch_mod.v']+[p for p in (ROOT/'candidate').glob('*.v') if p.name!='note_map_owned.v']+list((ROOT/'rtl').glob('*.v'))+[ROOT/'optimization/pitch_mod.v',ROOT/'optimization/note_map_owned.v',ROOT/'optimization/note_map_owned_parallel.v']
logs={}
for name in ['allocator','owner_equiv','left_music','sensor_music']:
    run([IV,'-g2012','-I',str(ROOT/'rtl'),'-s','tb_'+name,'-o',str(E/('serial-'+name+'.vvp')),*[str(p) for p in files],str(ROOT/('tb_'+name+'.v'))],'compile-serial-'+name)
    logs[name]=run([VVP,str(E/('serial-'+name+'.vvp'))],'run-serial-'+name,cwd=ROOT/'engine')
    assert 'PASS '+name in logs[name]
inputs=files+list((ROOT/'engine').glob('*.hex'))+list((ROOT/'rtl').glob('*.vh'))+[ROOT/('tb_'+name+'.v') for name in logs]+[ROOT/'prepare_serial_owner.py',Path(__file__).resolve()]
(E/'serial-validation.json').write_text(json.dumps(dict(status='PASS serial allocation equivalence and real digital music',hardware_tested=False,optimized_glide_selected=True,logs=logs,inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}),indent=2),encoding='utf-8')
