"""Independent integer reference for raw-frame calibration and strip positions."""
from pathlib import Path
import random,json,hashlib
R=Path(__file__).resolve().parent
rng=random.Random(0x20261016)
N=4;LANES=2;FRAMES=160
base=[None]*32;active=[False]*N;confirm=[0]*N;position=[0]*N
rows=[];meta=[];expected=[]
for frame in range(FRAMES):
    cal=frame in (1,75)
    raw=[100+n for n in range(32)];bad=[False]*32
    if frame>=2:
        for s in range(N):
            if frame<10:
                ds=([100,0,0] if frame<4 else [0,100,0] if frame<6 else [0,0,100] if frame<8 else [3900]*3)
            elif frame<16:ds=[0,0,0]
            else:ds=[rng.randrange(0,3970) for _ in range(3)] if rng.random()<.8 else [0,0,0]
            for k,d in enumerate(ds):
                n=3*s+k;raw[n]+=d
                if frame>=16 and rng.random()<.04:bad[n]=True
    valid=[];deltas=[]
    for n in range(32):
        if cal:base[n]=None if bad[n] else raw[n]
        valid.append(base[n] is not None and not bad[n])
        deltas.append(0 if base[n] is None else max(0,raw[n]-base[n]))
    invalid=0
    for s in range(N):
        ds=deltas[3*s:3*s+3];good=all(valid[3*s:3*s+3]);total=sum(ds)
        if not good:invalid|=1<<s
        if cal:active[s]=False;confirm[s]=0
        elif not good:confirm[s]=0
        else:
            wanted=total>=(30 if active[s] else 60)
            if wanted==active[s]:confirm[s]=0
            else:
                confirm[s]+=1
                if confirm[s]>=2:active[s]=wanted;confirm[s]=0
            if total:position[s]=(ds[1]+2*ds[2])*128//total
    packed=sum(p<<(9*s) for s,p in enumerate(position))
    packed|=sum(int(a)<<s for s,a in enumerate(active))<<36
    packed|=invalid<<40
    packed|=int(cal)<<44
    expected.append('%012x'%packed);meta.append('%x'%int(cal))
    for addr in range(16):
        n=addr*2
        word=raw[n]|raw[n+1]<<12|int(bad[n])<<24|int(bad[n+1])<<25
        rows.append('%08x'%word)
for name,lines in [('row_vectors.hex',rows),('meta_vectors.hex',meta),('expected_vectors.hex',expected)]:
    (R/name).write_text('\n'.join(lines)+'\n',encoding='ascii')
record=dict(frames=FRAMES,seed='0x20261016',strips=N,lanes=LANES,threshold_on=60,threshold_off=30,confirm_frames=2,generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),vectors={name:hashlib.sha256((R/name).read_bytes()).hexdigest() for name in ['row_vectors.hex','meta_vectors.hex','expected_vectors.hex']})
(R/'vector-reference.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print('Generated %d independent calibration/centroid frames'%FRAMES)
