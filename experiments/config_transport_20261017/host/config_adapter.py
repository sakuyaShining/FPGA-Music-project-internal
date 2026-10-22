"""Compile schema-1 drafts to volatile slot v1 words. No UART/Flash writes.

Supported: preset ratios, add/replace spectrum, sustain/strike/hybrid and ADSR.
Vibrato/effects must be disabled until independent layer routing is implemented.
Timing is quantized; reported phase jitter and full-level release are explicit.
"""
from pathlib import Path
import argparse,functools,json,math
from instrument_config import validate_config,load_config
FS=27000000/512
FIELDS={'ratio_q8','amplitude','sustain_q15','decay_m','decay_k','decay_shift','attack_inc','attack_shift','release_m','release_k','release_shift'}
def integer(v,lo,hi,name):
    if type(v) is not int or not lo<=v<=hi:raise ValueError(name+' out of range')
    return v
def encode(parts):
    if type(parts) is not list or len(parts)!=16:raise ValueError('exactly 16 partials')
    words=[]
    for p in parts:
        if type(p) is not dict or set(p)!=FIELDS:raise ValueError('unknown/missing partial field')
        limits={'ratio_q8':(1,65535),'amplitude':(0,255),'sustain_q15':(0,32768),'decay_m':(1,3),'decay_k':(0,31),'decay_shift':(0,15),'attack_inc':(1,32768),'attack_shift':(0,15),'release_m':(1,3),'release_k':(0,31),'release_shift':(0,15)}
        for k,(lo,hi) in limits.items():integer(p[k],lo,hi,k)
        env=(1<<35)|(p['attack_shift']<<31)|(p['attack_inc']<<15)|(p['decay_shift']<<11)|(p['release_shift']<<7)|(p['release_m']<<5)|p['release_k']
        base=(p['ratio_q8']<<32)|(p['amplitude']<<24)|(p['sustain_q15']<<7)|(p['decay_m']<<5)|p['decay_k']
        words.append((env<<48)|base)
    return words
def decode(words):
    if type(words) is not list or len(words)!=16:raise ValueError('exactly 16 words')
    parts=[]
    for w in words:
        integer(w,0,(1<<88)-1,'word')
        if w>>84 or not w&(1<<83) or w&(1<<23):raise ValueError('reserved/format bits')
        e=w>>48
        parts.append(dict(ratio_q8=(w>>32)&65535,amplitude=(w>>24)&255,sustain_q15=(w>>7)&65535,decay_m=(w>>5)&3,decay_k=w&31,decay_shift=(e>>11)&15,attack_inc=(e>>15)&65535,attack_shift=(e>>31)&15,release_m=(e>>5)&3,release_k=e&31,release_shift=(e>>7)&15))
    assert encode(parts)==words
    return parts
@functools.lru_cache(maxsize=None)
def exp_steps(floor,m,k):
    level=32768;n=0
    while level>floor:
        step=max(1,((level*m)>>k)&65535)
        level=floor if level<=floor+step else level-step;n+=1
        if n>32768:raise ValueError('invalid decay coefficient')
    return max(1,n)
def fit_exp(ms,floor):
    target=round(FS*ms/1000);best=None
    for m in (1,2,3):
        for k in range(22):
            if k==0 and m!=1:continue
            steps=exp_steps(floor,m,k)
            for shift in range(16):
                duration=steps*(1<<shift);candidate=(abs(duration-target),shift,k,m,steps)
                if best is None or candidate<best:best=candidate
    error,shift,k,m,steps=best
    return dict(m=m,k=k,shift=shift,nominal_ms=steps*(1<<shift)*1000/FS,phase_jitter_bound_ms=((1<<shift)-1)*1000/FS,requested_ms=ms)
def fit_attack(ms):
    target=round(FS*ms/1000);best=None
    for shift in range(16):
        ideal=32768*(1<<shift)/max(1,target)
        for inc in {max(1,min(32768,int(ideal)+delta)) for delta in (-2,-1,0,1,2)}:
            steps=(32768+inc-1)//inc;duration=steps*(1<<shift);candidate=(abs(duration-target),shift,inc,steps)
            if best is None or candidate<best:best=candidate
    error,shift,inc,steps=best
    return dict(inc=inc,shift=shift,nominal_ms=steps*(1<<shift)*1000/FS,phase_jitter_bound_ms=((1<<shift)-1)*1000/FS,requested_ms=ms)
def compile_document(document,preset_words=None):
    doc=validate_config(document)
    unsupported=[]
    if doc['vibrato']['enabled']:unsupported.append('independent vibrato')
    if not doc['effects']['dry_enabled'] or any(doc['effects'][k]['enabled'] for k in ('delay','chorus','reverb')):unsupported.append('independent effects / dry routing')
    if unsupported:raise ValueError('not applied: unsupported '+', '.join(unsupported))
    if preset_words is None:preset_words=[int(w,16) for w in (Path(__file__).resolve().parents[1]/'src/preset_part.hex').read_text(encoding='ascii').split()]
    if len(preset_words)!=64:raise ValueError('preset ROM must contain 64 words')
    art=doc['articulation'];attack=fit_attack(art['attack_ms']);release=fit_exp(art['release_ms'],100);parts=[];timing=[]
    for i in range(16):
        base=preset_words[doc['preset']*16+i];mode=art['hybrid_parts'][i] if art['mode']=='hybrid' else art['mode']
        sustain=0 if mode=='strike' else round(art['sustain_level']*32768/255)
        decay=fit_exp(art['decay_ms'],sustain)
        amp=doc['spectrum'][i] if doc['spectrum_mode']=='replace' else min(255,doc['spectrum'][i]+((base>>24)&255))
        parts.append(dict(ratio_q8=(base>>32)&65535,amplitude=amp,sustain_q15=sustain,decay_m=decay['m'],decay_k=decay['k'],decay_shift=decay['shift'],attack_inc=attack['inc'],attack_shift=attack['shift'],release_m=release['m'],release_k=release['k'],release_shift=release['shift']))
        timing.append(dict(part=i,mode=mode,decay=decay))
    return encode(parts),dict(status='compiled only; not sent or persisted',format='slot-v1/88-bit',sample_rate_nominal=FS,attack=attack,release_from_full_to_cutoff100=release,partials=timing,unsupported_enabled_fields=[],remaining='compiler only; transport is separate; independent vibrato/effects and persistence not implemented')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('output',type=Path);p.add_argument('--report',type=Path);a=p.parse_args()
    words,report=compile_document(load_config(a.input));a.output.write_text(''.join('%022x\n'%w for w in words),encoding='ascii')
    if a.report:a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('compiled 16 words; no device writes')
if __name__=='__main__':main()
