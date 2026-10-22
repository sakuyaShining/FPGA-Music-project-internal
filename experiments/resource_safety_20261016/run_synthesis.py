from common import *
import shutil,sys,time,re,xml.etree.ElementTree as ET
variant=sys.argv[1] if len(sys.argv)>1 else 'all'
assert variant in ('reference','anchor','identity','both','all')
D=R/(sys.argv[2] if len(sys.argv)>2 else ('synthesis_all_clean' if variant=='all' else 'synthesis_'+variant));D.mkdir(exist_ok=True)
files=sources(variant)+list((R/'engine').glob('*.hex'))+list((R/'rtl').glob('*.vh'))
assert len(files)==len({p.name for p in files})
inputs={}
for p in files:
    shutil.copyfile(p,D/p.name);inputs[p.name]=dict(source=p.relative_to(R).as_posix(),sha256=sha(p))
(D/'inputs.json').write_text(json.dumps(inputs,indent=2),encoding='utf-8')
(D/'probe.gprj').write_text('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE gowin-fpga-project>
<Project><Template>FPGA</Template><Version>5</Version><Device name="GW2AR-18C" pn="GW2AR-LV18QN88C8/I7">gw2ar18c-000</Device><FileList>
'''+''.join('<File path="'+p.name+'" type="file.verilog" enable="1"/>\n' for p in files if p.suffix=='.v')+'</FileList></Project>',encoding='utf-8')
(D/'synth.tcl').write_text('open_project "'+(D/'probe.gprj').as_posix()+'"\nset_option -top_module instrument_layer_probe\nrun syn\nexit\n',encoding='utf-8')
start=time.time();exe='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe'
with (D/'console.txt').open('w',encoding='utf-8') as f:
    proc=subprocess.Popen([exe,str(D/'synth.tcl')],cwd=D,stdout=f,stderr=subprocess.STDOUT);rc=proc.wait(timeout=240)
log=(D/'console.txt').read_text(encoding='utf-8',errors='replace');metrics={}
html=D/'impl/gwsynthesis/probe_syn.rpt.html'
if rc==0 and html.exists():
    text=html.read_text(encoding='utf-8',errors='replace')
    for key in ('Logic','BSRAM'):metrics[key]=int(re.search('>'+key+r'</td>\s*<td>(\d+)',text)[1])
    metrics['Register']=int(ET.parse(D/'impl/gwsynthesis/probe_syn_rsc.xml').getroot().get('T_Register').split('(')[0])
data=dict(status='PASS synthesis only' if rc==0 and 'ERROR (' not in log else 'FAILED synthesis',variant=variant,returncode=rc,metrics=metrics,seconds=round(time.time()-start,2),inputs=inputs,project_sha256=sha(D/'probe.gprj'),tcl_sha256=sha(D/'synth.tcl'),pnr_tested=False)
(D/'run.json').write_text(json.dumps(data,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in data.items() if k!='inputs'}),flush=True)
assert rc==0,log[-2000:]
