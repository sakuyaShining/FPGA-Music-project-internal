"""04 real capture vs indexed RAM, then100 exact streams, no retries."""
import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools/scripts'))
import test_board_hardware as h
OUT=Path(__file__).parent/'transport-stability04';OUT.mkdir(exist_ok=False);h.OUT=OUT
b=h.Board('COM6');report={'build_record':'project/versions/board-build-20261010-04.json','retries':0,'read_delay':0,'streams':[]}
try:
    report['identity']={hex(a):b.read(a) for a in (0xa4,0xa5,0xa9,0x7f)}
    assert report['identity']=={'0xa4':211,'0xa5':2,'0xa9':32,'0x7f':17}
    b.clear_events(32);b.write(0,8);b.write(0x37,0);b.write(0x40,1);b.note(69,True,15);time.sleep(.08)
    captured=b.capture('actual_host_capture',2048)
    indexed=[]
    for i in range(2048):
        b.write(0x81,i&255);b.write(0x82,i>>8);indexed.append(b.word(0xa0,3))
    payload=b''.join(v.to_bytes(3,'little') for v in indexed);(OUT/'indexed.bin').write_bytes(payload)
    capture_payload=b''.join((int(v)&0xffffff).to_bytes(3,'little') for v in captured)
    report['actual_capture_equals_indexed']=capture_payload==payload
    assert report['actual_capture_equals_indexed'],'Actual host capture differs from indexed RAM'
    expected=bytes([0xa8])+payload
    for k in range(100):
        # Match the repaired Board.capture ordering. Reconfigure before request.
        previous=b.port.timeout;b.port.timeout=5
        try:b.write(15,0xa8);raw=b.port.read(6145)
        finally:b.port.timeout=previous
        (OUT/('stream%03d.bin'%k)).write_bytes(raw)
        row={'attempt':k,'length':len(raw),'equals_indexed':raw==expected}
        report['streams'].append(row);print(json.dumps(row),flush=True)
    report['status']='PASS' if all(r['equals_indexed'] for r in report['streams']) else 'FAIL'
except Exception as e:
    report['status']='FAIL';report['error']=repr(e)
finally:
    try:b.clear_events(32)
    finally:b.port.close()
    (OUT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='streams'}),flush=True)
sys.exit(0 if report['status']=='PASS' else 1)
