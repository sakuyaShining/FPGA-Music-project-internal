from common import *
import sys
nominal=len(sys.argv)>1 and sys.argv[1]=='nominal';label='board-nominal' if nominal else 'board-config'
files=sources()+[R/'board/board_config_top.v',R/'tb_board_config.v']
extra=['-Ptb_board_config.DIV=234','-Ptb_board_config.SMOKE=1'] if nominal else []
run([IV,'-g2012','-I',str(R),'-I',str(R/'src'),'-s','tb_board_config',*extra,'-o',str(E/(label+'.vvp')),*map(str,files)],'compile-'+label)
log=run([VVP,str(E/(label+'.vvp'))],'run-'+label,R/'src',timeout=360)
(E/(label+'.json')).write_text(json.dumps(dict(status='PASS board wrapper UART/PCM/reset in simulation',log=log,hardware_tested=False,nominal_baud=115200 if nominal else 1687500,inputs={p.relative_to(R).as_posix():sha(p) for p in files+list((R/'src').glob('*.hex'))+[R/'transport_fixture.vh',R/'transport-payload.hex',R/'config-fast.hex',Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
