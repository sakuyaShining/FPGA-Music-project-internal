from common import *
import sys,shutil,re,time,xml.etree.ElementTree as ET
mode=sys.argv[1];assert mode in ('reference','buffered','standalone')
D=R/('synthesis_'+mode+('_'+sys.argv[2] if len(sys.argv)>2 else ''));D.mkdir(exist_ok=False)
files=sources()+list((R/'engine/src').glob('*.hex'))+list((R/'engine/src').glob('*.vh'))
if mode=='reference':files=[R/'reference/sdram_stream_probe.v' if p.name=='sdram_stream_probe.v' else p for p in files]
inputs={}
for p in files:
 assert p.name not in inputs;shutil.copyfile(p,D/p.name);inputs[p.name]=dict(source=p.relative_to(R).as_posix(),sha256=sha(p))
(D/'probe.gprj').write_text('<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project><Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>'+''.join('<File path="'+p.name+'" type="file.verilog" enable="1"/>' for p in files if p.suffix=='.v')+'</FileList></Project>')
top='pcm_sdram_arbiter' if mode=='standalone' else 'sdram_stream_probe'
(D/'synth.tcl').write_text('open_project "'+(D/'probe.gprj').as_posix()+'"\nset_option -top_module '+top+'\nrun syn\nexit\n')
start=time.monotonic()
exe='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
with (D/'console.log').open('w',encoding='utf-8') as f:
 proc=subprocess.Popen([exe,str(D/'synth.tcl')],cwd=D,stdout=f,stderr=subprocess.STDOUT)
 try:rc=proc.wait(timeout=600)
 except subprocess.TimeoutExpired:
  subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True);proc.wait();rc=124
log=(D/'console.log').read_text(encoding='utf-8',errors='replace');metrics={}
report=D/'impl/gwsynthesis/probe_syn.rpt.html'
if report.exists():
 s=report.read_text(encoding='utf-8')
 for k in ('Logic','BSRAM'):
  m=re.search('>'+k+r'</td>\s*<td>(\d+)',s)
  if m:metrics[k]=int(m[1])
 xml=D/'impl/gwsynthesis/probe_syn_rsc.xml'
 if xml.exists():metrics['Register']=int(ET.parse(xml).getroot().get('T_Register').split('(')[0])
status='PASS synthesis only' if rc==0 and 'ERROR (' not in log else 'FAILED synthesis'
record=dict(status=status,metrics=metrics,returncode=rc,seconds=round(time.monotonic()-start,2),inputs=inputs,top=top,project_sha256=sha(D/'probe.gprj'),tcl_sha256=sha(D/'synth.tcl'),pnr_tested=False,hardware_tested=False)
(D/'run.json').write_text(json.dumps(record,indent=2))
print(json.dumps({k:v for k,v in record.items() if k!='inputs'}));assert status.startswith('PASS'),log[-2000:]
