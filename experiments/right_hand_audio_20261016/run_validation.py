"""Run actual control and latest-engine comparison simulations, no hardware."""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent;E=ROOT/'evidence';E.mkdir(exist_ok=True)
IVERILOG='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'
FADERS=ROOT.parent/'right_hand_faders_20261016'
def run(args,name,cwd=ROOT,timeout=120):
 r=subprocess.run(args,cwd=cwd,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 (E/(name+'.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
 if r.returncode:raise RuntimeError((E/(name+'.log')).read_text(encoding='utf-8'))
 if name.startswith('run-'):print(r.stdout.strip(),flush=True)
 return r.stdout
def main():
 shutil.copyfile(ROOT/'fader_gain_q8.hex',ROOT/'engine/fader_gain_q8.hex')
 control=[str(FADERS/'rtl/rh_fader_bank.v'),str(FADERS/'rtl/rh_fader_panel.v')]+[str(ROOT/'rtl'/n) for n in ['rh_timbre_slew.v','rh_fader_gain_map.v','rh_performance_control.v']]
 run([IVERILOG,'-g2012','-Wall','-s','tb_control','-o',str(E/'control.vvp'),*control,'tb_control.v'],'compile-control')
 run([VVP,str(E/'control.vvp')],'run-control')
 engine=[str(ROOT/'engine'/n) for n in ['tdm_engine.v','tdm_engine_rh.v','pitch_mod.v','osc_env.v']]
 run([IVERILOG,'-g2012','-Wall','-s','tb_engine','-o',str(E/'engine.vvp'),*engine,str(ROOT/'tb_engine.v')],'compile-engine')
 run([VVP,str(E/'engine.vvp')],'run-engine',cwd=ROOT/'engine')
 all_engine=[str(p) for p in (ROOT/'engine').glob('*.v')]
 run([IVERILOG,'-g2012','-Wall','-s','tb_music','-o',str(E/'music.vvp'),*all_engine,*control,str(ROOT/'rtl/rh_music_probe.v'),str(ROOT/'tb_music.v')],'compile-music')
 run([VVP,str(E/'music.vvp')],'run-music',cwd=ROOT/'engine')
 files=list((ROOT/'rtl').glob('*.v'))+[ROOT/'engine/tdm_engine_rh.v',ROOT/'engine/tdm_top_rh.v',ROOT/'tb_control.v',ROOT/'tb_engine.v',ROOT/'tb_music.v',ROOT/'run_validation.py',ROOT/'generate_assets.py',ROOT/'audition-config.json',ROOT/'fader_gain_q8.hex']
 record=dict(status='PASS within control and engine simulations',audio_hardware_tested=False,product_engine_modified=False,inputs={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},control_log='evidence/run-control.log',engine_log='evidence/run-engine.log')
 (E/'validation.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
if __name__=='__main__':main()
