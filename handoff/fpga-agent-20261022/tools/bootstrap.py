"""Create a NEW isolated FPGA workspace from verified packaged sources."""
from pathlib import Path
import argparse,difflib,hashlib,json,shutil
from verify import verify

P=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--destination',required=True);args=ap.parse_args()
verify(P)
raw=Path(args.destination)
assert raw.is_absolute(),'Use an absolute destination'
D=raw.resolve()
assert D!=P and P not in D.parents,'Do not create a work directory inside the frozen package'
assert not D.exists(),'Refuse to overwrite an existing workspace'
assert D.parent.is_dir(),'Destination parent must exist'
shutil.copytree(P/'candidate_source',D)
shutil.copytree(P/'support',D/'handoff_support')
(D/'evidence').mkdir();changes={}
def edit(name,old,new):
    p=D/name;s=p.read_text(encoding='utf-8');assert s.count(old)==1,(name,old)
    t=s.replace(old,new,1);p.write_text(t,encoding='utf-8')
    changes.setdefault(name,dict(steps=[]))['steps'].append(''.join(difflib.unified_diff(s.splitlines(True),t.splitlines(True),fromfile='previous/'+name,tofile='adapted/'+name)))
    changes[name]['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
edit('common.py','import subprocess,hashlib,json','import subprocess,hashlib,json,os')
edit('common.py',"IV='D:/iverilog/bin/iverilog.exe';VVP='D:/iverilog/bin/vvp.exe'",
     "IV=os.environ.get('FPGA_IVERILOG','D:/iverilog/bin/iverilog.exe');VVP=os.environ.get('FPGA_VVP','D:/iverilog/bin/vvp.exe')")
edit('check_engine_compat.py',"U=Path('C:/Users/Sakuya/FPGA-Music-project/experiments/resource_safety_20261016')", "U=R/'handoff_support/resource_safety_20261016'")
edit('check_pitch.py',"U=R.parents[1]/'experiments/pitch_memory_20261018'", "U=R/'handoff_support/pitch_memory_20261018'")
edit('check_sensor.py',"U=R.parents[1]/'experiments/system_integration_20261016'", "U=R/'handoff_support/system_integration_20261016'")
# Use ordinary fresh local build directories. No old D-drive label collision,
# junction sharing, string-built PowerShell mutation or upstream build writes.
build=D/'build_board.py';s=build.read_text(encoding='utf-8')
start=s.index("D=R/label;target=Path(");end=s.index("sdc=R/",start)
old=s[start:end]
edit('build_board.py',old,"D=R/label\nassert not D.exists(),'Refuse to overwrite an existing build'\nD.mkdir()\n")
edit('build_board.py',"exe='D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe';start=time.monotonic()",
     "exe=os.environ.get('FPGA_GOWIN_GW_SH','D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe');start=time.monotonic()")
for p in (D/'handoff_support/additional_tests').glob('check_*.py'):
    dst=D/p.name;assert not dst.exists();shutil.copyfile(p,dst)
    src=dst.read_text(encoding='utf-8')
    adapted=src.replace("R/'src'","R/'engine/src'").replace("files=sources()+", "files=sources()+[R/'tb/vendor_ram16sdp4.v']+")
    adapted=adapted.replace("[IV,'-g2012',", "[IV,'-g2012','-DTIMING_RTL_SIM',")
    dst.write_text(adapted,encoding='utf-8')
    changes[dst.name]=dict(sha256=hashlib.sha256(dst.read_bytes()).hexdigest(),origin=str(p.relative_to(D)),
                           adaptation="Source directory adaptation, TIMING_RTL_SIM functional macro and native RAM model inclusion for current complete source set")
for p in (D/'handoff_support/additional_tests').iterdir():
    if p.suffix in ('.v','.hex','.vh'):
        dst=D/p.name;assert not dst.exists() or dst.read_bytes()==p.read_bytes(),dst
        shutil.copyfile(p,dst)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_files=[p for folder in ('engine/src','engine/rtl','rtl') for p in (D/folder).glob('*') if p.is_file()]
assert all(sha(p)==sha(P/'candidate_source'/p.relative_to(D)) for p in source_files),'RTL changed in bootstrap'
protected=[p for p in (D/'tb').glob('*.v')]+list(D.glob('tb*.v'))+list(D.glob('*.hex'))
marker=dict(package_root=str(P),package_manifest_sha256=sha(P/'MANIFEST.json'),workspace=str(D),
    adaptations=changes,rtl_source_identities={p.relative_to(D).as_posix():sha(p) for p in source_files},
    protected_test_inputs={p.relative_to(D).as_posix():sha(p) for p in protected},
    hardware_programmed=False,bench_gate=False)
(D/'HANDOFF-WORKSPACE.json').write_text(json.dumps(marker,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='Created isolated workspace; RTL unchanged; helper paths adapted',workspace=str(D),
    marker=str(D/'HANDOFF-WORKSPACE.json'),source_files=len(source_files)),ensure_ascii=False))
