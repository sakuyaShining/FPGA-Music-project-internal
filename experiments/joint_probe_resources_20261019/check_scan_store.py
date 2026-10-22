from common import *
files=[R/'rtl/probe_scan_store.v',R/'tb/vendor_alu54d.v',R/'tb/vendor_mac18.v',R/'tb/tb_scan_store.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']};results={}
for width,words,gap in ((54,1,0),(108,2,0),(587,6,0),(587,9,96),(587,0,96)):
    name='scan-%d-%d-%d'%(width,words,gap)
    run([IV,'-g2012','-s','tb_scan_store','-Ptb_scan_store.WIDTH='+str(width),'-Ptb_scan_store.HARD_WORDS='+str(words),'-Ptb_scan_store.GAP_SIZE='+str(gap),'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
    results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name)
text=files[0].read_text(encoding='utf-8');fault=E/'wrong-scan.v'
assert text.count('.C(active_next[k*54+:54])')==1
fault.write_text(text.replace('.C(active_next[k*54+:54])',".C(active_next[k*54+:54]^54'd1)"),encoding='utf-8')
run([IV,'-g2012','-s','tb_scan_store','-o',str(E/'fault-scan.vvp'),str(fault),*map(str,files[1:])],'compile-scan-fault')
out=subprocess.run([VVP,str(E/'fault-scan.vvp')],cwd=R,capture_output=True,text=True,timeout=60)
(E/'scan-fault.log').write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode!=0 and 'scan history mismatch' in out.stdout
delay_fault=E/'wrong-gap-delay.v'
assert text.count('pointer-(GAP_SIZE-1)')==1
delay_fault.write_text(text.replace('pointer-(GAP_SIZE-1)','pointer-(GAP_SIZE-2)'),encoding='utf-8')
run([IV,'-g2012','-s','tb_scan_store','-Ptb_scan_store.HARD_WORDS=9','-Ptb_scan_store.GAP_SIZE=96','-o',str(E/'fault-gap.vvp'),str(delay_fault),*map(str,files[1:])],'compile-gap-fault')
bad=subprocess.run([VVP,str(E/'fault-gap.vvp')],cwd=R,capture_output=True,text=True,timeout=60)
(E/'gap-fault.log').write_text(bad.stdout+bad.stderr,encoding='utf-8');assert bad.returncode!=0 and 'scan history mismatch' in bad.stdout
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'scan-model.json').write_text(json.dumps(dict(status='PASS DSP-register/RAM-gap scan history versus independent full-width shift; two faults detected',results=results,detected_faults=[out.stdout,bad.stdout],inputs=inputs,hardware_tested=False),indent=2),encoding='utf-8')
