"""M1 structural-probe audit; never a complete-product or programming approval."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,re,sys
from verify import verify

P=Path(__file__).resolve().parents[1];verify(P)
ap=argparse.ArgumentParser();ap.add_argument('--workspace',required=True);ap.add_argument('--label',required=True)
ap.add_argument('--output',required=True);a=ap.parse_args()
assert re.fullmatch(r'build_[A-Za-z0-9_]+',a.label)
W=Path(a.workspace).resolve();D=W/a.label;out=Path(a.output).resolve()
assert not out.exists(),'Do not overwrite audit results'
assert W in out.parents,'Audit output must remain in the workspace'
sys.path.insert(0,str(W));spec=importlib.util.spec_from_file_location('audit_helpers',W/'audit_timing.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
d=json.loads((D/'run.json').read_text(encoding='utf-8'))
identity=all((D/n).is_file() and (W/v['source']).is_file() and sha(D/n)==sha(W/v['source'])==v['sha256'] for n,v in d['inputs'].items())
identity=identity and sha(D/'board.gprj')==d['project_sha256'] and sha(D/'build.tcl')==d['tcl_sha256']
assert identity,'Build inputs changed; do not sign stale results'
sdc=D/('sdram_board.sdc' if d['mode']=='nominal' else 'stress.sdc')
helper.constraints(sdc.read_text())
baseline_sdc=P/'candidate_source'/('constraints/sdram_board.sdc' if d['mode']=='nominal' else 'reference/stress.sdc')
assert sha(sdc)==sha(baseline_sdc),'M1 constraint envelope changed; requires a new reviewed audit scope'
assert sha(D/'sdram_board.cst')==sha(P/'candidate_source/constraints/sdram_board.cst'),'M1 pin contract changed'
log=(D/'console.log').read_text(encoding='utf-8',errors='replace')
errors=[l for l in log.splitlines() if re.search(r'\bERROR\s*\(|Error:',l)]
route=d['returncode']==0 and 'Bitstream generation completed' in log and not errors
sta=None;qualified=False;metrics={};pins_ok=False
if route:
    assert (D/'impl/pnr/board.fs').is_file()
    sta=helper.timing((D/'impl/pnr/board_tr_content.html').read_text(encoding='utf-8'))
    rows=helper.rows((D/'impl/pnr/board.pin.html').read_text(encoding='utf-8'))
    sip=[v for v in rows if len(v)>7 and (v[0].startswith('O_sdram') or v[0].startswith('IO_sdram'))]
    external={v[0]:int(v[2].split('/')[0]) for v in rows if len(v)>7 and '/' in v[2] and not v[2].startswith('p') and v[4] in ('in','out','io')}
    expected={'clk':4,'reset_button':87,'scan_in':70,'probe_out':69,'pa_en':51,'dac_din':54,'dac_ws':55,'dac_bck':56,**{'led[%d]'%i:15+i for i in range(6)}}
    pins_ok=len(sip)==55 and all(v[2].startswith('p') for v in sip) and external==expected
    qualified=pins_ok and all(v>=0 for v in sta['slack_ns'].values())
report=D/'impl/pnr/board.rpt.txt'
if report.exists():
    for k in ('Logic','Register','CLS','BSRAM','DSP'):
        m=re.search(r'^\s*'+k+r'\s*\|\s*([\d.]+)/([\d.]+)',report.read_text(),re.M)
        if m:metrics[k]=dict(used=float(m[1]),capacity=float(m[2]))
r=dict(status='PASS scoped structural STA' if qualified else 'FAIL or incomplete scoped structural STA',
    route_completed=route,scoped_static_pass=qualified,source_identity_pass=identity,pins_pass=pins_ok,
    timing=sta,resource=metrics,errors=errors,returncode=d['returncode'],
    product_qualified=False,bench_gate=False,hardware_programmed=False,
    report_inputs={str(p.relative_to(W)):sha(p) for p in [D/'run.json',sdc,report,D/'console.log',D/'impl/pnr/board_tr_content.html'] if p.exists()})
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(r,ensure_ascii=False));sys.exit(0 if qualified else 2)
