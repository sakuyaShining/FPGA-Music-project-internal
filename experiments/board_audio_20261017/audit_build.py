from common import *
import re,html,shutil
def rows(text):
    return [[html.unescape(re.sub('<[^>]*>','',v)).strip() for v in re.findall(r'<td\b[^>]*>(.*?)</td>',row,re.S|re.I)] for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',text,re.S|re.I)]
expected={'clk':4,'reset_button':87,'uart_rx_pin':70,'uart_tx_pin':69,'pa_en':51,'dac_din':54,'dac_ws':55,'dac_bck':56,**{'led[%d]'%i:15+i for i in range(6)}}
profiles={}
for profile in ('build_ready_default','build_mute'):
    D=R/profile;run_data=json.loads((D/'run.json').read_text(encoding='utf-8'));assert run_data['returncode']==0
    assert run_data['project_sha256']==sha(D/'board_audio.gprj') and run_data['tcl_sha256']==sha(D/'build.tcl')
    for name,item in run_data['inputs'].items():assert sha(D/name)==item['sha256'] and sha(R/item['source'])==item['sha256'],(profile,name)
    log=(D/'console.txt').read_text(encoding='utf-8',errors='replace');assert 'ERROR (' not in log and 'Bitstream generation completed' in log
    P=D/'impl/pnr';report=(P/'board_audio.rpt.txt').read_text(encoding='utf-8',errors='replace')
    metric={}
    for key in ('Logic','Register','BSRAM','CLS','I/O Port'):
        match=re.search(r'^\s*'+re.escape(key)+r'\s*\|\s*(\d+)',report,re.M)
        if match:metric[key]=int(match[1])
        else:assert profile=='build_mute' and key=='BSRAM';metric[key]=0
    pin_rows=rows((P/'board_audio.pin.html').read_text(encoding='utf-8',errors='replace'))
    ports={r[1]:int(r[0].split('/')[0]) for r in pin_rows if len(r)>5 and '/' in r[0] and r[2] in ('in','out','inout') and r[1]!='-'}
    assert ports==expected,(profile,ports)
    assert all(r[5]=='LVCMOS33' for r in pin_rows if len(r)>5 and r[1] in expected)
    timing=(P/'board_audio_tr_content.html').read_text(encoding='utf-8',errors='replace')
    slack={}
    for kind,end in [('Setup','Hold'),('Hold','Recovery')]:
        section=timing.split('name="'+kind+'_Slack_Table"')[1].split('name="'+end+'_Slack_Table"')[0]
        values=[float(r[1]) for r in rows(section) if len(r)>2 and r[0].isdigit()]
        assert values,(profile,kind);slack[kind]=min(values);assert slack[kind]>=0,(profile,slack)
    tns_section=timing.split('name="Total_Negative_Slack_Report"')[1].split('name="Detail"')[0]
    tns=[r for r in rows(tns_section) if len(r)==4 and r[1] in ('Setup','Hold')]
    assert len(tns)==2 and all(float(r[2])==0 and int(r[3])==0 for r in tns)
    warnings=[line for line in log.splitlines() if 'WARN ' in line]
    assert not any('EX3791' in line and any(n in line for n in ('board_audio_top.v','board_test_driver.v','tdm_top_owned.v')) for line in warnings)
    profiles[profile]=dict(status='PASS internal constrained PnR and pin audit only',resource=metric,slack_ns=slack,tns=0,pins=ports,bitstream_sha256=sha(P/'board_audio.fs'),warnings=warnings,external_i2s_timing_verified=False,hardware_tested=False)
package=R/'package';package.mkdir(exist_ok=True)
for profile,name in [('build_ready_default','board-audio-sram.fs'),('build_mute','mute-sram.fs')]:shutil.copyfile(R/profile/'impl/pnr/board_audio.fs',package/name)
shutil.copyfile(R/'board_check.py',package/'board_check.py')
artifact_files={p.name:sha(p) for p in package.iterdir() if p.is_file() and p.name!='manifest.json'}
(package/'manifest.json').write_text(json.dumps(dict(profile=0x72,abi=1,device='GW2AR-LV18QN88C8/I7',download_mode='SRAM only; no download performed',hardware_tested=False,files=artifact_files),indent=2),encoding='utf-8')
inputs=[Path(__file__).resolve(),R/'common.py']+list((R/'constraints').glob('*'))+[R/'board_check.py']
(E/'build-audit.json').write_text(json.dumps(dict(status='PASS pin/PnR package audit only',profiles=profiles,inputs={p.relative_to(R).as_posix():sha(p) for p in inputs}),indent=2),encoding='utf-8')
print(json.dumps({k:{'resource':v['resource'],'slack_ns':v['slack_ns'],'ports':len(v['pins'])} for k,v in profiles.items()}),flush=True)
