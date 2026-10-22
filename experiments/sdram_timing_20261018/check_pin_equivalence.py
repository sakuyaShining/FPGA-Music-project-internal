from common import *
original=R/'reference/sdram_word_controller_unregistered.v'
reference=E/'sdram_original.v';reference.write_text(original.read_text().replace('module sdram_word_controller','module sdram_original'))
files=[reference,R/'rtl/sdram_word_controller.v',R/'tb/tb_pin_equivalence.v']
before={p.relative_to(R).as_posix():sha(p) for p in files+[original,Path(__file__).resolve(),R/'common.py']}
run([IV,'-g2012','-s','tb_pin_equivalence','-o',str(E/'pin-equivalence.vvp'),*map(str,files)],'compile-pin-equivalence')
log=run([VVP,str(E/'pin-equivalence.vvp')],'run-pin-equivalence');print(log)
assert all(sha(R/p)==h for p,h in before.items())
(E/'pin-equivalence.json').write_text(json.dumps(dict(status='PASS sampled old-source command/data/handshake equivalence',log=log,inputs=before),indent=2))
