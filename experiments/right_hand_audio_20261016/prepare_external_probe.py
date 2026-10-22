"""Diagnostic only: measure replacing the obsolete pad frontend, not omit it
from a claimed final product. The real new left-hand frontend remains absent.
The preserved candidate and its compatibility path are never edited.
"""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
src=ROOT/'synthesis/music_visualizer';dst=ROOT/'synthesis/external_input_visualizer';dst.mkdir(parents=True,exist_ok=True)
for p in src.iterdir():
 if p.is_file() and p.suffix in ('.v','.vh','.hex','.gprj'):shutil.copyfile(p,dst/p.name)
p=dst/'tdm_top_rh.v';original_bytes=p.read_bytes();original=p.read_text(encoding='utf-8')
start=original.index('    pad_scan #(.NCH(16)) u_pad (')
end=original.index('\n    );',start)+len('\n    );')
overlay='''    // RESOURCE DIAGNOSTIC: new physical left frontend is NOT included here.
    // Only the already-present digital note/finger interfaces remain enabled.
    assign pad = 16'bz;
    assign pad_state_raw = 16'd0;
    assign pd_ev_note = 7'd0;
    assign pd_ev_on = 1'b0;
    assign pd_ev_valid = 1'b0;
    assign pad_raw_sel = 12'd0;
    assign pad_base_sel = 12'd0;'''
p.write_text(original[:start]+overlay+original[end:],encoding='utf-8')
(dst/'synth.tcl').write_text('open_project "'+(dst/'probe.gprj').as_posix()+'"\nset_option -top_module rh_music_visualizer_probe\nrun syn\nexit\n',encoding='utf-8')
(dst/'overlay.json').write_text(json.dumps(dict(scope='Diagnostic only; entire new physical left frontend excluded; no shipping approval',modified='tdm_top_rh.v',before_sha256=hashlib.sha256(original_bytes).hexdigest(),after_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),removed=original[start:end],inserted=overlay,preserved_candidate_unchanged=hashlib.sha256((ROOT/'engine/tdm_top_rh.v').read_bytes()).hexdigest()==hashlib.sha256(original_bytes).hexdigest()),ensure_ascii=False,indent=2),encoding='utf-8')
print(dst)
