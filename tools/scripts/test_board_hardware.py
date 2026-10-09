"""Exercise diagnostic-only bitstream over real UART. Does not program Flash."""
import argparse
import json
import random
import time
from pathlib import Path
import numpy as np
import serial

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'sim_build/board_diag_20261009/hardware'
FS=52734.375

class Board:
    def __init__(self,port):
        self.port=serial.Serial(port,115200,timeout=1,write_timeout=1)
        self.reads=0;self.writes=0
        self.port.reset_input_buffer()
    def write(self,addr,data):
        self.port.write(bytes([addr,data]));self.writes+=1
    def read(self,addr):
        self.write(15,addr)
        frame=self.port.read(2);self.reads+=1
        if len(frame)!=2 or frame[0]!=addr:
            raise RuntimeError('Bad UART read %02x: %s'%(addr,frame.hex()))
        return frame[1]
    def word(self,addr,count=2):
        return sum(self.read(addr+i)<<(8*i) for i in range(count))
    def snapshot(self):
        self.write(0x83,1)
        return dict(ack=self.word(0x83),on=self.word(0x85),off=self.word(0x87),
                    active=self.word(0x89,4),fingers=self.word(0x94,4),
                    last_group=self.read(0x9c),last_note=self.read(0x9d))
    def note(self,n,on=True,vel=12):
        self.write(0x60,n|(0x80 if on else 0));self.write(0x61,vel)
    def capture(self,name,count=1024,fx=False):
        self.write(0x80,3 if fx else 1)
        time.sleep(.055)
        assert self.read(0x80)&3==2,'Capture did not finish'
        assert self.word(0x81)==2048,'Capture length mismatch'
        self.write(15,0xa8)
        previous_timeout=self.port.timeout;self.port.timeout=5
        stream=self.port.read(1+2048*3);self.port.timeout=previous_timeout
        assert len(stream)==6145 and stream[0]==0xa8,('capture stream',len(stream),stream[:8].hex())
        values=[]
        for i in range(count):
            v=int.from_bytes(stream[1+i*3:4+i*3],'little')
            values.append(v-(1<<24) if v&(1<<23) else v)
        x=np.asarray(values,dtype=np.int32)
        np.save(OUT/(name+'.npy'),x)
        return x
    def finger(self,fid,group,pos,cmd):
        self.write(0xb0,fid);self.write(0xb1,group)
        self.write(0xb2,pos&255);self.write(0xb3,(pos>>8)&15);self.write(0xb4,cmd)

