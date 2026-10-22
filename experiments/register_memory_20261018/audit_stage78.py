"""Check the new diagnostic build; do not promote or program any package."""
from common import *
import re,html
def rows(text):
 return [[html.unescape(re.sub('<[^>]*>','',v)).strip() for v in re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S|re.I)] for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',text,re.S|re.I)]
D=R/'build_board_register';b=json.loads((D/'run.json').read_text(encoding='utf-8'));assert b['returncode']==0
assert sha(D/'board_config.gprj')==b['project_sha256'] and sha(D/'build.tcl')==b['tcl_sha256']
for name,item in b['inputs'].items():assert sha(D/name)==sha(R/item['source'])==item['sha256'],name
log=(D/'console.txt').read_text(encoding='utf-8');assert 'ERROR (' not in log and 'Bitstream generation completed' in log
expected={'clk':4,'reset_button':87,'uart_rx_pin':70,'uart_tx_pin':69,'pa_en':51,'dac_din':54,'dac_ws':55,'dac_bck':56,**{'led[%d]'%i:15+i for i in range(6)}}
Q=D/'impl/pnr';pins=rows((Q/'board_config.pin.html').read_text(encoding='utf-8'))
actual={r[1]:int(r[0].split('/')[0]) for r in pins if len(r)>5 and '/' in r[0] and r[2] in ('in','out','inout') and r[1]!='-'}
assert actual==expected and all(r[5]=='LVCMOS33' for r in pins if len(r)>5 and r[1] in expected)
text=(Q/'board_config.rpt.txt').read_text(encoding='utf-8');metrics={}
for key in ('Logic','Register','BSRAM','I/O Port'):
 m=re.search(r'^\s*'+re.escape(key)+r'\s*\|\s*(\d+)',text,re.M);assert m,key;metrics[key]=int(m[1])
timing=(Q/'board_config_tr_content.html').read_text(encoding='utf-8');slack={}
for kind,end in [('Setup','Hold'),('Hold','Recovery')]:
 section=timing.split('name="'+kind+'_Slack_Table"')[1].split('name="'+end+'_Slack_Table"')[0]
 values=[float(r[1]) for r in rows(section) if len(r)>2 and r[0].isdigit()];assert values,kind
 slack[kind]=min(values);assert slack[kind]>=0,slack
section=timing.split('name="Total_Negative_Slack_Report"')[1].split('name="Detail"')[0]
tns=[r for r in rows(section) if len(r)==4 and r[1] in ('Setup','Hold')];assert len(tns)==2 and all(float(r[2])==0 and int(r[3])==0 for r in tns)
for name in ('board-config','board-nominal'):
 v=json.loads((E/(name+'.json')).read_text());assert v['status'].startswith('PASS')
 for p,h in v['inputs'].items():assert sha(R/p)==h,(name,p)
record=dict(status='PASS diagnostic internal PnR/pins and wrapper simulation only',resource=metrics,slack_ns=slack,tns=0,pins=actual,bitstream_sha256=sha(Q/'board_config.fs'),programmed=False,hardware_tested=False,full_system_pnr=False,external_i2s_timing_verified=False,warnings=[l for l in log.splitlines() if 'WARN ' in l],inputs={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__).resolve(),R/'common.py',*list((R/'constraints').glob('*'))]})
(E/'board-register-audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps(dict(resource=metrics,slack_ns=slack,hardware_tested=False,programmed=False)))
