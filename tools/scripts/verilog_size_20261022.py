"""Count authored Verilog once per selected source tree, excluding build copies.

code_lines is physical nonblank lines after lexical comment removal, not gates
or statements. String literals are preserved. Generated Gowin netlists, hex
assets and vendor/reference copies are not part of the RTL size headline.
"""
from pathlib import Path
import hashlib,json,re,xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
MAIN=Path('C:/Users/Sakuya/FPGA-Music-project')
C=ROOT/'experiments/nano20k_feasibility_20261021'
U=MAIN/'experiments/joint_probe_resources_20261019'
OUT=ROOT/'notes/nano20k-next-stage-20261022'
OUT.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
tokens=re.compile(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\r\n]*',re.S)
def uncomment(s):
    return tokens.sub(lambda m:m[0] if m[0].startswith('"') else ' '+'\n'*m[0].count('\n'),s)
def measure(p):
    raw=p.read_text(encoding='utf-8-sig',errors='strict');code=uncomment(raw)
    return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size,
        physical_lines=len(raw.splitlines()),nonblank_lines=sum(bool(l.strip()) for l in raw.splitlines()),
        code_lines=sum(bool(l.strip()) for l in code.splitlines()),
        module_definitions=len(re.findall(r'\bmodule\s+[A-Za-z_$][\w$]*',code)))
def group(paths):
    files=[measure(p) for p in sorted(set(paths))]
    return dict(file_count=len(files),unique_contents=len({f['sha256'] for f in files}),
                **{k:sum(f[k] for f in files) for k in ('physical_lines','nonblank_lines','code_lines','bytes','module_definitions')},files=files)
def project_files(gprj,base=None):
    return [(base or gprj.parent)/p.get('path') for p in ET.parse(gprj).getroot().findall('.//File')
            if p.get('enable')=='1' and p.get('type')=='file.verilog']
def source_files(base):
    return [p for folder in ('engine/src','engine/rtl','rtl') for p in (base/folder).glob('*.v')]
groups={
    'main_rtl_directory':group((MAIN/'src/rtl').glob('*.v')),
    'main_legacy_shipping_project':group(project_files(MAIN/'src/gowin/tdm_synth/tdm_synth.gprj')),
    'main_simulation_sources':group((MAIN/'src/sim').rglob('*.v')),
    'experiment86_project_sources':group(source_files(U)),
    'current_candidate_project_sources':group(source_files(C)),
    'current_candidate_testbenches':group(list((C/'tb').glob('tb*.v'))+list(C.glob('tb*.v'))),
    'current_candidate_headers':group((C/'engine/src').glob('*.vh')),
}
build=ET.parse(C/'build_nominal_v0/board.gprj').getroot()
enabled=[p.get('path') for p in build.findall('.//File') if p.get('enable')=='1' and p.get('type')=='file.verilog']
assert set(enabled)=={p.name for p in source_files(C)}
delta=[str(p.relative_to(C)).replace('\\','/') for p in source_files(C) if sha(p)!=sha(U/p.relative_to(C))]
data=dict(date='2026-10-22',method='Physical source lines, and nonblank physical lines after lexical // and /* */ removal; source copies counted only in their own profile. No generated netlists/hex/vendor models in RTL headline.',
    script_sha256=sha(Path(__file__).resolve()),
    warning='The enabled project source set also contains unused historical modules. This is source volume, not the number of elaborated modules or a resource estimate. Profiles overlap and must not be summed.',
    groups=groups,only_changed_rtl_from86=delta,
    current_largest_sources=sorted(groups['current_candidate_project_sources']['files'],key=lambda f:f['physical_lines'],reverse=True)[:10])
(OUT/'verilog-size.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({name:{k:v for k,v in g.items() if k!='files'} for name,g in groups.items()},ensure_ascii=False,indent=2))
print('Largest current:',[(Path(f['path']).name,f['physical_lines'],f['code_lines']) for f in data['current_largest_sources']])
