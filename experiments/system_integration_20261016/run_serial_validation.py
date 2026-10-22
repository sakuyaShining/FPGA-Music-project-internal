"""Verify all logical group states against the original parallel glide."""
from pathlib import Path
import hashlib,json
from run_validation import ROOT,E,IV,VVP,run
inputs=[ROOT/'optimization/pitch_mod.v',ROOT/'optimization/pitch_mod_reference.v',ROOT/'tb_serial_glide.v',ROOT/'prepare_serial_glide.py',Path(__file__).resolve()]
run([IV,'-g2012','-Wall','-s','tb_serial_glide','-o',str(E/'serial-glide.vvp'),*[str(p) for p in inputs[:3]]],'compile-serial-glide')
text=run([VVP,str(E/'serial-glide.vvp')],'run-serial-glide')
assert 'PASS serial_glide' in text
(E/'serial-glide-validation.json').write_text(json.dumps(dict(status='PASS logical state and pitch output equivalence within cadence contract',inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},log=text),indent=2),encoding='utf-8')
