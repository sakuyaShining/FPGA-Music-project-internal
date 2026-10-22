from pathlib import Path
import shutil,subprocess,json,hashlib,re,xml.etree.ElementTree as ET,time,sys
from run_validation import R,sources
D=R/(sys.argv[1] if len(sys.argv)>1 else 'synthesis');D.mkdir(exist_ok=True)
files=sources()+list((R/'engine').glob('*.hex'))+list((R/'rtl').glob('*.vh'))
assert len({p.name for p in files})==len(files)
inputs={}
for p in files:
    shutil.copyfile(p,D/p.name);inputs[p.name]=dict(source=p.relative_to(R).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(D/'inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
(D/'probe.gprj').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE gowin-fpga-project>
<Project><Template>FPGA</Template><Version>5</Version>
<Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>
'''+''.join('<File path="'+p.name+'" type="file.verilog" enable="1"/>\n' for p in files if p.suffix=='.v')+'</FileList></Project>',encoding='utf-8')
(D/'synth.tcl').write_text('open_project "'+(D/'probe.gprj').as_posix()+'"\nset_option -top_module instrument_layer_probe\nrun syn\nexit\n',encoding='utf-8')
exe='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
start=time.time()
with (D/'console.txt').open('w',encoding='utf-8') as f:
    proc=subprocess.Popen([exe,str(D/'synth.tcl')],cwd=D,stdout=f,stderr=subprocess.STDOUT)
    rc=proc.wait(timeout=240)
log=(D/'console.txt').read_text(encoding='utf-8',errors='replace')
reports=list((D/'impl/gwsynthesis').glob('*_syn.rpt.html'))
metrics={}
if reports:
    s=reports[0].read_text(encoding='utf-8',errors='replace')
    for key in ('Logic','BSRAM','DSP'):
        m=re.search(r'>'+key+r'</td>\s*<td>(\d+)',s)
        if m:metrics[key]=int(m.group(1))
xml=list((D/'impl/gwsynthesis').glob('*_syn_rsc.xml'))
if xml:metrics['Register']=int(ET.parse(xml[0]).getroot().get('T_Register').split('(')[0])
record=dict(status='PASS synthesis only' if rc==0 and not re.search(r'^ERROR',log,re.M) else 'FAILED synthesis',returncode=rc,seconds=round(time.time()-start,2),top='instrument_layer_probe',metrics=metrics,pnr_tested=False,hardware_tested=False,inputs=inputs,project_sha256=hashlib.sha256((D/'probe.gprj').read_bytes()).hexdigest(),tcl_sha256=hashlib.sha256((D/'synth.tcl').read_bytes()).hexdigest())
(D/'run.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in record.items() if k!='inputs'}),flush=True)
if rc:print(log[-2500:])
