from common import *
files=[R/'reference/probe_scan_store_mac.v',R/'tb/vendor_alu54d.v',R/'tb/vendor_mac18.v',R/'tb/tb_scan_store.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']};results={}
for width,words in ((54,1),(108,2),(587,6),(587,0)):
    name='mac-scan-%d-%d'%(width,words)
    run([IV,'-g2012','-s','tb_scan_store','-Ptb_scan_store.WIDTH='+str(width),'-Ptb_scan_store.HARD_WORDS='+str(words),'-o',str(E/(name+'.vvp')),*map(str,files)],'compile-'+name)
    results[name]=run([VVP,str(E/(name+'.vvp'))],'run-'+name)
text=files[0].read_text(encoding='utf-8');fault=E/'wrong-mac-scan.v'
assert text.count('.C(next[k*54+:54])')==1
fault.write_text(text.replace('.C(next[k*54+:54])',".C(next[k*54+:54]^54'd1)"),encoding='utf-8')
run([IV,'-g2012','-s','tb_scan_store','-o',str(E/'fault-mac-scan.vvp'),str(fault),*map(str,files[1:])],'compile-mac-scan-fault')
out=subprocess.run([VVP,str(E/'fault-mac-scan.vvp')],cwd=R,capture_output=True,text=True,timeout=60)
(E/'mac-scan-fault.log').write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode!=0 and 'scan history mismatch' in out.stdout
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'mac-scan-model.json').write_text(json.dumps(dict(status='PASS DSP-register scan history versus independent full-width shift; fault detected',results=results,detected_fault=out.stdout,inputs=inputs,hardware_tested=False),indent=2),encoding='utf-8')
