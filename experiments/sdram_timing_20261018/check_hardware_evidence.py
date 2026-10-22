"""Offline checks of recorded physical frames/program logs; never opens COM/JTAG."""
from common import *
import functools,operator
P=R.parents[1];N=P/'notes/sdram-timing-20261018'
S=Path((N/'latest-hardware.txt').read_text(encoding='utf-8'))
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
d=read(S/'result.json');a=read(E/'timing-audit.json')
assert d['status']=='PASS two bounded SDRAM sweeps and restored stage76 identity/silence'
assert sha(S/'bench_hardware_attempt.py')==d['script_sha256']==sha(N/'bench_hardware.py')
assert sha(E/'timing-audit.json')==d['audit_sha256']
assert sha(R/'build_pll32_nominal/impl/pnr/board.fs')==d['test_bitstream_sha256']==a['selected']['nominal']['bitstream_sha256']
assert not any(d[k] for k in ('flash_read_or_written','tf_accessed','audio_played'))
assert len(d['runs'])==2
inputs={}
for n,run in enumerate(d['runs'],1):
 raw=(S/('sweep%d.bin'%n)).read_bytes();frames=read(S/('sweep%d.json'%n));parsed=[]
 assert sha(S/('sweep%d.bin'%n))==run['raw_sha256']
 assert sha(S/('sweep%d.json'%n))==run['frames_sha256']
 for i in range(len(raw)-15):
  b=raw[i:i+16]
  if b[:3]!=b'\xa5\x81\x01' or functools.reduce(operator.xor,b)!=0:continue
  parsed.append(b)
 assert len(parsed)==len(frames)==run['frames'] and len(parsed)>=2
 for b,f in zip(parsed,frames):
  assert b.hex()==f['hex']
  assert not b[3]&2 and f['initialized'] and f['completed']<=1<<24
  assert (b[3]>>3)&7==f['state'] and bool(b[3]&1)==f['passed']
  assert int.from_bytes(b[12:15],'little')|(((b[4]>>1)&1)<<24)==f['completed']
  if f['state'] in (3,4):assert f['observed']==f['expected']
 assert all(y['completed']>=x['completed'] for x,y in zip(frames,frames[1:]))
 assert len({f['completed'] for f in frames})>1
 f=frames[-1];assert f==run['final'] and f['state']==5 and f['phase']==1 and f['passed']
 assert f['completed']==1<<24 and f['index']==(1<<22)-1 and f['observed']==f['expected']==0xa565
 for k in ('address_halfwords','write_halfwords','read_halfwords'):
  assert run[k]==(1<<22 if k=='address_halfwords' else 1<<23)

for label in ('sweep1-sram','sweep2-sram','restore-stage76'):
 item=read(S/(label+'-attempt.json'));args=item['command']
 assert item['operation']==2 and item['mode']=='SRAM only'
 assert args[1:]==['--device','GW2AR-18C','--operation_index','2','--chain_size','1','--chain_index','0','--channel','0','--fsFile',item['image']]
 assert sha(Path(item['image']))==item['sha256']
 expected=d['restore_bitstream_sha256'] if label=='restore-stage76' else d['test_bitstream_sha256']
 assert item['sha256']==expected
 log=(S/(label+'.log')).read_text(encoding='utf-8')
 assert all(s in log for s in ('GW2AR-18C(0x0000081B)','Operation "SRAM Program" for device#1','100%','Status Code is: 0x00006020','Finished.'))
 assert 'failed' not in log.lower() and 'error' not in log.lower()
assert d['restored']['identity']=={'C0':0x72,'C2':0x76,'C3':1,'D0':0x75,'D1':1,'A4':0xD3,'A9':32}
assert d['restored']['snapshot']['active']==d['restored']['snapshot']['fingers']==0
assert d['restored']['snapshot']['period_min']==d['restored']['snapshot']['period_max']==512
assert d['restored']['zero_pcm_samples']==2048
assert (S/'restored-silence-s24le.bin').read_bytes()==bytes(2048*3)
for p in S.iterdir():
 if p.is_file():inputs[p.relative_to(P).as_posix()]=sha(p)
for p in (Path(__file__).resolve(),R/'common.py',E/'timing-audit.json',N/'bench_hardware.py'):
 inputs[p.relative_to(P).as_posix()]=sha(p)
record=dict(status='PASS offline audit of two physical SDRAM sweeps and restored stage76',
 hardware_directory=S.relative_to(P).as_posix(),hardware_tested=True,production_qualified=False,
 runs=2,total_halfword_operations=1<<25,bytes_transferred=1<<26,zero_pcm_samples=2048,
 input_root=str(P),inputs=inputs,
 limitations=['one board and current ambient/supply only','two complementary XOR-address patterns, not exhaustive alias/March/retention tests',
 'no analog edge/timing measurements','readback receives 1Hz snapshots, not each transaction','no physical S2 test or power-cycle test in this stage'])
(E/'hardware-audit.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({k:record[k] for k in ('status','runs','total_halfword_operations','bytes_transferred','production_qualified')}))
