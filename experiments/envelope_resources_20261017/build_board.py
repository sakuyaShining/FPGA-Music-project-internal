from common import *
import sys,shutil,time
D=R/(sys.argv[1] if len(sys.argv)>1 else 'build_board');D.mkdir(exist_ok=False)
files=sources()+[R/'board/board_config_top.v']+list((R/'src').glob('*.hex'))+list((R/'src').glob('*.vh'))+list((R/'constraints').glob('*'))
assert len(files)==len({p.name for p in files})
inputs={};entries=[]
for p in files:
 shutil.copyfile(p,D/p.name);inputs[p.name]=dict(source=p.relative_to(R).as_posix(),sha256=sha(p))
 kind={'.v':'file.verilog','.cst':'file.cst','.sdc':'file.sdc'}.get(p.suffix)
 if kind:entries.append('<File path="'+p.name+'" type="'+kind+'" enable="1"/>')
(D/'inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
(D/'board_config.gprj').write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project><Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>'+''.join(entries)+'</FileList></Project>',encoding='utf-8')
(D/'build.tcl').write_text('open_project "'+(D/'board_config.gprj').as_posix()+'"\nset_option -top_module board_config_top\nset_option -use_sspi_as_gpio 1\nrun all\nexit\n',encoding='utf-8')
start=time.time();exe='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
with (D/'console.txt').open('w',encoding='utf-8') as f:
 proc=subprocess.Popen([exe,str(D/'build.tcl')],cwd=D,stdout=f,stderr=subprocess.STDOUT)
 try:rc=proc.wait(timeout=900)
 except subprocess.TimeoutExpired:
    subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True);proc.wait(timeout=30);rc=124
log=(D/'console.txt').read_text(encoding='utf-8',errors='replace')
record=dict(status='build completed; timing needs audit' if rc==0 and 'ERROR (' not in log else 'FAILED build',returncode=rc,seconds=round(time.time()-start,2),inputs=inputs,project_sha256=sha(D/'board_config.gprj'),tcl_sha256=sha(D/'build.tcl'),hardware_programmed=False)
(D/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in record.items() if k!='inputs'}),flush=True)
if rc:print(log[-2000:]);raise SystemExit(rc)
