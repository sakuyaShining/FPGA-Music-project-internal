from common import *
import re
old=R/'reference/tdm_top_owned_original.v'
ref=E/'tdm_top_reference.v';ref.write_text(old.read_text(encoding='utf-8').replace('module tdm_top_owned','module tdm_top_reference'),encoding='utf-8')
unit=[R/'src/reg_bank.v',R/'src/reg_bank_compact.v',R/'tb_register_memory.v']
integration=sources()+[ref,R/'tb_readback_equivalence.v']
logs={}
for name,top,files in [('register-memory','tb_register_memory',unit),('readback-equivalence','tb_readback_equivalence',integration)]:
 run([IV,'-g2012','-I',str(R),'-I',str(R/'src'),'-s',top,'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
 logs[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name,R/'src',timeout=240)
# A deliberately missing previous-edge forwarding path must fail.
fault=E/'tdm_top_no_forward.v'
text=(R/'src/tdm_top_owned.v').read_text(encoding='utf-8');needle='reg_read_forward ? reg_read_forward_data : reg_read_data'
assert text.count(needle)==1;fault.write_text(text.replace(needle,'reg_read_data'),encoding='utf-8')
files=[fault if p.name=='tdm_top_owned.v' else p for p in integration]
run([IV,'-g2012','-I',str(R),'-I',str(R/'src'),'-s','tb_readback_equivalence','-o',str(E/'no-forward.vvp'),*map(str,files)],'compile-no-forward')
out=subprocess.run([VVP,str(E/'no-forward.vvp')],cwd=R/'src',capture_output=True,text=True,timeout=240)
(E/'fault-no-forward.log').write_text(out.stdout+out.stderr,encoding='utf-8')
assert out.returncode!=0 and 'readback FSM mismatch' in out.stdout,'fault was not detected'
# Keep the source list explicit: changes in live consumers need a new review.
clean=re.sub(r'//[^\n]*','',(R/'src/tdm_top_owned.v').read_text(encoding='utf-8'))
assert 'R[{' not in clean,'dynamic flat read reintroduced'
addresses=sorted({int(a,16) for a in re.findall(r"R\[8'h([0-9A-Fa-f]+)\*8\s*\+:",clean)})
mapping=json.loads((E/'register-map.json').read_text(encoding='utf-8'))
assert addresses==mapping['live_addresses']
inputs=unit+integration+[Path(__file__).resolve(),R/'common.py',old,R/'evidence/register-map.json']
(E/'register-memory.json').write_text(json.dumps(dict(status='PASS old-reference bank and UART readback equivalence; missing-forward fault detected',logs=logs,fault=out.stdout,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs}),indent=2),encoding='utf-8')
print('PASS missing-forward fault detected and live-mask consumers audited')