def peak(x):
    y=x.astype(float);y-=y.mean()
    mag=np.abs(np.fft.rfft(y*np.hanning(len(y)),n=16384))
    k=np.argmax(mag[2:])+2
    return float(k*FS/16384)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ports',nargs='+',default=['COM6','COM5'])
    args=parser.parse_args();OUT.mkdir(parents=True,exist_ok=True)
    board=None;probes=[]
    for port in args.ports:
        candidate=None
        try:
            candidate=Board(port)
            identity=candidate.read(0xa4)
            if identity!=0xd2:raise RuntimeError('Not diagnostic device: %02x'%identity)
            board=candidate;probes.append(dict(port=port,identity=identity,connected=True));break
        except Exception as error:
            probes.append(dict(port=port,error=str(error)))
            if candidate:candidate.port.close()
    if board is None:
        (OUT/'report.json').write_text(json.dumps(dict(probes=probes,status='NO_DEVICE'),indent=2),encoding='utf-8')
        raise SystemExit('No diagnostic UART device found')
    cases=[]
    def case(name,function):
        started=time.monotonic()
        try: detail=function();row=dict(name=name,status='PASS',detail=detail)
        except Exception as error:row=dict(name=name,status='FAIL',error=str(error))
        row['seconds']=round(time.monotonic()-started,3);cases.append(row)
        (OUT/'report.json').write_text(json.dumps(dict(port=board.port.port,probes=probes,cases=cases,
            reads=board.reads,writes=board.writes),ensure_ascii=False,indent=2),encoding='utf-8')
        print(name,row['status'],row.get('error',''),flush=True)
    def defaults():
        got={hex(a):board.read(a) for a in [0,0x37,0x40,0x5c,0x7f,0xa4,0xa5]}
        assert list(got.values())==[2,0,1,0x70,0x10,0xd2,1],got
        assert board.snapshot()['active']==0
        assert board.word(0x90)==512 and board.word(0x92)==512
        return got
    case('power_on_defaults_and_frame_period',defaults)
    def startup_silence():
        values=board.capture('startup_silence',512)
        assert np.all(values==0),dict(min=int(values.min()),max=int(values.max()))
        return dict(samples=512,all_zero=True)
    case('internal_power_on_silence',startup_silence)
    def registers():
        rng=random.Random(20);tested=0
        # Safe inert parameters, effects and sequencer disabled.
        for addr in [0x30,0x31,0x32,0x33,0x34,0x35,0x36,0x43,0x44,0x45,0x46,0x47,0x49,0x54,0x5c,0x6e]:
            old=board.read(addr)
            for value in [0,255,85,170,rng.randrange(256)]:
                board.write(addr,value);assert board.read(addr)==value,(addr,value);tested+=1
            board.write(addr,old)
        # Out-of-range writes must not alias low parameters.
        before=board.read(0x30);board.write(0xb0,7);assert board.read(0x30)==before
        return dict(patterns=tested,out_of_range_alias=False)
    case('register_roundtrips_and_alias_protection',registers)
    board.write(0,8);board.write(0x37,0);board.write(0x40,1)
    def note_lifecycle():
        start=board.snapshot()
        for n in [36,48,60,69,84,96,108]:
            board.note(n);assert bin(board.snapshot()['active']).count('1')==1,n
            board.note(n,False);assert board.snapshot()['active']==0,n
        end=board.snapshot();assert (end['ack']-start['ack'])&65535==14
        return dict(notes=7,on=7,off=7)
    case('notes_across_range_on_off',note_lifecycle)
    def full_polyphony():
        for n in range(40,72):board.note(n)
        snap=board.snapshot();assert snap['active']==0xffffffff,snap
        board.note(84);assert board.snapshot()['active']==0xffffffff
        for n in list(range(41,72))+[84]:board.note(n,False)
        snap=board.snapshot();assert snap['active']==0,snap
        return dict(voices=32,steal=True,recovered=True)
    case('32_voices_steal_and_recovery',full_polyphony)
    def high_note_boundary():
        try:
            board.note(127);board.note(60)
            got=board.snapshot()
            assert bin(got['active']).count('1')==2,got
            return dict(highest_note=127,independent_of_note60=True)
        finally:
            board.note(127,False);board.note(60,False)
    case('midi127_free_sentinel_boundary',high_note_boundary)
    def randomized():
        rng=random.Random(2026);held=set();start=board.snapshot()
        for i in range(300):
            if held and (len(held)>=8 or rng.random()<.48):
                n=rng.choice(sorted(held));held.remove(n);board.note(n,False)
            else:
                n=rng.choice([v for v in range(48,84) if v not in held]);held.add(n);board.note(n,True,rng.randrange(1,16))
            if i%15==0:assert bin(board.snapshot()['active']).count('1')==len(held)
        for n in sorted(held):board.note(n,False)
        end=board.snapshot();assert end['active']==0
        expected=300+len(held);assert (end['ack']-start['ack'])&65535==expected
        return dict(events=expected,random_seed=2026)
    case('deterministic_random_event_stress',randomized)
    def uart_burst():
        start=board.snapshot();events=5000
        payload=b''.join(bytes([0x60,60|(0x80 if i%2==0 else 0),0x61,12]) for i in range(events))
        previous=board.port.write_timeout;board.port.write_timeout=10
        written=board.port.write(payload);board.port.flush();board.port.write_timeout=previous
        assert written==len(payload),(written,len(payload))
        time.sleep(.1);end=board.snapshot()
        assert (end['ack']-start['ack'])&65535==events,(start,end)
        assert end['active']==0,end
        return dict(events=events,bytes=written,no_lost_ack=True,active_after=0)
    case('5000_event_real_uart_burst',uart_burst)
    def sound():
        board.note(69,True,15);time.sleep(.04)
        base=board.capture('a4_base',2048)
        assert np.max(np.abs(base))>50,'silent synthesis'
        freq=peak(base);assert abs(freq-440)<12,freq
        group=board.snapshot()['last_group']
        board.finger(0,group,0,0);board.finger(0,group,16,1)
        moved=board.capture('a4_finger_plus75cents',2048)
        newfreq=peak(moved);assert abs(newfreq-440*2**(16/256))<12,newfreq
        assert board.snapshot()['fingers']&(1<<group)
        board.finger(0,group,0,1);board.note(69,False);time.sleep(.7)
        tail=board.capture('released_tail',512)
        assert board.snapshot()['active']==0
        return dict(base_peak_hz=freq,moved_peak_hz=newfreq,base_rms=float(np.sqrt(np.mean(base.astype(float)**2))),
                    tail_peak=int(np.max(np.abs(tail))),note='internal digital samples, not DAC output')
    case('hardware_samples_pitch_finger_release',sound)
    def timbre():
        board.write(0x6e,255)
        board.note(60,True,4);low=board.capture('c4_velocity4',1024);board.note(60,False)
        board.note(60,True,15);high=board.capture('c4_velocity15',1024);board.note(60,False)
        lo=float(np.sqrt(np.mean(low.astype(float)**2)));hi=float(np.sqrt(np.mean(high.astype(float)**2)))
        assert hi>lo,(lo,hi)
        board.write(0x6e,0)
        return dict(low_rms=lo,high_rms=hi,ratio=hi/max(lo,1))
    case('hardware_velocity_amplitude',timbre)
    def presets_and_effects():
        levels={}
        try:
            for preset in range(4):
                board.write(0x37,preset);board.note(60,True,15)
                values=board.capture('preset%d_c4'%preset,512)
                rms=float(np.sqrt(np.mean(values.astype(float)**2)))
                assert rms>1,('silent preset',preset,rms)
                levels[str(preset)]=rms;board.note(60,False)
            board.write(0x37,0);board.note(69,True,15)
            for name,control in [('delay',3),('chorus',5),('reverb_safe',0x59)]:
                board.write(0x40,control);time.sleep(.1)
                values=board.capture(name,512,fx=True)
                rms=float(np.sqrt(np.mean(values.astype(float)**2)))
                assert rms>1,('silent effect path',name,rms)
                levels[name]=rms
            return dict(rms=levels,note='functional finite digital output; detailed FX impulse criteria remain simulation tests')
        finally:
            board.write(0x40,1);board.write(0x37,0);board.note(69,False)
    case('presets_and_effects_digital_output',presets_and_effects)
    def two_fingers():
        start=board.snapshot()
        try:
            board.note(60,True,15);g0=board.snapshot()['last_group']
            board.note(67,True,15);g1=board.snapshot()['last_group']
            assert (g0,g1)==(0,1),(g0,g1)
            board.finger(0,g0,0,0);board.finger(1,g1,0,0)
            board.finger(0,g0,16,1);board.finger(1,g1,-16,1)
            data=board.capture('two_fingers_opposite',2048)
            spec=np.abs(np.fft.rfft((data-data.mean())*np.hanning(len(data)),n=16384))
            axis=np.fft.rfftfreq(16384,1/FS)
            expected=[440*2**((60-69)/12+16/256),440*2**((67-69)/12-16/256)]
            peaks=[]
            for f in expected:
                mask=(axis>f-15)&(axis<f+15)
                k=np.flatnonzero(mask)[np.argmax(spec[mask])]
                assert spec[k]>max(spec)*.1,(f,float(spec[k]/max(spec)))
                assert abs(axis[k]-f)<12,(f,float(axis[k]))
                peaks.append(float(axis[k]))
            end=board.snapshot();assert (end['on']-start['on'])&65535==2,(start,end)
            assert end['fingers']&3==3,end
            return dict(expected_hz=expected,observed_hz=peaks,movement_note_on=0)
        finally:
            board.note(60,False);board.note(67,False)
    case('two_fingers_independent_opposite_pitch',two_fingers)
    def sequence():
        board.write(0x50,1);time.sleep(.8);a=board.snapshot()
        time.sleep(.4);b=board.snapshot();assert b['ack']!=a['ack'],(a,b)
        board.write(0x50,0);time.sleep(.03);c=board.snapshot();time.sleep(.15);d=board.snapshot()
        assert c['ack']==d['ack'],(c,d)
        return dict(running_events=(b['ack']-a['ack'])&65535,stopped=True,
                    remaining_active=d['active'],note='disable is not an all-notes-off command')
    case('sequencer_start_and_stop',sequence)
    def overflow():
        got={hex(a):board.read(a) for a in range(0x74,0x7d)}
        assert all(v==0 for v in got.values()),got
        return got
    case('event_drop_diagnostics',overflow)
    board.write(0x50,0)
    # Explicit note-off cleanup; no sensor inputs enabled.
    for n in range(0,127):board.note(n,False)
    board.port.close()
    raise SystemExit(1 if any(x['status']!='PASS' for x in cases) else 0)

if __name__=='__main__':main()
