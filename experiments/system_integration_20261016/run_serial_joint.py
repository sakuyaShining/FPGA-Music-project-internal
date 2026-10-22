"""Optional optimized candidate against an independently named original core."""
from pathlib import Path
import hashlib,json
from run_validation import ROOT,E,IV,VVP,run
D=ROOT/'optimization'
ref_engine=(ROOT/'engine/tdm_engine.v').read_text(encoding='utf-8').replace('module tdm_engine #(','module tdm_engine_reference #(').replace('    pitch_mod #(','    pitch_mod_reference #(')
ref_top=(ROOT/'engine/tdm_top.v').read_text(encoding='utf-8').replace('module tdm_top #(','module tdm_top_reference #(').replace('    tdm_engine #(','    tdm_engine_reference #(')
(D/'tdm_engine_reference.v').write_text(ref_engine,encoding='utf-8')
(D/'tdm_top_reference.v').write_text(ref_top,encoding='utf-8')
tb=(ROOT/'tb_joint.v').read_text(encoding='utf-8').replace('    tdm_top #(','    tdm_top_reference #(')
tb=tb.replace('if(control_error)$fatal', 'if(dut.music.core.u_tdm.u_pmod.update_overrun)$fatal(1,"serial glide overrun");\n            if(control_error)$fatal')
(D/'tb_serial_joint.v').write_text(tb,encoding='utf-8')
files=[p for p in (ROOT/'engine').glob('*.v') if p.name!='pitch_mod.v']+list((ROOT/'rtl').glob('*.v'))+[D/n for n in ['pitch_mod.v','pitch_mod_reference.v','tdm_engine_reference.v','tdm_top_reference.v','tb_serial_joint.v']]
run([IV,'-g2012','-Wall','-I',str(ROOT/'rtl'),'-s','tb_joint','-o',str(E/'serial-joint.vvp'),*[str(p) for p in files]],'compile-serial-joint')
result=run([VVP,str(E/'serial-joint.vvp')],'run-serial-joint',cwd=ROOT/'engine',timeout=180)
assert 'PASS joint' in result and 'PASS music' in result
inputs=files+list((ROOT/'engine').glob('*.hex'))+list((ROOT/'rtl').glob('*.vh'))+[Path(__file__).resolve()]
(E/'serial-joint-validation.json').write_text(json.dumps(dict(status='PASS optimized concurrent prototype against original separately named engine',hardware_tested=False,sensor_to_note_bridge=False,inputs={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},log=result),indent=2),encoding='utf-8')
