"""Run01 diagnosis only: archive raw stream and indexed reads, do not reinterpret failures."""
import json
import sys
import time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/scripts'))
from test_board_hardware import Board

out = Path(__file__).parent / 'sample-probe01'
out.mkdir(exist_ok=False)
b = Board('COM6')
report = {}
try:
    report['identity'] = {hex(a): b.read(a) for a in [0x7f,0xa4,0xa5,0xa9]}
    assert report['identity']=={'0x7f':17,'0xa4':211,'0xa5':2,'0xa9':32}
    b.write(0x50,0)
    for n in range(128): b.note(n,False)
    b.write(0,8); b.write(0x37,0); b.write(0x40,1)
    b.note(69,True,15)
    time.sleep(.1)
    report['snapshot']=b.snapshot()
    report['registers']={hex(a): b.read(a) for a in [0,0x37,0x40,0x6e,0x5a,0x5c]}
    b.write(0x80,1);time.sleep(.06)
    indexed=[]
    for index in range(128):
        b.write(0x81,index);b.write(0x82,0)
        value=b.word(0xa0,3)
        indexed.append(value-(1<<24) if value&(1<<23) else value)
    np.save(out/'indexed128.npy',np.asarray(indexed,dtype=np.int32))
    report['indexed']={'min':min(indexed),'max':max(indexed),'nonzero':sum(v!=0 for v in indexed),
                       'first16':indexed[:16]}
    report['streams']=[]
    for attempt in range(3):
        b.port.reset_input_buffer();b.write(15,0xa8)
        b.port.timeout=2
        raw=b.port.read(6145)
        (out/('stream%d.bin'%attempt)).write_bytes(raw)
        report['streams'].append({'length':len(raw),'first16':raw[:16].hex(),'last16':raw[-16:].hex()})
        time.sleep(.1)
    print(json.dumps(report,indent=2),flush=True)
finally:
    b.note(69,False);b.port.close()
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
