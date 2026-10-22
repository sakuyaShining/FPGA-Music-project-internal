"""Create an isolated copy of experiment 86. Never edits upstream or hardware."""
from pathlib import Path
import hashlib, json, shutil

R = Path(__file__).resolve().parent
U = Path('C:/Users/Sakuya/FPGA-Music-project/experiments/joint_probe_resources_20261019')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert not (R/'engine').exists(), 'Refuse to overwrite an existing experiment'
for name in ('engine', 'rtl', 'constraints', 'reference', 'tb', 'project'):
    shutil.copytree(U/name, R/name)
for p in U.iterdir():
    if p.is_file() and p.suffix in ('.py', '.hex', '.v'):
        if p.name != 'prepare.py':
            shutil.copy2(p, R/p.name)
frozen = {str(p.relative_to(U)).replace('\\','/'): sha(p)
          for name in ('engine','rtl','constraints','reference','tb','project')
          for p in (U/name).rglob('*') if p.is_file()}
(R/'source-identity.json').write_text(json.dumps({'upstream':str(U), 'files':frozen},indent=2),encoding='utf-8')
src = R/'engine/src/mv_renderer.v'
old = src.read_text(encoding='utf-8')
(R/'reference/mv_renderer_before.v').write_text(old.replace('module mv_renderer #','module mv_renderer_before #'),encoding='utf-8')
start = old.index('            if(y>=4&&y<18&&x>=12&&x<82)')
end = old.index('            if(char_id>=0)',start)
lines = ['            // Fixed glyph cells: exact original pixels, no runtime division.']
for y, x, ids in [(4,12,range(5)), (28,16,range(5,7)), (94,16,range(7,9)), (166,16,range(9,11))]:
    for n, char in enumerate(ids):
        left = x+n*14
        lines.append(f'            if(y>={y}&&y<{y+14}&&x>={left}&&x<{left+14}) begin char_id={char};column=x-{left};row=y-{y}; end')
for n in range(4):
    left = 214+n*20
    lines.append(f"            if(y>=4&&y<18&&x>={left}&&x<{left+14}) begin char_id={11+n};column=x-{left};row=y-4; if(frame_layers[{n}]) color=16'h2453; else color=16'h10a4; end")
src.write_text(old[:start]+'\n'.join(lines)+'\n'+old[end:],encoding='utf-8')
# Only our copies are adapted to their isolated root and immutable goldens.
p=R/'build_board.py'
p.write_text(p.read_text().replace('joint-probe-resources-20261019','nano20k-feasibility-20261021'),encoding='utf-8')
p=R/'check_engine_compat.py'
p.write_text(p.read_text().replace("U=P/'experiments/resource_safety_20261016'", "U=Path('C:/Users/Sakuya/FPGA-Music-project/experiments/resource_safety_20261016')"),encoding='utf-8')
print('Prepared isolated renderer candidate; upstream identities recorded')
