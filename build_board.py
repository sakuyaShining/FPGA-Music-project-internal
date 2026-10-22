"""Build structural joint timing probe only. No programmer invocation."""
from common import *
import sys,shutil,time,re
label=sys.argv[1];mode=sys.argv[2];assert mode in ('nominal','stress')
strategy=int(sys.argv[3]) if len(sys.argv)>3 else 0;assert strategy in (0,1)
assert re.fullmatch(r'build_[a-zA-Z0-9_]+',label)
D=R/label
assert not D.exists(),'Refuse to overwrite an existing build'
D.mkdir()
sdc=R/('constraints/sdram_board.sdc' if mode=='nominal' else 'reference/stress.sdc')
files=sources()+list((R/'engine/src').glob('*.hex'))+list((R/'engine/src').glob('*.vh'))+[R/'constraints/sdram_board.cst',sdc]
inputs={};entries=[]
for p in files:
    assert p.name not in inputs
    shutil.copyfile(p,D/p.name);inputs[p.name]=dict(source=p.relative_to(R).as_posix(),sha256=sha(p))
    kind={'.v':'file.verilog','.cst':'file.cst','.sdc':'file.sdc'}.get(p.suffix)
    if kind:entries.append('<File path="'+p.name+'" type="'+kind+'" enable="1"/>')
(D/'board.gprj').write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project><Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>'+''.join(entries)+'</FileList></Project>')
options='set_option -place_option 1\nset_option -route_option 1\n' if strategy else ''
(D/'build.tcl').write_text('open_project "'+(D/'board.gprj').as_posix()+'"\nset_option -top_module joint_timing_top\nset_option -use_sspi_as_gpio 1\n'+options+'run all\nexit\n')
exe=os.environ.get('FPGA_GOWIN_GW_SH','D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe');start=time.monotonic()
with (D/'console.log').open('w',encoding='utf-8') as f:
    proc=subprocess.Popen([exe,str(D/'build.tcl')],cwd=D,stdout=f,stderr=subprocess.STDOUT)
    try:rc=proc.wait(timeout=900)
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True);proc.wait();rc=124
log=(D/'console.log').read_text(encoding='utf-8',errors='replace')
status='build completed; audit required; NEVER PROGRAM' if rc==0 and not re.search(r'\bERROR\s*\(',log) and 'Bitstream generation completed' in log else 'FAILED build'
data=dict(status=status,returncode=rc,mode=mode,strategy=strategy,seconds=round(time.monotonic()-start,2),inputs=inputs,
    project_sha256=sha(D/'board.gprj'),tcl_sha256=sha(D/'build.tcl'),bench_gate=False,hardware_programmed=False)
(D/'run.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in data.items() if k!='inputs'}));assert status.startswith('build completed'),log[-3000:]
