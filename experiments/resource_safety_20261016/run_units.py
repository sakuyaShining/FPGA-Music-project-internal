from common import *
results={};inputs=[]
for name in ('anchor','identity'):
    files=([R/'selected/finger_pitch.v',R/'reference/finger_pitch.v'] if name=='anchor' else [R/'selected/note_map_owned.v',R/'reference/note_map_owned.v',R/'engine/vel_shape.v',R/'rtl/instrument_table.v'])+[R/('tb_'+name+'_equiv.v')]
    run([IV,'-g2012','-s','tb_'+name+'_equiv','-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
    results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name,R/'engine');inputs+=files
record('units.json',dict(status='PASS cycle equivalence in tested scope',results=results),inputs+list((R/'engine').glob('*.hex'))+[Path(__file__).resolve(),R/'common.py'])
