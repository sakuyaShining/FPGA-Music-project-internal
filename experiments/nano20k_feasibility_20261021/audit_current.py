"""Audit the new scoped probe honestly. Product qualification is always false."""
from common import *
import re, xml.etree.ElementTree as ET
from audit_timing import constraints, timing, rows

U=Path(json.loads((R/'source-identity.json').read_text())['upstream'])
frozen=json.loads((R/'source-identity.json').read_text())['files']
assert all(sha(U/k)==h for k,h in frozen.items()),'Upstream changed during assessment'
changed=[k for k,h in frozen.items() if k.startswith(('engine/','rtl/','constraints/')) and sha(R/k)!=h]
assert changed==['engine/src/mv_renderer.v'],changed
builds={}
for D in sorted(R.glob('build_*')):
    if not D.is_dir() or not (D/'run.json').exists():continue
    d=json.loads((D/'run.json').read_text())
    assert all(sha(D/name)==sha(R/v['source'])==v['sha256'] for name,v in d['inputs'].items())
    assert sha(D/'board.gprj')==d['project_sha256'] and sha(D/'build.tcl')==d['tcl_sha256']
    sdc=D/('sdram_board.sdc' if d['mode']=='nominal' else 'stress.sdc')
    constraints(sdc.read_text())
    log=(D/'console.log').read_text(encoding='utf-8',errors='replace')
    errors=[l for l in log.splitlines() if re.search(r'\bERROR\s*\(|Error:',l)]
    successful=d['returncode']==0 and 'Bitstream generation completed' in log and not errors
    metrics={};p=D/'impl/pnr/board.rpt.txt'
    if p.exists():
        report=p.read_text()
        for k in ('Logic','Register','CLS','BSRAM','DSP','I/O Port'):
            m=re.search(r'^\s*'+re.escape(k)+r'\s*\|\s*([\d.]+)/([\d.]+)',report,re.M)
            if m:metrics[k]=dict(used=float(m[1]),capacity=float(m[2]))
    x=D/'impl/gwsynthesis/board_syn_rsc.xml'
    hierarchy={}
    if x.exists():
        def walk(n,p=''):
            p+=('/' if p else '')+n.get('name');a=n.attrib
            val=lambda k:int(a.get(k,'0').split('(')[0])
            hierarchy[p]=dict(logic=val('T_Lut')+val('T_Alu')+val('T_Ssram')*6,
                              register=val('T_Register'),bsram=val('T_Bsram'))
            for c in n:walk(c,p)
        walk(ET.parse(x).getroot())
    sta=None;static_pass=False
    if successful:
        assert (D/'impl/pnr/board.fs').is_file()
        sta=timing((D/'impl/pnr/board_tr_content.html').read_text(encoding='utf-8'))
        static_pass=all(v>=0 for v in sta['slack_ns'].values())
        pinrows=rows((D/'impl/pnr/board.pin.html').read_text(encoding='utf-8'))
        sip=[v for v in pinrows if len(v)>7 and (v[0].startswith('O_sdram') or v[0].startswith('IO_sdram'))]
        assert len(sip)==55 and all(v[2].startswith('p') for v in sip)
    builds[D.name]=dict(returncode=d['returncode'],seconds=d['seconds'],mode=d['mode'],
        route_completed=successful,scoped_static_pass=static_pass,errors=errors,resource=metrics,
        timing=sta,hierarchy=hierarchy,warnings=[l for l in log.splitlines() if 'WARN' in l],
        identities={str(p.relative_to(R)):sha(p) for p in [D/'run.json',D/'console.log',sdc,x] if p.exists()})

required=['renderer-equivalence.json','engine-compatibility.json','joint-model.json']
regressions={}
for n in required:
    p=E/n
    if not p.exists():regressions[n]='NOT COMPLETE';continue
    d=json.loads(p.read_text());assert d['status'].startswith('PASS')
    for name,h in d['inputs'].items():
        path=Path(name) if Path(name).is_absolute() else R/name
        assert sha(path)==h,(n,name)
    regressions[n]=dict(status=d['status'],sha256=sha(p))
result=dict(status='Recorded scoped probe evidence; full product NOT qualified',changed_from86=changed,
            regressions=regressions,builds=builds,product_top_exists=False,product_static_pass=False,
            bench_gate=False,hardware_programmed=False,hardware_interface_changed=False)
(R/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status=result['status'],builds={n:{k:v for k,v in b.items() if k not in ('hierarchy','warnings','identities')} for n,b in builds.items()},regressions=regressions),ensure_ascii=False))
