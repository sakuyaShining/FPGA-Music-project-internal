"""Verify the external-input diagnostic under digital note/finger stimuli only."""
import hashlib,json
from pathlib import Path
from run_validation import run,IVERILOG,VVP,ROOT,E
D=ROOT/'synthesis/external_input_visualizer'
inputs=list(D.glob('*.v'))+[ROOT/'tb_music.v']
run([IVERILOG,'-g2012','-Wall','-I',str(D),'-s','tb_music','-o',str(E/'external-input-music.vvp'),*[str(p) for p in inputs]],'compile-external-input-music')
text=run([VVP,str(E/'external-input-music.vvp')],'run-external-input-music',cwd=D)
assert 'PASS music' in text
(E/'external-input-validation.json').write_text(json.dumps(dict(status='PASS only for digital music stimuli with no physical pad frontend',new_physical_left_frontend_included=False,pinout_or_board_verified=False,overlay_sha256=hashlib.sha256((D/'overlay.json').read_bytes()).hexdigest(),inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},log=text),indent=2),encoding='utf-8')
