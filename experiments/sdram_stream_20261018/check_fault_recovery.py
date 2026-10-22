from common import *
from collections import deque,Counter
files=[R/'rtl'/n for n in ('pcm_sdram_stream.v','pcm_sdram_arbiter.v','pcm_storage_buffers.v','pcm_sync_fifo.v')]+[R/'tb/memory_backend_model.v',R/'tb/tb_fault_recovery.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']}
D=E/'fault-recovery';D.mkdir(exist_ok=True)
run([IV,'-g2012','-s','tb_fault_recovery','-o',str(D/'test.vvp'),*map(str,files)],'fault-recovery-compile')
out=subprocess.run([VVP,str(D/'test.vvp')],cwd=D,capture_output=True,text=True,timeout=60)
(D/'run.log').write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,out.stdout+out.stderr
rec=deque();play=deque();events=Counter();previous_over=0;record_before_clear=[];last_capture_cycle=None
for line in (D/'trace-fault.txt').read_text().splitlines():
 words=line.split()
 if words[1]=='0':continue
 c,rst,rc,pc,rcd,pcd,rcb,pcb,re,tick,pcm,ro,rd,fi,data,pv,pd,miss,over,under=map(int,words)
 if rc:rec.clear();events['rec_clear']+=1
 if pc:play.clear();events['play_clear']+=1
 if over and not previous_over:
  assert rec and last_capture_cycle==c-1,'overflow must reject the preceding candidate sample'
  rec.pop();events['overflow_latched']+=1
 if re and tick and not rcb and not over:rec.append(pcm);last_capture_cycle=c
 if fi:play.append(data);events['feed']+=1
 if ro:
  assert rec and rec.popleft()==rd,(c,'record prefix/order',rd)
  events['record']+=1
  if c<6000:record_before_clear.append(rd)
  else:events['record_after_recovery']+=1
 if pv:
  assert play and play.popleft()==pd,(c,'play generation/order',pd)
  events['played']+=1
 if miss:assert under and not pv;events['misses']+=1
 if rcd:events['rec_done']+=1
 if pcd:events['play_done']+=1
 previous_over=over
assert not rec and not play
assert events['overflow_latched']==1 and events['rec_clear']==events['rec_done']==1
assert events['play_clear']==events['play_done']==2 and events['feed']==events['played']==32
assert events['record_after_recovery']>60 and events['misses']>50
assert 12<=len(record_before_clear)<=14 and all(y==x+1 for x,y in zip(record_before_clear,record_before_clear[1:]))
assert all(sha(R/rel)==h for rel,h in inputs.items())
record=dict(status='PASS expected overflow contiguous-prefix drain, explicit underrun misses and clear recovery',events=dict(events),recorded_prefix_samples=len(record_before_clear),log=out.stdout,inputs=inputs,hardware_tested=False)
(E/'fault-recovery.json').write_text(json.dumps(record,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in record.items() if k not in ('inputs','log')}))
