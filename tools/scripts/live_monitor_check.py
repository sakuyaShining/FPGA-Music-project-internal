"""Gate for real-rate observer framing, CRC, audio continuity and event times."""
import os
from pathlib import Path
import subprocess
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/host'))
from live_visualizer import FrameParser

out=ROOT/'sim_build/live-monitor-check';out.mkdir(parents=True,exist_ok=True)
iv=Path('D:/iverilog/bin')
subprocess.run([str(iv/'iverilog.exe'),'-g2012','-s','tb_live_audio_monitor','-o',str(out/'test.vvp'),
    str(ROOT/'src/rtl/live_audio_monitor.v'),str(ROOT/'src/sim/tb_live_audio_monitor.v')],check=True)
r=subprocess.run([str(iv/'vvp.exe'),str(out/'test.vvp')],cwd=out,capture_output=True,text=True,check=True)
assert 'RESULT live_audio=PASS' in r.stdout,r.stdout
raw=bytes.fromhex((out/'live-bytes.hex').read_text())
p=FrameParser();frames=p.feed(raw);audio=[f for f in frames if f['kind']==1];events=[f for f in frames if f['kind']==2]
assert p.errors==0 and p.gaps==0 and len(audio)>=6 and len(events)==4,(p.errors,p.gaps,len(audio),len(events))
for i,f in enumerate(audio):
 assert f['timestamp']==i*512
 assert np.array_equal(np.frombuffer(f['payload'],dtype='<i2'),np.arange(i*512,(i+1)*512,dtype=np.int16))
 assert f['losses']==0
assert [f['timestamp'] for f in events]==[19,399,599,899]
assert [f['payload'][0] for f in events]==[197,69,197,69]
(out/'normal-bytes.hex').write_bytes((out/'live-bytes.hex').read_bytes())
r=subprocess.run([str(iv/'vvp.exe'),str(out/'test.vvp'),'+SLOW'],cwd=out,capture_output=True,text=True,check=True)
slow=FrameParser().feed(bytes.fromhex((out/'live-bytes.hex').read_text()))
sa=[f for f in slow if f['kind']==1]
assert any(f['losses']>0 for f in slow), 'Backpressure must be visible'
assert all(a['timestamp']<b['timestamp'] for a,b in zip(sa,sa[1:])), 'Reordered audio bank'
for f in sa:
 assert np.array_equal(np.frombuffer(f['payload'],dtype='<i2'),np.arange(f['timestamp'],f['timestamp']+512,dtype=np.int16))
assert any(b['timestamp']!=a['timestamp']+512 for a,b in zip(sa,sa[1:])), 'No visible sample gap'
# Observation filter: bit-exact convolution and anti-alias suppression.
x=np.rint(6000*np.sin(2*np.pi*1000*np.arange(4096)/(27000000/512))+
          6000*np.sin(2*np.pi*12000*np.arange(4096)/(27000000/512))).astype(np.int16)
(out/'filter-input.hex').write_text('\n'.join('%04x'%(int(v)&65535) for v in x))
subprocess.run([str(iv/'iverilog.exe'),'-g2012','-s','tb_live_observation_filter','-o',str(out/'filter.vvp'),
 str(ROOT/'src/rtl/live_observation_filter.v'),str(ROOT/'src/sim/tb_live_observation_filter.v')],check=True)
subprocess.run([str(iv/'vvp.exe'),str(out/'filter.vvp')],cwd=out,check=True,capture_output=True)
import re
rtl=(ROOT/'src/rtl/live_observation_filter.v').read_text()
cs=[]
for line in rtl.splitlines():
 match=re.search(r"coefficient=(-?)16'sd([0-9]+)",line)
 if match:cs.append((-1 if match[1] else 1)*int(match[2]))
cs=np.array(cs,dtype=np.int64)
assert len(cs)==63 and cs.sum()==32768
expected=(np.convolve(x.astype(np.int64),cs)[:len(x)]>>15)[3::4]
y=np.loadtxt(out/'filter-output.txt',dtype=np.int64)
assert np.array_equal(y,expected), 'FIR pipeline does not match reference'
f=np.linspace(6592,26367,500)
response=np.abs(np.exp(-2j*np.pi*f[:,None]*np.arange(63)/(27000000/512))@cs/32768)
assert response.max()<.01, 'Insufficient alias rejection above observed Nyquist'
print('PASS FIR exact1024 samples; stopband max %.1f dB'%(20*np.log10(response.max())))
env=dict(os.environ,PYTHONIOENCODING='utf-8')
subprocess.run([sys.executable,'-m','unittest','discover','-s','tools/host','-p','test_live_visualizer.py'],cwd=ROOT,env=env,check=True)
print('RESULT live_monitor=PASS audio=%d events=%d CRC=0 gaps=0'%(len(audio),len(events)))
