from common import *
import collections
files=sources()+[R/'tb/vendor_ram16sdp4.v']+[R/'tb_envelope.v']
run([IV,'-g2012','-DTIMING_RTL_SIM','-I',str(R/'engine/src'),'-s','tb_envelope','-o',str(E/'envelope.vvp'),*map(str,files)],'compile-envelope')
trace=E/'envelope.tsv';run([VVP,str(E/'envelope.vvp'),'+trace='+trace.as_posix()],'run-envelope',R/'engine/src')
DEFAULT=(22938<<7)|(3<<5)|12
active=[dict(level=0,stage=0,gate=0,previous=0,meta=DEFAULT) for _ in range(32)]
pending=[dict(valid=0,parity=0,gate=0,meta=DEFAULT) for _ in range(32)]
pipe=None;phase=0;parity=0;states=collections.Counter();consumes=0;releases=0;rows=0
def step(level,stage,on,off,attack,dm,dk,sustain,rm,rk):
    if on:return level,1
    if stage==0:return 0,0
    if stage==1:
        if off:return level,4
        if level+attack>=32768:return 32768,2
        return level+attack,1
    if stage==2:
        if off:return level,4
        if level<=sustain:return sustain,3
        dec=max(1,((level*dm)>>dk)&65535)
        if level<=sustain+dec:return sustain,3
        return level-dec,2
    if stage==3:return sustain,(4 if off else 3)
    if stage==4:
        dec=max(1,((level*rm)>>rk)&65535)
        if level<=100+dec:return 0,0
        return level-dec,4
    return level,0
for line in trace.read_text(encoding='utf-8').splitlines():
    cols=line.split();cycle,sc=int(cols[0]),int(cols[1]);assert sc==cycle%32
    load=int(cols[16]);slot=int(cols[17]);gate=int(cols[18]);ext=int(cols[19],16);tag=int(cols[20],16);epar=int(cols[21],16)
    # Read-before-write: stage-one snapshots are from the prior clock's RAM reads.
    next_pipe=( (sc+4)%32,dict(active[(sc+4)%32]),dict(pending[(sc+4)%32]),phase,parity)
    if pipe is not None:
        sl,a,p,ph,pp=pipe
        observed=[int(v,16) if j in (7,11) else int(v) for j,v in enumerate(cols) if 2<=j<=15]
        sl1,level,stage,gc,gq,meta,pv,pt,pg,pe,pr,ppr,out_level,out_stage=observed
        assert (sl1,level,stage,gc,gq,meta,pv,pt,pg,pe,pr,ppr)==(sl,a['level'],a['stage'],a['gate'],a['previous'],a['meta'],p['valid'],p['parity'],p['gate'],p['meta'],ph,pp),(cycle,'RAM/pipeline mismatch')
        consume=p['valid'] and p['parity']!=pp;release_only=consume and a['gate'] and not p['gate'];replace=consume and not release_only
        effective=p['meta'] if replace else a['meta'];new_gate=p['gate'] if consume else a['gate'];profile=effective>>31
        on=(new_gate and not a['previous']) or (consume and p['gate'] and ((p['meta']>>23)&255)!=((a['meta']>>23)&255));off=not new_gate and a['previous']
        custom=bool(profile&(1<<35));attack=((profile>>15)&65535) if custom else 117;rm=((profile>>5)&3) if custom else 3;rk=(profile&31) if custom else 13
        shift=(((profile>>31)&15) if stage==1 else ((profile>>11)&15) if stage==2 else ((profile>>7)&15) if stage==4 else 0) if custom else 0
        expected=step(a['level'],stage,on,off,attack,(effective>>5)&3,effective&31,(effective>>7)&65535,rm,rk)
        if custom and ph% (1<<shift)!=0 and not on and not off:expected=(a['level'],stage)
        assert (out_level,out_stage)==expected,(cycle,sl,'envelope mismatch',(out_level,out_stage),expected)
        active[sl]=dict(level=expected[0],stage=expected[1],gate=new_gate,previous=new_gate,meta=effective)
        states[expected[1]]+=1
        if consume:pending[sl]['valid']=0;consumes+=1
        if release_only:releases+=1
    if load:pending[slot]=dict(valid=1,parity=parity,gate=gate,meta=(ext<<31)|(tag<<23)|epar)
    if sc==31:phase=(phase+1)&32767;parity^=1
    pipe=next_pipe;rows+=1
assert rows==50000 and len(states)==5 and releases>100 and consumes>1000,(rows,states,releases,consumes)
data=dict(status='PASS independent RAM/pending/envelope reference',cycles=rows,checked_updates=rows-1,states=dict(states),consumes=consumes,release_metadata_retention=releases,trace_sha256=sha(trace),inputs={p.relative_to(R).as_posix():sha(p) for p in files+list((R/'engine/src').glob('*.hex'))+[Path(__file__).resolve(),R/'common.py']})
(E/'envelope-reference.json').write_text(json.dumps(data,indent=2),encoding='utf-8');print('PASS independent envelope reference',rows,dict(states),consumes,releases)
