from common import *
from collections import deque,Counter
import shutil
files=[R/'rtl/pcm_sdram_arbiter.v',R/'tb/memory_backend_model.v',R/'tb/tb_arbiter.v']
inputs={p.relative_to(R).as_posix():sha(p) for p in files+[Path(__file__).resolve(),R/'common.py']}

def case(label,aw,seed,rtl=None,negative=False):
 D=E/label;D.mkdir(exist_ok=True)
 cmd=[IV,'-g2012','-s','tb_arbiter','-Ptb_arbiter.AW='+str(aw),'-Ptb_arbiter.SEED='+str(seed),'-o',str(D/'test.vvp'),str(rtl or files[0]),*map(str,files[1:])]
 run(cmd,label+'-compile');out=subprocess.run([VVP,str(D/'test.vvp')],cwd=D,capture_output=True,text=True,timeout=180)
 (D/'run.log').write_text(out.stdout+out.stderr,encoding='utf-8')
 if out.returncode:raise AssertionError(out.stdout+out.stderr)
 queues=[deque(),deque()];clears=[0,0];pending_clear=[False,False];events=Counter();kinds=Counter();prev_cmd=None
 pending_kind=None;decision=None;waits=[0]*4;max_wait=[0]*4;clear_at=[None,None];max_clear=0
 for line in (D/'trace-arbiter.txt').read_text().splitlines():
  words=line.split();assert len(words)==32
  if words[1]=='0':
   for q in queues:q.clear()
   pending_kind=None;pending_clear=[False,False];prev_cmd=None;decision=None;waits=[0]*4;clear_at=[None,None];continue
  v=list(map(int,words))
  c,rst,rc,pc,rcd,pcd,rcb,pcb,ri,rd,ro,rod,pi,pd,po,pod,mv,mr,mw,ma,md,sv,sr,rl,pl,rov,rr,pov,pr,busy,riv,piv=v
  if not rst:
   for q in queues:q.clear()
   pending_kind=None;pending_clear=[False,False];prev_cmd=None;continue
  for j,fire in enumerate((rc,pc)):
   if fire:
    queues[j].clear();clears[j]+=1;pending_clear[j]=True;clear_at[j]=c
    events[('rec' if j==0 else 'play')+'_clear_'+('issue' if mv else 'wait' if busy else 'idle')]+=1
    if pending_kind is not None:events['clear_with_pending_memory']+=1
  for j,done in enumerate((rcd,pcd)):
   if done:
    assert pending_clear[j],(c,'unexpected clear done')
    assert pending_kind is None or pending_kind//2!=j,(c,'early clear before memory drain')
    max_clear=max(max_clear,c-clear_at[j]);assert c-clear_at[j]<=256,(c,'clear exceeded bounded backend')
    pending_clear[j]=False;events['clear_done']+=1
  if ri:queues[0].append(rd);events['record_in']+=1
  if pi:queues[1].append(pd);events['play_in']+=1
  for j,pop,value in ((0,ro,rod),(1,po,pod)):
   if pop:
    assert queues[j] and queues[j].popleft()==value,(label,c,j,'stream data/order mismatch',value)
    events['record_out' if j==0 else 'play_out']+=1
  if mv and mr:
   assert pending_kind is None,(c,'overlapping memory requests')
   pending_kind=(2 if ma>=1<<aw else 0)+(0 if mw else 1);kinds[pending_kind]+=1
   assert decision and decision[pending_kind],(c,'selected ineligible client')
   for j in range(4):
    waits[j]=waits[j]+1 if decision[j] and j!=pending_kind else 0
    max_wait[j]=max(max_wait[j],waits[j]);assert waits[j]<=3,(c,'round robin starvation',j)
   decision=None
   assert ma<2<<aw
  if sv and sr:
   assert pending_kind is not None,(c,'unsolicited response')
   pending_kind=None;events['memory_responses']+=1
  assert rl<=1<<aw and pl<=1<<aw
  if rcb:assert not ri and not ro
  if pcb:assert not pi and not po
  if not busy:
   available=[riv and rl<1<<aw and not rcb,rl!=0 and not rov and not rcb,
              piv and pl<1<<aw and not pcb,pl!=0 and not pov and not pcb]
   if any(available):
    assert decision is None,(c,'overlapping scheduling decisions');decision=available
 assert not any(queues) and not any(pending_clear) and pending_kind is None
 assert all(kinds[i]>500 for i in range(4)),kinds
 assert min(clears)>100 and events['clear_with_pending_memory']>100
 assert events['rec_clear_issue'] and events['rec_clear_wait'] and events['play_clear_issue'] and events['play_clear_wait']
 result=dict(aw=aw,seed=seed,cycles=c,clears=clears,events=dict(events),memory_clients=dict(kinds),max_other_grants_before_service=max_wait,max_clear_cycles=max_clear,log=out.stdout)
 print(json.dumps({k:v for k,v in result.items() if k!='log'}));return result

results=[case('arbiter-a%d-s%d'%(aw,seed),aw,seed) for aw,seed in ((1,19),(3,71),(5,991),(17,331))]
text=files[0].read_text();faults={
 'wrong-play-region':('22\'d1<<AW | play_wp','22\'d0<<AW | play_wp'),
 'early-clear':('state==IDLE || !is_rec','1\'b1'),
 'head-overwrite':('rec_level!=0 && !rec_head_valid','rec_level!=0')}
detected={}
for label,(old,new) in faults.items():
 assert text.count(old)==1
 p=E/(label+'.v');p.write_text(text.replace(old,new),encoding='utf-8')
 try:case('negative-'+label,3,71,p,True)
 except AssertionError as exc:detected[label]=str(exc)[:1800]
 else:raise AssertionError('fault escaped: '+label)
assert all(sha(R/rel)==h for rel,h in inputs.items())
(E/'arbiter.json').write_text(json.dumps(dict(status='PASS independent two-deque stream scoreboard, stalls, clear drain and three deliberate faults',results=results,detected_faults=detected,inputs=inputs,hardware_tested=False),indent=2),encoding='utf-8')
print('PASS independent arbiter scoreboard and three faults')
