from common import *
inputs=[R/'selected/left_contact_bridge.v',R/'reference/left_contact_bridge.v'];results={}
for top,tb in [('tb_bridge','tb_bridge_equiv.v'),('tb_bridge_random','tb_bridge_random.v')]:
    files=inputs[:2]+[R/tb]
    run([IV,'-g2012','-s',top,'-o',str(E/(top+'.vvp')),*map(str,files)],'compile-'+top)
    results[top]=run([VVP,str(E/(top+'.vvp'))],'run-'+top);inputs.append(R/tb)
record('bridge-equivalence.json',dict(status='PASS functional and cycle equivalence',results=results),inputs+[Path(__file__).resolve(),R/'common.py'])
