"""Extract actual routed critical paths; do not infer timing from utilization."""
from common import *
from audit_timing import rows
import re,csv
D=R/'build_nominal_v0';P=D/'impl/pnr/board_tr_content.html'
s=P.read_text(encoding='utf-8');result={}
for kind in ('Setup','Hold'):
    section=s.split('name="'+kind+'_Analysis"',1)[1]
    path=section.split('<h3>Path2</h3>',1)[0]
    tables=re.findall(r'<table\b[^>]*>(.*?)</table>',path,re.S)
    summary=dict(r for r in rows(tables[0]) if len(r)==2)
    data=[r for r in rows(tables[1]) if len(r)==7]
    first=next(i for i,r in enumerate(data) if r[2]=='tC2Q')
    data=data[first:]
    sums={k:round(sum(float(r[1]) for r in data if r[2]==k),3) for k in ('tNET','tINS','tC2Q')}
    result[kind]=dict(summary=summary,data_path_delay_sums_ns=sums,
        largest_net_delays=sorted([r for r in data if r[2]=='tNET'],key=lambda r:float(r[1]),reverse=True)[:8],
        arrival_nodes=data)
    with (R/(kind.lower()+'-critical-path.csv')).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['arrival_ns','delay_ns','type','edge','fanout','location','node']);w.writerows(data)
result['report_sha256']=sha(P)
result['interpretation']='Setup crosses pitch_mod async native RAM, lazy advance/selection/clamp, phase modulation arithmetic and phase RAM write; Hold originates in temporary scan DSP. Retiming must preserve epoch/forwarding/sample boundaries.'
(R/'critical-paths.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:dict(slack=v['summary'].get('Slack'),sums=v['data_path_delay_sums_ns']) for k,v in result.items() if k in ('Setup','Hold')}))
