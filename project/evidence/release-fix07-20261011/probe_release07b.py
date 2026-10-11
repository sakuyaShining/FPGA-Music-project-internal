"""Evidence-only real PCM release test; no retries or GUI smoothing."""
import sys,time,json,hashlib
from pathlib import Path
import serial,numpy as np
ROOT=Path('C:/Users/Sakuya/.codex/worktrees/66a4/FPGA-Music-project')
sys.path.insert(0,str(ROOT/'tools/host'))
from live_visualizer import FrameParser
out=Path(__file__).parent/'release-audio07b';out.mkdir(exist_ok=False)
p=FrameParser();frames=[];wire=bytearray();inputs=[]
ser=serial.Serial('COM6',460800,timeout=.3,write_timeout=1)
def write(a,v):
 ser.write(bytes((a,v)));ser.flush();inputs.append([time.monotonic(),a,v])
def note(n,on,v=0):write(0x60,n|(128 if on else 0));write(0x61,v)
def pump(seconds):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  raw=ser.read(max(1,min(8192,ser.in_waiting)));wire.extend(raw);frames.extend(p.feed(raw))
try:
 identity={}
 for a,v in [(0x7f,0x11),(0xa4,0xd4),(0xa5,4),(0xa9,32)]:
  write(15,a);got=ser.read(2);assert got==bytes((a,v)),got;identity[str(a)]=v
 ser.set_buffer_size(rx_size=262144,tx_size=65536)
 write(0,8);write(0x37,0);write(0x40,1);write(0x5c,0x70)
 
 for n in range(128):note(n,False)
 time.sleep(.4)
 ser.timeout=.02;ser.reset_input_buffer();write(0xb5,1);pump(.2)
 cases=[]
 for v,refresh,poly in [(1,False,False),(4,False,False),(8,False,False),(12,False,False),(4,True,False),(12,False,True)]:
  write(0x5c,0x70);note(69,True,v)
  if poly:note(72,True,v)
  pump(.45)
  if refresh:
   write(0x5c,0x50);write(0x63,0xff);pump(.2)
  note(69,False)
  if poly:pump(.45);note(72,False)
  pump(.55);cases.append({'velocity':v,'refresh':refresh,'poly':poly,'target_note':72 if poly else 69})
 write(0xb5,0);pump(.15)
 audio=[f for f in frames if f['kind']==1];events=[f for f in frames if f['kind']==2]
 t=np.concatenate([(f['timestamp']+np.arange(512)*4)/52734.375 for f in audio])
 y=np.concatenate([np.frombuffer(f['payload'],dtype='<i2') for f in audio]).astype(float)
 offs=[f for f in events if not(f['payload'][0]&128)]
 selected=[f for f in offs if f['payload'][0]==69][:5]+[f for f in offs if f['payload'][0]==72]
 assert len(selected)==len(cases),(len(selected),len(cases))
 for case,event in zip(cases,selected):
  delta=t-event['timestamp']/52734.375
  before=y[(delta>=-.04)&(delta<-.01)];after=y[(delta>=.001)&(delta<.010)]
  assert len(before)>300 and len(after)>100
  pre=float(np.max(np.abs(before)));post=float(np.max(np.abs(after)))
  rms=lambda x:float(np.sqrt(np.mean(x*x)))
  case.update(pre_peak=pre,post_peak=post,peak_ratio=post/pre,pre_rms=rms(before),post_rms=rms(after),off_timestamp=event['timestamp'])
  case['pass']=pre>10 and post<=pre*1.08+3 and rms(after)<=rms(before)*1.08+3
 discontinuities=sum(b['timestamp']!=a['timestamp']+2048 for a,b in zip(audio,audio[1:]))
 losses=sum(f['losses'] for f in frames)
 good=all(c['pass'] for c in cases) and p.errors==0 and p.gaps==0 and discontinuities==0 and losses==0
 report=dict(status='PASS' if good else 'FAIL',cases=cases,identity=identity,crc_errors=p.errors,gaps=p.gaps,discontinuities=discontinuities,losses=losses,audio_frames=len(audio),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),criterion='Post1..10ms peak/RMS <= pre40..10ms *1.08 +3 PCM16 quantization; original v12 spike~30%, v4~4x rejected; no retries',boundary='Internal filtered PCM, not DAC or physical touch')
 (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
finally:
 try:
  write(0xb5,0)
  for n in [69,72]:note(n,False)
 finally:
  ser.close();(out/'wire.bin').write_bytes(wire);(out/'stream.bin').write_bytes(b''.join(f['raw'] for f in frames));(out/'inputs.json').write_text(json.dumps(inputs),encoding='utf-8')
raise SystemExit(0 if good else 1)
