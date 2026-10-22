"""Fail closed on missing I/O constraints and negative path tables.
TNS summaries in this tool version can omit failing output endpoints.
"""
from common import *
import html,re
def rows(s):
 return [[html.unescape(re.sub('<[^>]*>','',v)).strip() for v in re.findall(r'<td\b[^>]*>(.*?)</td>',r,re.S|re.I)] for r in re.findall(r'<tr\b[^>]*>(.*?)</tr>',s,re.S|re.I)]
def timing(folder):
 D=R/folder;Q=D/'impl/pnr';s=(Q/'board_tr_content.html').read_text(encoding='utf-8');slacks={};paths={}
 for kind,end in [('Setup','Hold'),('Hold','Recovery'),('Recovery','Removal'),('Removal','MPW')]:
  match=re.search(r'name="'+kind+r'_Slack_Table"(.*?)(?=<a name=|\Z)',s,re.S)
  assert match,(folder,kind)
  paths[kind]=[v for v in rows(match.group(1)) if len(v)>=9 and v[0].isdigit()]
  assert paths[kind],(folder,kind,'no timing paths')
  slacks[kind]=min(float(v[1]) for v in paths[kind])
 summary=[v for v in rows(s) if len(v)==2 and v[0].startswith('Numbers of')]
 return dict(slack_ns=slacks,worst_paths={k:v[0] for k,v in paths.items()},summary=summary)
def constraints(text,pll):
 assert 'create_generated_clock -name sdram_forward' in text,'missing forwarded clock'
 if pll:assert 'get_pins {clocking/CLKOUT}' in text and 'create_generated_clock -name core_clk' in text
 for command in ('set_input_delay','set_output_delay'):
  for mode in ('-max','-min'):
   matches=[l for l in text.splitlines() if l.startswith(command) and mode in l]
   assert len(matches)==1 and 'IO_sdram_dq[*]' in matches[0],(command,mode,'missing DQ constraints')
 for token in ('O_sdram_addr[*]','O_sdram_ba[*]','O_sdram_dqm[*]','O_sdram_ras_n','O_sdram_cas_n','O_sdram_wen_n'):
  assert all(token in l for l in text.splitlines() if l.startswith('set_output_delay')),token
 for l in text.splitlines():
  if l.startswith(('set_false_path','set_clock_groups','set_multicycle_path')):
   assert l in ('set_false_path -from [get_ports {reset_button}]','set_false_path -to [get_ports {led[*] uart_tx_pin}]'),('unreviewed exception',l)
 assert 'set_clock_uncertainty -setup' in text and 'set_clock_uncertainty -hold' in text
def build_identity(folder):
 D=R/folder;d=json.loads((D/'run.json').read_text(encoding='utf-8'));assert d['returncode']==0
 for name,v in d['inputs'].items():assert sha(D/name)==sha(R/v['source'])==v['sha256'],(folder,name)
 assert sha(D/'board.gprj')==d['project_sha256'] and sha(D/'build.tcl')==d['tcl_sha256']
 return d
selected={}
for folder,mode in [('build_pll32_nominal','nominal'),('build_pll32_stress','stress')]:
 D=R/folder;d=build_identity(folder)
 cst=(D/'sdram_board.cst').read_text();sdc_name='sdram_board.sdc' if mode=='nominal' else 'stress.sdc'
 constraints((D/sdc_name).read_text(),True)
 result=timing(folder);assert all(v>=0 for v in result['slack_ns'].values()),(folder,result)
 pins=rows((D/'impl/pnr/board.pin.html').read_text(encoding='utf-8'))
 # Use the first pin table (port name is column0); do not mix with its reverse.
 sip=[v for v in pins if len(v)>7 and (v[0].startswith('O_sdram') or v[0].startswith('IO_sdram'))]
 assert len(sip)==55 and all(v[2].startswith('p') and v[7]=='LVTTL33' for v in sip)
 external={v[0]:int(v[2].split('/')[0]) for v in pins if len(v)>7 and '/' in v[2] and not v[2].startswith('p') and v[4] in ('in','out','io')}
 expected={'clk':4,'reset_button':87,'uart_tx_pin':69,'pa_en':51,'dac_din':54,'dac_ws':55,'dac_bck':56,**{'led[%d]'%i:15+i for i in range(6)}}
 assert external==expected,external
 report=(D/'impl/pnr/board.rpt.txt').read_text();metrics={}
 for key in ('Logic','Register','I/O Port'):
  m=re.search(r'^\s*'+re.escape(key)+r'\s*\|\s*(\d+)',report,re.M);assert m,key;metrics[key]=int(m[1])
 assert 'logic_clk' in report and 'PRIMARY' in report and 'rPLL' in report
 log=(D/'console.log').read_text();assert 'ERROR (' not in log and 'Bitstream generation completed' in log
 result.update(resource=metrics,bitstream_sha256=sha(D/'impl/pnr/board.fs'),sip_ports={v[0]:v[2] for v in sip},external_pins=external,warnings=[v for v in log.splitlines() if 'WARN' in v])
 selected[mode]=result
# Wrong constraint files must be detected even when the tool says TNS=0.
missing_text=(R/'build_missing_io/missing_io.sdc').read_text()
try:constraints(missing_text,False)
except AssertionError as e:missing_reason=str(e)
else:raise AssertionError('missing I/O constraints escaped audit')
old_stress=timing('build_stress');assert old_stress['slack_ns']['Setup']<0
missing_report=timing('build_missing_io')
record=dict(status='PASS declared-envelope static audit and negative cases; experimental bench only',selected=selected,
 negative_cases=dict(unregistered_stress=old_stress,missing_io_reason=missing_reason,missing_io_falsely_good_slack=missing_report['slack_ns']),
 deployment_scope='volatile RAM diagnostic bench; not production or exact embedded die qualification',
 limitations=['embedded die/bin and package delays unbound','remaining clk_d PR1014 warning is PLL input; logic_clk has primary route','default timing report shows worst25 paths; not an exhaustive per-bit path certificate','no analog waveform/jitter or temperature/voltage sweep'],
 input_constraints_bits=32,output_constraints_bits=52,sip_ports=55,bench_gate=True,production_qualified=False,
 inputs={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__).resolve(),R/'common.py',*list((R/'rtl').glob('*.v')),*list((R/'constraints').glob('*')),R/'reference/stress.sdc',R/'build_pll32_nominal/run.json',R/'build_pll32_stress/run.json']})
for name in ('sdram-reference','board-model','pin-equivalence'):
 p=E/(name+'.json');d=json.loads(p.read_text());assert d['status'].startswith('PASS')
 for rel,h in d['inputs'].items():assert sha(R/rel)==h,(name,rel)
 record['inputs'][p.relative_to(R).as_posix()]=sha(p)
(E/'timing-audit.json').write_text(json.dumps(record,indent=2))
print(json.dumps(dict(status=record['status'],nominal=selected['nominal']['slack_ns'],stress=selected['stress']['slack_ns'],resource=selected['nominal']['resource'],negative_missing=missing_reason,old_stress_setup=old_stress['slack_ns']['Setup'],bench_gate=True,production_qualified=False)))
