from pathlib import Path
import hashlib,json,zipfile,datetime,shutil
P=Path(__file__).resolve().parents[2];N=Path(__file__).resolve().parent
U=P/'experiments/sdram_stream_20261018';T=P/'experiments/sdram_timing_20261018';R=P/'experiments/sdram_stream_board_20261018'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
up=json.loads((U/'delivery.json').read_text(encoding='utf-8'));t=json.loads((T/'delivery.json').read_text(encoding='utf-8'))
for root,d in ((U,up),(T,t)):
 for rel,h in d['files'].items():assert sha(root/rel)==h,(str(root),rel)
assert not R.exists()
rel=['pcm_sdram_stream.v','pcm_sdram_arbiter.v','pcm_storage_buffers.v','pcm_sync_fifo.v','sdram_word_controller.v']
paths=[U/'rtl'/n for n in rel]+[U/'delivery.json',T/'delivery.json',T/'rtl/sdram_board_top.v',T/'rtl/uart_tx.v',T/'constraints/sdram_board.cst',T/'constraints/sdram_board.sdc',T/'reference/stress.sdc',T/'build_board.py',P/'experiments/envelope_resources_20261017/package/config-sram.fs',P/'experiments/envelope_resources_20261017/package/manifest.json']
paths +=[next((P/'docs/02-技术方案').glob(k+'*.md')) for k in ('38-','39-','49-','82-')]
B=N/('backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'));B.mkdir(parents=True);items={}
with zipfile.ZipFile(B/'before.zip','w',zipfile.ZIP_DEFLATED) as z:
 for i,p in enumerate(paths):
  member='files/%04d/%s'%(i,p.name);z.write(p,member);items[str(p)]=dict(member=member,sha256=sha(p))
with zipfile.ZipFile(B/'before.zip') as z:
 assert z.testzip() is None
 for v in items.values():assert hashlib.sha256(z.read(v['member'])).hexdigest()==v['sha256']
(B/'manifest.json').write_text(json.dumps(items,indent=2));(N/'latest-backup.txt').write_text(str(B))
for name in ('rtl','tb','constraints','reference','evidence','project'):(R/name).mkdir(parents=True)
for name in rel:shutil.copyfile(U/'rtl'/name,R/'rtl'/name)
for src,dst in [('rtl/uart_tx.v','rtl/uart_tx.v'),('constraints/sdram_board.cst','constraints/sdram_board.cst'),('constraints/sdram_board.sdc','constraints/sdram_board.sdc'),('reference/stress.sdc','reference/stress.sdc'),('tb/sdram_timing_model.v','tb/sdram_timing_model.v'),('common.py','common.py'),('build_board.py','build_board.py')]:shutil.copyfile(T/src,R/dst)
(R/'upstream.json').write_text(json.dumps(dict(stream_root=str(U),stream_delivery_sha256=sha(U/'delivery.json'),stream_files=up['files'],timing_root=str(T),timing_delivery_sha256=sha(T/'delivery.json'),timing_files=t['files']),indent=2))
print('PASS backup',len(paths),'items, isolated stage83; stage82 transport RTL frozen')
