from common import *
original=R/'reference/osc_env_original.v';ref=R/'reference/osc_env_reference.v'
ref.write_text(original.read_text(encoding='utf-8').replace('module osc_env #(','module osc_env_reference #('),encoding='utf-8')
files=[R/'src/osc_env.v',ref,R/'tb_env_shared.v']
run([IV,'-g2012','-s','tb_env_shared','-o',str(E/'env-shared.vvp'),*map(str,files)],'compile-env-shared')
log=run([VVP,str(E/'env-shared.vvp')],'run-env-shared')
# Prove the comparison can catch incorrect DECAY/RELEASE parameter selection.
bad=R/'faults/osc_env_shared_bad.v';bad.parent.mkdir(exist_ok=True)
text=files[0].read_text(encoding='utf-8');assert text.count('release_phase = stg_i == ST_REL;')==1
bad.write_text(text.replace('release_phase = stg_i == ST_REL;','release_phase = stg_i == ST_DEC;'),encoding='utf-8')
run([IV,'-g2012','-s','tb_env_shared','-o',str(E/'env-shared-fault.vvp'),str(bad),str(ref),str(files[2])],'compile-env-shared-fault')
out=subprocess.run([VVP,str(E/'env-shared-fault.vvp')],cwd=R,capture_output=True,text=True,encoding='utf-8');fault=out.stdout+out.stderr
(E/'fault-env-shared.log').write_text(fault,encoding='utf-8');assert out.returncode!=0 and 'shared envelope mismatch' in fault
(E/'shared-envelope.json').write_text(json.dumps(dict(status='PASS reference equivalence and deliberate fault rejection',log=log,product_width=16,extra_widths=[8,24],hardware_tested=False,inputs={p.relative_to(R).as_posix():sha(p) for p in files+[original,bad,R/'check_shared.py',R/'common.py']}),indent=2),encoding='utf-8')
print('PASS deliberate coefficient-selection fault rejected')
