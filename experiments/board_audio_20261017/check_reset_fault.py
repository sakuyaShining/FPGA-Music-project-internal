from common import *
F=R/'reference';F.mkdir(exist_ok=True)
source=R/'rtl/board_audio_top.v';text=source.read_text(encoding='utf-8');assert text.count('.BOARD_BOOT_SCRUB(1)')==1
mutant=F/'board_top_no_scrub.v';mutant.write_text(text.replace('.BOARD_BOOT_SCRUB(1)','.BOARD_BOOT_SCRUB(0)'),encoding='utf-8')
files=[mutant if p==source else p for p in sources()]+[R/'tb_board_audio.v']
run([IV,'-g2012','-I',str(R/'src'),'-s','tb_board_audio','-o',str(E/'no-scrub.vvp'),*map(str,files)],'compile-no-scrub')
out=subprocess.run([VVP,str(E/'no-scrub.vvp')],cwd=R/'src',capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
log=out.stdout+out.stderr;(E/'reset-scrub-fault.log').write_text(log,encoding='utf-8')
assert out.returncode!=0 and 'reset left hidden sounding slots' in log,log
(E/'reset-fault.json').write_text(json.dumps(dict(status='PASS regression reproduced when scrub disabled',expected_failure='reset left hidden sounding slots',returncode=out.returncode,inputs={p.relative_to(R).as_posix():sha(p) for p in files+list((R/'src').glob('*.hex'))+[Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
print('PASS held-note reset regression detected when quiet fence disabled')
