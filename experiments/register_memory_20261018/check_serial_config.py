from common import *
import sys
nominal=len(sys.argv)>1 and sys.argv[1]=='nominal';dual=len(sys.argv)>1 and sys.argv[1]=='dual';label='serial-nominal' if nominal else 'serial-dual' if dual else 'serial-config'
files=sources()+[R/'tb_serial_config.v'];extra=['-Ptb_serial_config.DIV=234','-Ptb_serial_config.SMOKE=1'] if nominal else ['-Ptb_serial_config.DUAL=1'] if dual else []
run([IV,'-g2012','-I',str(R),'-I',str(R/'src'),'-s','tb_serial_config',*extra,'-o',str(E/(label+'.vvp')),*map(str,files)],'compile-'+label)
log=run([VVP,str(E/(label+'.vvp'))],'run-'+label,R/'src')
(E/(label+'.json')).write_text(json.dumps(dict(status='PASS physical UART pins to configuration/PC-note PCM in simulation',log=log,configured_baud=115200 if nominal else 1687500,hardware_tested=False,inputs={p.relative_to(R).as_posix():sha(p) for p in files+list((R/'src').glob('*.hex'))+[R/'transport_fixture.vh',R/'transport-payload.hex',R/'config-fast.hex',Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
