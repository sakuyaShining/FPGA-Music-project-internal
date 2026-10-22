"""Isolate held sample RAM reads and two contacts after run02; preserve failures."""
import sys, json, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tools/scripts'))
from test_board_hardware import Board, FS
OUT=Path(__file__).parent/'transport-probe02'
OUT.mkdir(exist_ok=False)
b=Board('COM6')
report={'build_record':'project/versions/board-build-20261010-02.json','scope':'diagnostic followup; not replacement for failed run02'}
def clean():
    for n in range(128): b.note(n,False)
    for f in range(32): b.finger(f,f,0,2)
    time.sleep(.8)
try:
    report['identity']={hex(a):b.read(a) for a in (0xa4,0xa5,0xa9,0x7f)}
    assert report['identity']=={'0xa4':211,'0xa5':2,'0xa9':32,'0x7f':17}
    clean(); report['clean_snapshot']=b.snapshot()
    b.write(0,8); b.write(0x37,0); b.write(0x40,1); b.write(0x6e,0)
    b.note(69,True,15);time.sleep(.08)
    b.write(0x80,1);time.sleep(.06)
    assert b.read(0x80)&3==2
    vals=[]
    for i in range(2048):
        b.write(0x81,i&255);b.write(0x82,i>>8)
        vals.append(b.word(0xa0,3))
    payload=b''.join(v.to_bytes(3,'little') for v in vals)
    (OUT/'indexed.bin').write_bytes(payload)
    report['streams']=[]
    for k in range(5):
        b.write(15,0xa8);b.port.timeout=5;raw=b.port.read(6145);b.port.timeout=1
        (OUT/('stream%d.bin'%k)).write_bytes(raw)
        report['streams'].append({'length':len(raw),'equals_indexed':raw==bytes([0xa8])+payload})
    clean()
    b.note(60,True,15);time.sleep(.05);g0=b.snapshot()['last_group']
    b.note(67,True,15);time.sleep(.05);g1=b.snapshot()['last_group']
    report['groups']=[g0,g1]
    b.finger(0,g0,0,0);b.finger(1,g1,0,0)
    b.finger(0,g0,16,1);b.finger(1,g1,-16,1)
    b.write(0x80,1);time.sleep(.06)
    vals=[]
    for i in range(2048):
        b.write(0x81,i&255);b.write(0x82,i>>8)
        v=b.word(0xa0,3); vals.append(v-(1<<24) if v&(1<<23) else v)
    x=np.asarray(vals,dtype=np.int32);np.save(OUT/'two_finger_indexed.npy',x)
    spec=np.abs(np.fft.rfft((x-x.mean())*np.hanning(len(x)),n=16384))
    axis=np.fft.rfftfreq(16384,1/FS)
    expected=[261.625565*2**(16/256),391.995436*2**(-16/256)]
    report['expected_peak_ratios']=[float(spec[np.abs(axis-f)<12].max()/max(spec.max(),1)) for f in expected]
    report['two_finger_snapshot']=b.snapshot()
except Exception as e:
    report['error']=repr(e)
finally:
    try: clean()
    finally: b.port.close()
    (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
