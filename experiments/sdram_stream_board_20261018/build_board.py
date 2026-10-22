from common import *
import sys,shutil,time
D=R/(sys.argv[1] if len(sys.argv)>1 else 'build_candidate');D.mkdir(exist_ok=False)
mode=sys.argv[2] if len(sys.argv)>2 else 'nominal'
assert mode in ('nominal','stress','missing_io')
sdc=R/'constraints/sdram_board.sdc' if mode=='nominal' else R/('reference/'+mode+'.sdc')
files=list((R/'rtl').glob('*.v'))+[R/'constraints/sdram_board.cst',sdc];inputs={};entries=[]
for p in files:
 shutil.copyfile(p,D/p.name);inputs[p.name]=dict(source=p.relative_to(R).as_posix(),sha256=sha(p))
 kind={'.v':'file.verilog','.cst':'file.cst','.sdc':'file.sdc'}[p.suffix]
 entries.append('<File path="'+p.name+'" type="'+kind+'" enable="1"/>')
(D/'board.gprj').write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project><Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>'+''.join(entries)+'</FileList></Project>')
(D/'build.tcl').write_text('open_project "'+(D/'board.gprj').as_posix()+'"\nset_option -top_module sdram_board_top\nset_option -use_sspi_as_gpio 1\nrun all\nexit\n')
start=time.monotonic();exe='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
with (D/'console.log').open('w',encoding='utf-8') as f:
 proc=subprocess.Popen([exe,str(D/'build.tcl')],cwd=D,stdout=f,stderr=subprocess.STDOUT)
 try:rc=proc.wait(timeout=600)
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True);proc.wait();rc=124
log=(D/'console.log').read_text(encoding='utf-8',errors='replace')
status='build completed; timing and pin audit required' if rc==0 and 'ERROR (' not in log else 'FAILED build'
d=dict(status=status,returncode=rc,seconds=round(time.monotonic()-start,2),inputs=inputs,project_sha256=sha(D/'board.gprj'),tcl_sha256=sha(D/'build.tcl'),hardware_programmed=False)
(D/'run.json').write_text(json.dumps(d,indent=2));print(json.dumps({k:v for k,v in d.items() if k!='inputs'}))
assert status.startswith('build completed'),log[-2500:]
