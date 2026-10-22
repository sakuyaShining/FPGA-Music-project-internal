"""Hash source, actual evidence and routed outputs without modifying old baselines."""
from common import *
import zipfile
report=R.parents[1]/'docs/02-技术方案/87-Nano20K完整功能可行性与预算-2026-10-22.md'
sources=[p for p in R.iterdir() if p.is_file() and p.name not in ('delivery.json',)]
for folder in ('engine','rtl','reference','tb','project'):
    sources += [p for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
evidence=[p for p in E.iterdir() if p.is_file()]
D=R/'build_nominal_v0'
build=[p for p in D.rglob('*') if p.is_file()]
data=dict(version='nano20k-feasibility-20261021-v0',report=str(report),report_sha256=sha(report),
          product_complete=False,product_static_pass=False,probe_routed=True,probe_static_pass=False,
          bench_gate=False,hardware_programmed=False,pcb_changed=False,
          source_files={str(p.relative_to(R)).replace('\\','/'):sha(p) for p in sources},
          evidence_files={str(p.relative_to(R)).replace('\\','/'):sha(p) for p in evidence},
          build_files={str(p.relative_to(R)).replace('\\','/'):sha(p) for p in build},
          external_identity_inputs=json.loads((R/'budget.json').read_text(encoding='utf-8'))['inputs'],
          note='Build/evidence are D-drive junctions. Newly generated structural .fs is forbidden to program; not a full product bitstream.')
(R/'delivery.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
# Compact review package: sources, machine results, report, raw timing/report/log.
# Full simulator traces and generated .fs remain preserved in D-drive directories.
out=Path('D:/FPGA-Project/codex-deliverables/nano20k-feasibility-20261022')
out.mkdir(parents=True,exist_ok=True)
archive=out/'review-package.zip'
assert not archive.exists(),'Refuse to overwrite review delivery'
included=sources+[R/'delivery.json',report]
included += [p for p in evidence if p.suffix in ('.json','.log')]
included += [p for p in build if p.name in ('run.json','console.log','board.gprj','build.tcl','board.rpt.txt','board.pin.html','board_tr_content.html','board_syn_rsc.xml')]
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in included:
        member='report/'+p.name if p==report else str(p.relative_to(R)).replace('\\','/')
        z.write(p,member)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in included:
        member='report/'+p.name if p==report else str(p.relative_to(R)).replace('\\','/')
        assert hashlib.sha256(z.read(member)).hexdigest()==sha(p)
(out/'package-sha256.json').write_text(json.dumps(dict(archive=str(archive),sha256=sha(archive),members=len(included),
    source_manifest=str(R/'delivery.json'),delivery_sha256=sha(R/'delivery.json')),indent=2),encoding='utf-8')
print(json.dumps(dict(archive=str(archive),sha256=sha(archive),members=len(included),source_count=len(sources),evidence_count=len(evidence),build_count=len(build))))
