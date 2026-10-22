from common import *
results={};inputs=sources()
for top in ('tb_board_audio','tb_uart_nominal'):
    files=sources()+[R/(top+'.v')]
    run([IV,'-g2012','-I',str(R/'src'),'-s',top,'-o',str(E/(top+'.vvp')),*map(str,files)],'compile-'+top)
    results[top]=run([VVP,str(E/(top+'.vvp'))],'run-'+top,R/'src');inputs.append(R/(top+'.v'))
inputs+=list((R/'src').glob('*.hex'))+list((R/'src').glob('*.vh'))+[Path(__file__).resolve(),R/'common.py']
(E/'validation.json').write_text(json.dumps(dict(status='PASS pin UART and digital audio in simulation',hardware_tested=False,nominal_baud_tested=115200,accelerated_capture_samples=64,results=results,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs}),indent=2),encoding='utf-8')
