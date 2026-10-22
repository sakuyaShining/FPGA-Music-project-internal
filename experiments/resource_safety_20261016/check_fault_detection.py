"""Require equivalence tests to reject deliberate regressions in COPY fixtures."""
from common import *
F=R/'fault_injection';F.mkdir(exist_ok=True)
cases=[
    ('anchor_overwrite','selected/finger_pitch.v','contact_anchor[finger]<=(!MULTI_BIND||!(|mine))?position:moving_anchor;','contact_anchor[finger]<=position;','tb_anchor_equiv',['reference/finger_pitch.v','tb_anchor_equiv.v'],'anchor mismatch'),
    ('identity_wrong_row','selected/note_map_owned.v','(st==ST_ALLOC)?instance_next[$clog2(NG)-1:0]:owner_index','(st==ST_ALLOC)?owner_index:owner_index','tb_identity_equiv',['reference/note_map_owned.v','engine/vel_shape.v','rtl/instrument_table.v','tb_identity_equiv.v'],'prefetch missed row'),
    ('bridge_no_forward','selected/left_contact_bridge.v','forward_read<=metadata_we&&metadata_addr==index;','forward_read<=0;','tb_bridge_random',['reference/left_contact_bridge.v','tb_bridge_random.v'],'cached row not coherent')
]
results={};inputs=[]
for name,source,old,new,top,others,expected in cases:
    s=(R/source).read_text(encoding='utf-8');assert s.count(old)==1
    mutant=F/(name+'.v');mutant.write_text(s.replace(old,new),encoding='utf-8')
    files=[mutant]+[R/n for n in others]
    run([IV,'-g2012','-s',top,'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-fault-'+name)
    out=subprocess.run([VVP,str(E/(name+'.vvp'))],cwd=R/'engine',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
    log=out.stdout+out.stderr;(E/('fault-'+name+'.log')).write_text(log,encoding='utf-8')
    assert out.returncode!=0 and expected in log,(name,'undetected or wrong failure',log)
    results[name]=dict(status='PASS deliberate regression rejected',failure=expected,returncode=out.returncode,log=log)
    inputs+=files+[R/source];print('PASS fault detected: '+name,flush=True)
record('fault-detection.json',dict(status='PASS all 3 deliberate regressions detected',results=results),inputs+list((R/'engine').glob('*.hex'))+[Path(__file__).resolve(),R/'common.py'])
