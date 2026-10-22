from common import *
from collections import deque,Counter
files=[R/'rtl'/n for n in ('pcm_sdram_stream.v','pcm_sdram_arbiter.v','pcm_storage_buffers.v','pcm_sync_fifo.v','sdram_word_controller.v')]
files +=[R/'tb'/n for n in ('tb_stream.v','memory_backend_model.v','sdram_timing_model.v')]
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']}
results=[]
for real in (0,1):
 D=E/('stream-real%d'%real);D.mkdir(exist_ok=True)
 run([IV,'-g2012','-s','tb_stream','-Ptb_stream.REAL_MEMORY='+str(real),'-o',str(D/'test.vvp'),*map(str,files)],'stream%d-compile'%real)
 out=subprocess.run([VVP,str(D/'test.vvp')],cwd=D,capture_output=True,text=True,timeout=180)
 (D/'run.log').write_text(out.stdout+out.stderr,encoding='utf-8');assert out.returncode==0,out.stdout+out.stderr
 rec=deque();play=deque();events=Counter();maximum=[0,0,0,0];in_clear=[False,False]
 for line in (D/'trace-stream.txt').read_text().splitlines():
  words=line.split();assert len(words)==29
  if words[1]=='0':rec.clear();play.clear();continue
  c,rst,rc,pc,rcd,pcd,rcb,pcb,re,tick,pcm,ro,rd,fi,data,pv,pd,miss,over,under,mem,mw,ma,rl,pl,rrl,prl,pe,st=map(int,words)
  if rc:rec.clear();events['record_clear']+=1;in_clear[0]=True
  if pc:play.clear();events['play_clear']+=1;in_clear[1]=True
  if rcd:in_clear[0]=False;events['record_clear_done']+=1
  if pcd:in_clear[1]=False;events['play_clear_done']+=1
  if re and tick and not rcb:rec.append(pcm);events['captured']+=1
  if fi:play.append(data);events['host_feed']+=1
  if ro:
   assert rec and rec.popleft()==rd,(real,c,'record sequence',rd)
   events['host_record']+=1
   if c>160000:events['record_after_stop']+=1
  if pv:
   assert play and play.popleft()==pd,(real,c,'play sequence',pd)
   events['played']+=1
  assert not(over or under or miss),(real,c,'unexpected fault')
  assert not(rcb and ro) and not(pcb and fi)
  assert ma<128 if mem else True
  if mem:events['memory_write' if mw else 'memory_read']+=1
  for i,value in enumerate((rl,pl,rrl,prl)):maximum[i]=max(maximum[i],value)
 assert not rec and not play and not any(in_clear)
 assert events['record_clear']==events['record_clear_done']==2
 assert events['play_clear']==events['play_clear_done']==3
 assert events['played']>250 and events['host_record']>200
 assert events['record_after_stop']>10,'stop must drain a nonempty captured backlog'
 # Stop has no implicit clear; no leftover captured record data may disappear.
 result=dict(real_sdram_model=bool(real),events=dict(events),max_fifo_rec_play_ring_rec_play=maximum,log=out.stdout)
 results.append(result);print(json.dumps(result))
text=files[0].read_text();old='assign play_valid=buffered_play_valid && !play_clearing;';assert text.count(old)==1
fault=E/'clear-pulse-leak.v';fault.write_text(text.replace(old,'assign play_valid=buffered_play_valid;'))
D=E/'stream-pulse-leak';D.mkdir(exist_ok=True)
run([IV,'-g2012','-s','tb_stream','-Ptb_stream.REAL_MEMORY=0','-o',str(D/'test.vvp'),str(fault),*map(str,files[1:])],'stream-leak-compile')
out=subprocess.run([VVP,str(D/'test.vvp')],cwd=D,capture_output=True,text=True,timeout=180)
(D/'run.log').write_text(out.stdout+out.stderr,encoding='utf-8')
assert out.returncode!=0 and 'stream output during clear' in out.stdout,out.stdout
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'stream.json').write_text(json.dumps(dict(status='PASS independent PCM queues through both FIFOs/rings and real SDRAM command model; stop, clear and bounded host/bus pauses',results=results,detected_fault=out.stdout,inputs=inputs,hardware_tested=False,final_mixer_connected=False),indent=2),encoding='utf-8')
