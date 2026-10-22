"""Preserve and audit the four unsuccessful physical revisions; no hardware."""
from common import *
P=R.parents[1];N=P/'notes/sdram-stream-board-20261018';read=lambda p:json.loads(p.read_text(encoding='utf-8'))
rows=[];inputs={}
for S in sorted(N.glob('hardware-*')):
 d=read(S/'result.json')
 if not d['status'].startswith('FAIL'):continue
 assert sha(S/'bench_hardware_attempt.py')==d['script_sha256']
 assert sha(S/'timing-audit-attempt.json')==d['audit_sha256']
 a=read(S/'timing-audit-attempt.json');D=R/d['selected_build']
 assert sha(D/'impl/pnr/board.fs')==d['test_bitstream_sha256']==a['selected']['stress']['bitstream_sha256']
 assert sha(D/'sdram_board_top.v')==a['inputs']['rtl/sdram_board_top.v']
 frames=read(S/'stream1.json');f=frames[-1]
 assert f['state']==19 and f['error_code'] in (11,12)
 assert f['prefix_count']==132097 and f['clear_count']==6 and f['after_stop']==8193
 assert d['restored']['zero_pcm_samples']==2048 and (S/'restored-silence-s24le.bin').read_bytes()==bytes(6144)
 assert d['restored']['identity']['C2']==0x76 and not d['flash_read_or_written']
 rows.append(dict(directory=S.relative_to(P).as_posix(),build=d['selected_build'],result='FAIL retained; never counted as acceptance',error_code=f['error_code'],reported_prefix=f['prefix_count'],restored=True))
 for p in S.iterdir():
  if p.is_file():inputs[p.relative_to(P).as_posix()]=sha(p)
assert len(rows)==4
inputs[Path(__file__).resolve().relative_to(P).as_posix()]=sha(Path(__file__))
(E/'history-audit.json').write_text(json.dumps(dict(status='PASS preservation/identity audit of four failed physical revisions; not a product PASS',failed_attempts=rows,input_root=str(P),inputs=inputs),indent=2))
print('PASS four failed physical sessions retained; each verified stage76 restore')
