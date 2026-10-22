from common import *
import shutil,time,re,xml.etree.ElementTree as ET,sys
D=R/(sys.argv[1] if len(sys.argv)>1 else 'synthesis_full');D.mkdir(exist_ok=False)
files=sources()+list((R/'src').glob('*.hex'))+list((R/'src').glob('*.vh'));inputs={}
if len(sys.argv)>2 and sys.argv[2]=='reference':files=[R/'reference/osc_env_original.v' if p.name=='osc_env.v' else p for p in files]
for p in files:
    name='osc_env.v' if p.name=='osc_env_original.v' else p.name
    shutil.copyfile(p,D/name);inputs[name]=dict(source=p.relative_to(R).as_posix(),sha256=sha(p))
(D/'inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
(D/'probe.gprj').write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project><Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>'+''.join('<File path="'+('osc_env.v' if p.name=='osc_env_original.v' else p.name)+'" type="file.verilog" enable="1"/>' for p in files if p.suffix=='.v')+'</FileList></Project>',encoding='utf-8')
(D/'synth.tcl').write_text('open_project "'+(D/'probe.gprj').as_posix()+'"\nset_option -top_module instrument_layer_probe\nrun syn\nexit\n',encoding='utf-8')
start=time.time();exe='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
with (D/'console.txt').open('w',encoding='utf-8') as f:
    p=subprocess.Popen([exe,str(D/'synth.tcl')],cwd=D,stdout=f,stderr=subprocess.STDOUT)
    try:rc=p.wait(timeout=300)
    except subprocess.TimeoutExpired:
        subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True);p.wait(timeout=30);rc=124
log=(D/'console.txt').read_text(encoding='utf-8',errors='replace');metrics={};report=D/'impl/gwsynthesis/probe_syn.rpt.html'
if report.exists():
    text=report.read_text(encoding='utf-8',errors='replace')
    for key in ('Logic','BSRAM'):
        match=re.search('>'+key+r'</td>\s*<td>(\d+)',text)
        if match:metrics[key]=int(match[1])
    xml=D/'impl/gwsynthesis/probe_syn_rsc.xml'
    if xml.exists():metrics['Register']=int(ET.parse(xml).getroot().get('T_Register').split('(')[0])
data=dict(status='PASS synthesis only' if rc==0 and 'ERROR (' not in log else 'FAILED synthesis',returncode=rc,metrics=metrics,seconds=round(time.time()-start,2),inputs=inputs,project_sha256=sha(D/'probe.gprj'),tcl_sha256=sha(D/'synth.tcl'),pnr_tested=False,hardware_tested=False)
(D/'run.json').write_text(json.dumps(data,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in data.items() if k!='inputs'}),flush=True)
if rc:print(log[-2000:]);raise SystemExit(rc)
