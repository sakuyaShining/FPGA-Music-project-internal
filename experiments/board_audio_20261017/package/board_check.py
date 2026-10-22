"""Only use with board-audio profile 0x72, ABI 1. Never programs FPGA/Flash.

Default mode reads identity/status. --case explicitly arms a bounded audio test.
"""
from pathlib import Path
import argparse,json,time,math
FS=27000000/512
class Board:
    def __init__(self,transport):self.port=transport
    def write(self,addr,data):
        packet=bytes([addr,data]);n=self.port.write(packet)
        if n!=2:raise RuntimeError('short UART write')
    def read_exact(self,n):
        out=bytearray();deadline=time.monotonic()+3
        while len(out)<n and time.monotonic()<deadline:
            data=self.port.read(n-len(out))
            if data:out.extend(data)
        if len(out)!=n:raise RuntimeError('short UART response: %d/%d'%(len(out),n))
        return bytes(out)
    def read(self,addr):
        self.write(15,addr);data=self.read_exact(2)
        if data[0]!=addr:raise RuntimeError('UART address mismatch')
        return data[1]
    def word(self,addr,n):return sum(self.read(addr+i)<<(8*i) for i in range(n))
    def identify(self):
        identity=dict(profile=self.read(0xC0),abi=self.read(0xC3),diagnostic=self.read(0xA4),scope=self.read(0xA9))
        if identity!=dict(profile=0x72,abi=1,diagnostic=0xD3,scope=32):raise RuntimeError('unexpected board identity: '+str(identity))
        return identity
    def status(self):
        value=self.read(0xC1)
        return dict(ready=bool(value&1),armed=bool(value&4),warm=bool(value&8),initialized=bool(value&16),running=bool(value&32),bound=bool(value&64),fault=bool(value&128),case=self.read(0xC2))
    def snapshot(self):
        self.write(0x83,1)
        return dict(ack=self.word(0x83,2),on=self.word(0x85,2),off=self.word(0x87,2),active=self.word(0x89,4),fingers=self.word(0x94,4),period_min=self.word(0x90,2),period_max=self.word(0x92,2))
    def start_case(self,case):
        self.write(0xC0,0xA6);deadline=time.monotonic()+1
        while time.monotonic()<deadline:
            self.write(0xC1,case);time.sleep(.01);state=self.status()
            if state['fault']:raise RuntimeError('board fault while starting test')
            if state['running'] and state['case']==case:return
        raise RuntimeError('test command not accepted')
    def capture(self):
        count=self.read(0xA7)*256
        if count!=2048:raise RuntimeError('unexpected capture size')
        self.write(0x80,1);deadline=time.monotonic()+2
        while not self.read(0x80)&2:
            if time.monotonic()>deadline:raise RuntimeError('capture timeout')
            time.sleep(.01)
        self.write(15,0xA8);data=self.read_exact(1+count*3)
        if data[0]!=0xA8:raise RuntimeError('capture header mismatch')
        values=[]
        for i in range(count):
            v=int.from_bytes(data[1+i*3:4+i*3],'little');values.append(v-(1<<24) if v&(1<<23) else v)
        return values
def analyze(values):
    result=dict(samples=len(values),sample_rate=FS,rms=math.sqrt(sum(x*x for x in values)/len(values)),peak=max(map(abs,values)),nonzero=sum(x!=0 for x in values),saturated=sum(x in (-8388608,8388607) for x in values))
    try:
        import numpy as np
        x=np.asarray(values,dtype=float);mag=np.abs(np.fft.rfft((x-x.mean())*np.hanning(len(x)),n=32768));k=int(np.argmax(mag[2:])+2);result['peak_hz']=k*FS/32768
    except ImportError:result['peak_hz']=None
    return result
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',required=True);parser.add_argument('--case',type=int,choices=range(1,7));parser.add_argument('--output',type=Path,default=Path('board-audio-result'))
    args=parser.parse_args()
    import serial
    result=dict(hardware_tested=True,bitstream_programmed_by_this_script=False,case=args.case)
    with serial.Serial(args.port,115200,timeout=.2,write_timeout=1) as transport:
        board=Board(transport);transport.reset_input_buffer();result['identity']=board.identify();result['before']=board.status()
        if args.case is None:
            result['snapshot']=board.snapshot();print(json.dumps(result,ensure_ascii=False,indent=2));return
        if not result['before']['ready'] or result['before']['fault'] or result['before']['bound']:raise RuntimeError('board is not ready for a new test')
        args.output.mkdir(parents=True,exist_ok=True)
        result['baseline']=board.snapshot()
        if result['baseline']['active']:raise RuntimeError('active notes already present; reset before a test')
        try:
            board.start_case(args.case);time.sleep(.12)
            current=board.status()
            if not current['running'] or current['case']!=args.case:raise RuntimeError('test command not accepted')
            result['during']=board.snapshot()
            if (result['during']['period_min'],result['during']['period_max'])!=(512,512):raise RuntimeError('sample timing mismatch')
            expected={1:1,2:3,3:2,4:2,6:32}.get(args.case)
            if expected is not None and bin(result['during']['active']).count('1')!=expected:raise RuntimeError('unexpected active group count')
            values=board.capture();result['audio']=analyze(values)
            args.output.mkdir(parents=True,exist_ok=True)
            (args.output/'capture-s24le.bin').write_bytes(b''.join((v&0xFFFFFF).to_bytes(3,'little') for v in values))
            if args.case!=5 and result['audio']['nonzero']==0:raise RuntimeError('silent internal audio')
            if result['audio']['saturated']:raise RuntimeError('internal PCM clipping')
            if args.case==1 and result['audio']['peak_hz'] is not None and abs(result['audio']['peak_hz']-440)>15:raise RuntimeError('A4 frequency mismatch')
            if args.case==6:
                result['stress_after_capture']=board.snapshot()
                if (result['stress_after_capture']['on']-result['baseline']['on'])&0xFFFF!=34:raise RuntimeError('stress did not allocate 34 child notes')
        except Exception as exc:
            result['status']='FAIL';result['error']=str(exc);raise
        finally:
            try:
                board.write(0xC2,0);time.sleep(.12)
                result['after']=board.snapshot();result['status_after']=board.status()
            except Exception as exc:
                result['cleanup_error']=str(exc)
                if 'error' not in result:raise
            finally:(args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        if result['after']['active'] or result['status_after']['armed'] or result['status_after']['fault']:
            result['status']='FAIL';result['error']='cleanup or fault check failed'
            (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');raise RuntimeError(result['error'])
        result['status']='PASS limited digital board checks; listening/analog not verified'
        (args.output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
