from common import *
import html,re,shutil
def rows(text):
 return [[html.unescape(re.sub('<[^>]*>','',v)).strip() for v in re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S|re.I)] for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',text,re.S|re.I)]
D=R/'build_board';b=json.loads((D/'run.json').read_text(encoding='utf-8'))
assert b['returncode']==0 and b['status']=='build completed; timing needs audit'
assert sha(D/'board_config.gprj')==b['project_sha256'] and sha(D/'build.tcl')==b['tcl_sha256']
for name,item in b['inputs'].items():assert sha(D/name)==sha(R/item['source'])==item['sha256'],name
log=(D/'console.txt').read_text(encoding='utf-8');assert 'ERROR (' not in log and 'Bitstream generation completed' in log
expected={'clk':4,'reset_button':87,'uart_rx_pin':70,'uart_tx_pin':69,'pa_en':51,'dac_din':54,'dac_ws':55,'dac_bck':56,**{'led[%d]'%i:15+i for i in range(6)}}
Q=D/'impl/pnr';pins=rows((Q/'board_config.pin.html').read_text(encoding='utf-8'))
actual={r[1]:int(r[0].split('/')[0]) for r in pins if len(r)>5 and '/' in r[0] and r[2] in ('in','out','inout') and r[1]!='-'}
assert actual==expected,actual
assert all(r[5]=='LVCMOS33' for r in pins if len(r)>5 and r[1] in expected)
text=(Q/'board_config.rpt.txt').read_text(encoding='utf-8');metrics={}
for key in ('Logic','Register','BSRAM','I/O Port'):
 m=re.search(r'^\s*'+re.escape(key)+r'\s*\|\s*(\d+)',text,re.M);assert m,key;metrics[key]=int(m[1])
timing=(Q/'board_config_tr_content.html').read_text(encoding='utf-8');slack={}
for kind,end in [('Setup','Hold'),('Hold','Recovery')]:
 section=timing.split('name="'+kind+'_Slack_Table"')[1].split('name="'+end+'_Slack_Table"')[0]
 values=[float(r[1]) for r in rows(section) if len(r)>2 and r[0].isdigit()]
 assert values,kind;slack[kind]=min(values);assert slack[kind]>=0,slack
section=timing.split('name="Total_Negative_Slack_Report"')[1].split('name="Detail"')[0]
tns=[r for r in rows(section) if len(r)==4 and r[1] in ('Setup','Hold')]
assert len(tns)==2 and all(float(r[2])==0 and int(r[3])==0 for r in tns)
for name in ('board-config','board-nominal'):
 v=json.loads((E/(name+'.json')).read_text());assert v['status'].startswith('PASS')
 for p,h in v['inputs'].items():assert sha(R/p)==h,(name,p)
package=R/'package';package.mkdir(exist_ok=True)
shutil.copyfile(Q/'board_config.fs',package/'config-sram.fs')
old=R.parents[1]/'experiments/board_audio_20261017'
old_manifest=json.loads((old/'package/manifest.json').read_text(encoding='utf-8'))
for name in ('board-audio-sram.fs','mute-sram.fs'):
 assert sha(old/'package'/name)==old_manifest['files'][name]
 shutil.copyfile(old/'package'/name,package/('rollback-'+name))
record=dict(status='PASS board diagnostic pin/internal timing and wrapper simulation audit only',resource=metrics,slack_ns=slack,tns=0,pins=actual,bitstream_sha256=sha(package/'config-sram.fs'),warnings=[l for l in log.splitlines() if 'WARN ' in l],external_i2s_timing_verified=False,full_system_pnr=False,hardware_tested=False,build_record_sha256=sha(D/'run.json'),inputs={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__).resolve(),R/'common.py',*list((R/'constraints').glob('*'))]})
(E/'board-build-audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
manifest=dict(device='GW2AR-LV18QN88C8/I7',operation='SRAM Program 2 only',configuration_capability=[117,1,4,16,11,7],diagnostic_identity=dict(C0=0x72,C2=0x76,C3=1,A4=0xd3,A9=32),default_sound='silent until host sends notes; one-second warm gate',hardware_tested=False,files={p.name:sha(p) for p in package.iterdir() if p.is_file() and p.name!='manifest.json'})
(package/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(dict(resource=metrics,slack_ns=slack,ports=len(actual),hardware_tested=False)))
