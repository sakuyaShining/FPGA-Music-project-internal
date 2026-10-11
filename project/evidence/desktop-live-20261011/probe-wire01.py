import sys,time,json
from pathlib import Path
sys.path.insert(0,'tools/host')
import serial
from live_visualizer import FrameParser
out=Path('project/evidence/desktop-live-20261011/wire-probe01');out.mkdir(exist_ok=False)
s=serial.Serial('COM6',1500000,timeout=.02,write_timeout=.5)
s.set_buffer_size(rx_size=262144,tx_size=65536)
s.write(bytes((0xb5,0)));s.flush();time.sleep(.12);s.reset_input_buffer()
p=FrameParser();data=bytearray();frames=[];start=time.monotonic()
s.write(bytes((0xb5,1)));s.flush()
try:
 while time.monotonic()-start<5:
  r=s.read(max(1,min(8192,s.in_waiting)));data.extend(r);frames.extend(p.feed(r))
finally:
 s.write(bytes((0xb5,0)));s.flush();time.sleep(.12);s.close()
(out/'wire.bin').write_bytes(data)
report=dict(bytes=len(data),frames=len(frames),errors=p.errors,gaps=p.gaps,first=[(f['kind'],f['sequence'],f['timestamp']) for f in frames[:4]],last=[(f['kind'],f['sequence'],f['timestamp']) for f in frames[-4:]])
(out/'report.json').write_text(json.dumps(report,indent=2));print(report)
