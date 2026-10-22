from common import *
files=[R/'rtl/sdram_word_controller.v',R/'tb/sdram_timing_model.v',R/'tb/tb_sdram.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']}
run([IV,'-g2012','-s','tb_sdram','-o',str(E/'sdram.vvp'),*map(str,files)],'compile-sdram')
log=run([VVP,str(E/'sdram.vvp')],'run-sdram');print(log)
faults={
 'early-column':('TRCD=3','TRCD=2','tRCD'),
 'late-refresh':('REF_PERIOD=384','REF_PERIOD=450','refresh deadline'),
 'half-mask':("address[0]?4'b0011:4'b1100","4'b1100",'data address='),
 'blocked-refresh':('IDLE:if(refresh_due)','IDLE:if(refresh_due && !rsp_valid)','refresh deadline'),
}
detected={}
for label,(old,new,expected) in faults.items():
 text=files[0].read_text();assert text.count(old)==1
 fault=E/(label+'.v');fault.write_text(text.replace(old,new))
 run([IV,'-g2012','-s','tb_sdram','-o',str(E/(label+'.vvp')),str(fault),*map(str,files[1:])],'compile-'+label)
 out=subprocess.run([VVP,str(E/(label+'.vvp'))],cwd=R,capture_output=True,text=True,timeout=240)
 (E/(label+'.log')).write_text(out.stdout+out.stderr)
 assert out.returncode!=0 and expected in out.stdout,(label,out.stdout,out.stderr)
 detected[label]=out.stdout
assert all(sha(R/p)==h for p,h in inputs.items())
(E/'sdram-reference.json').write_text(json.dumps(dict(status='PASS subset command/timing model and data scoreboard; four deliberate faults detected',log=log,faults=detected,inputs=inputs,hardware_tested=False),indent=2))
print('PASS independent command/timing checks and all four fault mutations')
