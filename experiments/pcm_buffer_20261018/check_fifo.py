from common import *
import random,collections
def stimulus(aw):
 depth=1<<aw;r=random.Random(7900+aw)
 rows=[(0,0,1,1,999),(1,1,1,1,888)]
 rows += [(1,0,1,0,n&65535) for n in range(depth+8)]
 rows += [(1,0,1,1,n^1234) for n in range(depth+8)]
 rows += [(1,0,0,1,0)]*(depth+8)
 for n in range(50000):rows.append((int(n%4001!=0),int(n%1973==0),r.randrange(2),r.randrange(2),r.randrange(65536)))
 return rows
def verify(rows,trace,aw):
 q=collections.deque();capacity=1<<aw;wait=0;stalled=None;stats=dict(push=0,pop=0,full=0,empty=0,simultaneous=0,reset_clear=0)
 lines=trace.read_text().splitlines();assert len(lines)==len(rows)
 for n,(stim,line) in enumerate(zip(rows,lines)):
  rst,clear,iv,ready,data=stim;i,ir,ov,od,level=line.split();ir=int(ir);ov=int(ov);level=int(level);assert int(i)==n
  if not rst or clear:
   assert ir==ov==level==0,(n,'reset/clear');q.clear();wait=0;stalled=None;stats['reset_clear']+=1;continue
  if stalled is not None:assert ov and int(od,16)==stalled,(n,'stalled head changed')
  if ov:assert q and int(od,16)==q[0],(n,'ordering',od,list(q)[:4])
  if q and not ov:wait+=1;assert wait<=1,(n,'prefetch starved')
  else:wait=0
  pop=bool(ov and ready);assert ir==int(len(q)<capacity or pop),(n,'capacity ready',len(q),ir)
  stats['full']+=len(q)==capacity;stats['empty']+=len(q)==0
  stalled=int(od,16) if ov and not ready else None
  if pop:q.popleft();stats['pop']+=1
  if iv and ir:q.append(data);stats['push']+=1
  stats['simultaneous']+=bool(pop and iv and ir)
  assert level==len(q) and len(q)<=capacity,(n,'occupancy',level,len(q))
 assert stats['full']>0 and stats['simultaneous']>0 and stats['reset_clear']>10
 return stats
results={};rtl=R/'rtl/pcm_sync_fifo.v'
for aw in (1,3,10):
 rows=stimulus(aw);inp=E/('fifo-%d.in'%aw);trace=E/('fifo-%d.tsv'%aw);exe=E/('fifo-%d.vvp'%aw)
 inp.write_text(''.join(' '.join(map(str,row))+'\n' for row in rows))
 run([IV,'-g2012','-s','tb_fifo','-Ptb_fifo.AW=%d'%aw,'-o',str(exe),str(rtl),str(R/'tb_fifo.v')],'compile-fifo-%d'%aw)
 run([VVP,str(exe),'+input='+str(inp),'+output='+str(trace)],'run-fifo-%d'%aw)
 results[str(aw)]=dict(cycles=len(rows),coverage=verify(rows,trace,aw),stimulus_sha256=sha(inp),trace_sha256=sha(trace))
fault=E/'fifo_bad_pointer.v';fault.write_text(rtl.read_text().replace('rp<=rp+1\'b1','rp<=rp+2\'d2'))
run([IV,'-g2012','-s','tb_fifo','-Ptb_fifo.AW=3','-o',str(E/'fault.vvp'),str(fault),str(R/'tb_fifo.v')],'compile-fault')
run([VVP,str(E/'fault.vvp'),'+input='+str(E/'fifo-3.in'),'+output='+str(E/'fault.tsv')],'run-fault')
try:verify(stimulus(3),E/'fault.tsv',3)
except (AssertionError,ValueError) as err:reason=str(err)
else:raise AssertionError('wrong read pointer escaped reference')
(E/'fifo-reference.json').write_text(json.dumps(dict(status='PASS independent deque reference and deliberate pointer fault',results=results,fault_detected=reason,inputs={p.relative_to(R).as_posix():sha(p) for p in [rtl,R/'tb_fifo.v',Path(__file__).resolve(),R/'common.py']}),indent=2))
print('PASS FIFO reference',json.dumps(results),'fault:',reason)
