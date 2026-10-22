from pathlib import Path
import json,hashlib,zipfile,datetime,shutil
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
U=P/'experiments/pitch_memory_20261018';T=P/'experiments/sdram_stream_board_20261018';R=P/'experiments/joint_timing_20261019'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
u=read(U/'delivery.json');t=read(T/'delivery.json')
for root,d in ((U,u),(T,t)):
    for rel,h in d['files'].items():assert sha(root/rel)==h,(root,rel)
assert not R.exists()
paths=[p for folder in ('engine','rtl') for p in (U/folder).rglob('*') if p.is_file()]
paths += [U/'delivery.json',T/'delivery.json',T/'rtl/sdram_board_top.v',T/'constraints/sdram_board.cst',T/'constraints/sdram_board.sdc',T/'reference/stress.sdc',T/'audit_timing.py']
paths += [next((P/'docs/02-技术方案').glob(prefix+'*.md')) for prefix in ('38-','39-','49-','84-')]
B=N/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));B.mkdir();items={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
    for i,p in enumerate(paths):
        member='files/%04d/%s'%(i,p.name);z.write(p,member);items[str(p)]=dict(member=member,sha256=sha(p))
with zipfile.ZipFile(B/'before.zip') as z:
    assert z.testzip() is None
    for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
(B/'manifest.json').write_text(json.dumps(items,indent=2),encoding='utf-8');(N/'latest-backup.txt').write_text(str(B),encoding='utf-8')
for folder in ('engine','rtl'):shutil.copytree(U/folder,R/folder)
for folder in ('constraints','project','tb','reference'):(R/folder).mkdir()
out=Path('D:/FPGA-Project/codex-builds/joint-timing-20261019/evidence');out.mkdir(parents=True)
subprocess=__import__('subprocess');subprocess.run(['powershell','-NoProfile','-Command',"New-Item -ItemType Junction -Path '%s' -Target '%s' -ErrorAction Stop | Out-Null"%(R/'evidence',out)],check=True)
for name in ('common.py',):shutil.copyfile(U/name,R/name)
for name in ('sdram_board.cst','sdram_board.sdc'):shutil.copyfile(T/'constraints'/name,R/'constraints'/name)
shutil.copyfile(T/'reference/stress.sdc',R/'reference/stress.sdc')
shutil.copyfile(T/'rtl/sdram_board_top.v',R/'reference/clock-wrapper.v')
(R/'upstream.json').write_text(json.dumps(dict(root=str(U),delivery_sha256=sha(U/'delivery.json'),files=u['files'],board_root=str(T),board_delivery_sha256=sha(T/'delivery.json'),board_files=t['files']),indent=2),encoding='utf-8')
print('PASS isolated copy; ZIP verified',len(items),'inputs')
