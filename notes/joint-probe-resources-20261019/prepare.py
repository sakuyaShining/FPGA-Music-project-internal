from pathlib import Path
import hashlib,json,zipfile,datetime,shutil,subprocess
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
U=P/'experiments/joint_timing_20261019';R=P/'experiments/joint_probe_resources_20261019'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
u=read(U/'delivery.json');old=read(U/'upstream.json')
for rel,h in u['files'].items():assert sha(U/rel)==h,rel
assert not R.exists()
paths=[p for folder in ('engine','rtl','constraints','tb') for p in (U/folder).rglob('*') if p.is_file()]
paths += [U/'delivery.json',U/'project/scan-map.json',U/'build_board.py',U/'audit_timing.py',U/'reference/stress.sdc']
paths += [next((P/'docs/02-技术方案').glob(prefix+'*.md')) for prefix in ('38-','39-','49-','85-')]
B=N/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));B.mkdir();items={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
    for i,p in enumerate(paths):
        member='files/%04d/%s'%(i,p.name);z.write(p,member);items[str(p)]=dict(member=member,sha256=sha(p))
with zipfile.ZipFile(B/'before.zip') as z:
    assert z.testzip() is None
    for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
(B/'manifest.json').write_text(json.dumps(items,indent=2),encoding='utf-8');(N/'latest-backup.txt').write_text(str(B),encoding='utf-8')
for folder in ('engine','rtl','constraints','tb','reference','project'):shutil.copytree(U/folder,R/folder)
for pattern in ('*.py','*.hex','tb*.v'):
    for p in U.glob(pattern):
        if p.name not in ('verify_delivery.py',):shutil.copyfile(p,R/p.name)
out=Path('D:/FPGA-Project/codex-builds/joint-probe-resources-20261019/evidence');out.mkdir(parents=True)
subprocess.run(['powershell','-NoProfile','-Command',"New-Item -ItemType Junction -Path '%s' -Target '%s' -ErrorAction Stop | Out-Null"%(R/'evidence',out)],check=True)
shutil.copyfile(U/'rtl/joint_timing_top.v',R/'reference/joint_timing_top.v')
s=(R/'build_board.py').read_text(encoding='utf-8').replace('codex-builds/joint-timing-20261019','codex-builds/joint-probe-resources-20261019')
(R/'build_board.py').write_text(s,encoding='utf-8')
(R/'upstream.json').write_text(json.dumps(dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),files=u['files'],board_root=old['board_root'],board_delivery_sha256=old['board_delivery_sha256'],board_files=old['board_files']),indent=2),encoding='utf-8')
lib=Path('D:/FPGA-Project/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64/IDE/simlib/gw2a/prim_sim.v');s=lib.read_text(encoding='utf-8');models=[]
for name in ('ALU54D','GSR'):
    model=s[s.index('module '+name+' ('):];model=model[:model.index('endmodule')+len('endmodule')];models.append(model)
(R/'tb/vendor_alu54d.v').write_text('// Exact functional definitions from installed vendor simulation library.\n'+'\n'.join(models)+'\n',encoding='utf-8')
(R/'reference/alu-model-source.json').write_text(json.dumps(dict(path=str(lib),library_sha256=sha(lib),model_sha256=sha(R/'tb/vendor_alu54d.v')),indent=2),encoding='utf-8')
print('PASS isolated backup',len(items),'inputs; no upstream changes')
