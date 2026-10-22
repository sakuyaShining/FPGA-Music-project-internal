from common import *
original=R/'reference/fx_delay_original.v';reference=R/'reference/fx_delay_reference.v'
reference.write_text(original.read_text(encoding='utf-8').replace('module fx_delay #(','module fx_delay_reference #('),encoding='utf-8')
files=[R/'src/fx_delay.v',reference,R/'tb_fx_memory.v'];logs={}
for mode in ('initialized','unknown_start'):
 args=['-DSIM_INIT'] if mode=='initialized' else []
 run([IV,'-g2012',*args,'-s','tb_fx_memory','-o',str(E/('fx-'+mode+'.vvp')),*map(str,files)],'compile-fx-'+mode)
 logs[mode]=run([VVP,str(E/('fx-'+mode+'.vvp'))],'run-fx-'+mode,timeout=360)
bad=R/'faults/fx_tag_bad.v';bad.parent.mkdir(exist_ok=True)
text=files[0].read_text(encoding='utf-8');assert text.count("read_tag<=read_enable?st:4'd0;")==1
bad.write_text(text.replace("read_tag<=read_enable?st:4'd0;","read_tag<=read_enable?(st-1'b1):4'd0;"),encoding='utf-8')
run([IV,'-g2012','-DSIM_INIT','-s','tb_fx_memory','-o',str(E/'fx-tag-fault.vvp'),str(bad),str(reference),str(files[2])],'compile-fx-tag-fault')
out=subprocess.run([VVP,str(E/'fx-tag-fault.vvp')],cwd=R,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60);fault=out.stdout+out.stderr
(E/'fault-fx-tag.log').write_text(fault,encoding='utf-8');assert out.returncode!=0 and 'mismatch' in fault
(E/'fx-equivalence.json').write_text(json.dumps(dict(status='PASS every-clock reference and tag-misalignment fault rejection',logs=logs,cycles_per_mode=600000,aw=[11,4],hardware_tested=False,inputs={p.relative_to(R).as_posix():sha(p) for p in files+[original,bad,R/'check_fx.py',R/'common.py']}),indent=2),encoding='utf-8')
print('PASS deliberately delayed read-tag rejected')
