"""Offline audit of raw frames and programmer/restore logs. No hardware access."""
from common import *
import functools,operator
P=R.parents[1];N=P/'notes/sdram-stream-board-20261018'
S=Path((N/'latest-hardware.txt').read_text());read=lambda p:json.loads(p.read_text(encoding='utf-8'))
d=read(S/'result.json');a=read(E/'timing-audit.json')
assert d['status']=='PASS two six-case SDRAM stream runs and restored stage76 identity/silence'
assert sha(S/'bench_hardware_attempt.py')==d['script_sha256']==sha(N/'bench_hardware.py')
assert sha(E/'timing-audit.json')==d['audit_sha256']
assert sha(R/a['bench_image'])==d['test_bitstream_sha256']==a['selected']['stress']['bitstream_sha256']
assert not any(d[k] for k in ('flash_read_or_written','tf_accessed','audio_played'))
assert len(d['runs'])==2
for n,run in enumerate(d['runs'],1):
 raw=(S/('stream%d.bin'%n)).read_bytes();frames=read(S/('stream%d.json'%n));parsed=[]
 assert sha(S/('stream%d.bin'%n))==run['raw_sha256'] and sha(S/('stream%d.json'%n))==run['frames_sha256']
 for i in range(len(raw)-63):
  b=raw[i:i+64]
  if b[:3]==b'\xa5\x83\x01' and functools.reduce(operator.xor,b)==0:parsed.append(b)
 assert len(parsed)==len(frames)==run['frames'] and len(frames)>=2
 for b,f in zip(parsed,frames):
  assert b.hex()==f['hex'] and b[3]==f['state'] and b[4]==f['flags'] and b[5]==f['tests']
  assert not b[4]&2 and b[58]==0
  for field,offset in [('cycles',6),('rec_count',10),('rec_read',14),('feed_count',18),('played',22),('after_stop',26),('prefix_count',30),('misses',34),('clear_count',38),('held_cycles',42),('inflight_clears',46),('failure_index',50),('requests',59)]:
   assert int.from_bytes(b[offset:offset+4],'little')==f[field]
 assert all(y['cycles']>=x['cycles'] for x,y in zip(frames,frames[1:]))
 f=frames[-1];assert f==run['final'] and f['state']==18 and f['flags']==0x25 and f['tests']==63
 assert all(f[k]==4096 for k in ('rec_count','rec_read','feed_count','played'))
 assert f['prefix_count']==132097 and f['misses']==8 and f['clear_count']==6
 assert f['held_cycles']==32 and f['inflight_clears']==1 and f['after_stop']>=4096
 assert f['requests']==4*(266240+4096)+2*132097+2
 assert run['bad_checksums']==0
for label in ('sweep1-sram','sweep2-sram','restore-stage76'):
 item=read(S/(label+'-attempt.json'));args=item['command']
 assert item['operation']==2 and item['mode']=='SRAM only'
 assert args[1:]==['--device','GW2AR-18C','--operation_index','2','--chain_size','1','--chain_index','0','--channel','0','--fsFile',item['image']]
 assert sha(Path(item['image']))==item['sha256']
 expected=d['restore_bitstream_sha256'] if label=='restore-stage76' else d['test_bitstream_sha256'];assert item['sha256']==expected
 log=(S/(label+'.log')).read_text(encoding='utf-8')
 assert all(s in log for s in ('GW2AR-18C(0x0000081B)','Operation "SRAM Program" for device#1','100%','Status Code is: 0x00006020','Finished.'))
 assert 'failed' not in log.lower() and 'error' not in log.lower()
assert d['restored']['identity']=={'C0':0x72,'C2':0x76,'C3':1,'D0':0x75,'D1':1,'A4':0xD3,'A9':32}
assert d['restored']['snapshot']['active']==d['restored']['snapshot']['fingers']==0
assert d['restored']['snapshot']['period_min']==d['restored']['snapshot']['period_max']==512
assert d['restored']['zero_pcm_samples']==2048 and (S/'restored-silence-s24le.bin').read_bytes()==bytes(6144)
inputs={p.relative_to(P).as_posix():sha(p) for p in S.iterdir() if p.is_file()}
for p in (Path(__file__).resolve(),R/'common.py',E/'timing-audit.json',N/'bench_hardware.py'):inputs[p.relative_to(P).as_posix()]=sha(p)
record=dict(status='PASS offline raw-frame/log audit of two physical six-case stream runs and stage76 restore',
 hardware_directory=S.relative_to(P).as_posix(),hardware_tested=True,runs=2,input_root=str(P),inputs=inputs,
 limits=['synthetic patterns and current single board/supply/ambient only','not real musical recording or final mixer','no physical S2, power-cycle or analog edge measurements','earlier final-prefix-check failures retained separately'])
(E/'hardware-audit.json').write_text(json.dumps(record,indent=2));print(record['status'])
