"""Low-level volatile slot format v0; NOT the GUI instrument.json schema.

No serial sender or persistent writer is provided. All fields are integer DSP
units. Attack/release/effects remain global and are intentionally not encoded.
"""
from pathlib import Path
import json,argparse
FIELDS={'ratio_q8','amplitude','sustain_q15','decay_m','decay_k'}
def integer(value,lo,hi,name):
    if type(value) is not int or not lo<=value<=hi:raise ValueError(name+' out of range')
    return value
def encode(partials):
    if not isinstance(partials,list) or len(partials)!=16:raise ValueError('exactly 16 partials required')
    result=[]
    for p in partials:
        if type(p) is not dict or set(p)!=FIELDS:raise ValueError('unknown/missing partial fields')
        ratio=integer(p['ratio_q8'],1,65535,'ratio_q8')
        amp=integer(p['amplitude'],0,255,'amplitude')
        sustain=integer(p['sustain_q15'],0,32768,'sustain_q15')
        m=integer(p['decay_m'],1,3,'decay_m');k=integer(p['decay_k'],0,31,'decay_k')
        result.append((ratio<<32)|(amp<<24)|(sustain<<7)|(m<<5)|k)
    return result
def decode(words):
    if not isinstance(words,list) or len(words)!=16:raise ValueError('exactly 16 words required')
    parts=[]
    for word in words:
        integer(word,0,(1<<48)-1,'word')
        if word&(1<<23):raise ValueError('reserved bit')
        parts.append(dict(ratio_q8=word>>32,amplitude=(word>>24)&255,sustain_q15=(word>>7)&65535,decay_m=(word>>5)&3,decay_k=word&31))
    encode(parts)
    return parts
def example(sustain):
    return [dict(ratio_q8=(k+1)*256,amplitude=(180 if sustain else 90) if k==0 else 3*k,sustain_q15=sustain,decay_m=3,decay_k=0) for k in range(16)]
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();words=encode(json.loads(args.input.read_text(encoding='utf-8')))
    args.output.write_text(''.join('%012x\n'%w for w in words),encoding='ascii')
