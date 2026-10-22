"""Record Win32 receive errors against retained capture RAM; no FPGA change."""
import ctypes,json,sys,difflib
from pathlib import Path
import numpy as np
from serial import win32
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools/scripts'))
from test_board_hardware import Board
OUT=Path(__file__).parent/'serial-errors02';OUT.mkdir(exist_ok=False)
x=np.load(Path(__file__).parent/'transport-probe02/two_finger_indexed.npy')
expected=bytes([0xa8])+b''.join((int(v)&0xffffff).to_bytes(3,'little') for v in x)
b=Board('COM6');rows=[]
def errors():
    flags=win32.DWORD();stat=win32.COMSTAT()
    if not win32.ClearCommError(b.port._port_handle,ctypes.byref(flags),ctypes.byref(stat)):
        raise ctypes.WinError()
    return {'flags':flags.value,'queued':stat.cbInQue}
try:
    assert b.read(0xa4)==0xd3 and b.read(0xa5)==2
    for k in range(20):
        before=errors();b.write(15,0xa8);b.port.timeout=3
        raw=b.port.read(6145);after=errors()
        (OUT/('stream%02d.bin'%k)).write_bytes(raw)
        row={'attempt':k,'before':before,'after':after,'length':len(raw),'equals_indexed':raw==expected}
        if raw!=expected:
            sm=difflib.SequenceMatcher(None,expected,raw,autojunk=False)
            row['differences']=[{'op':t,'expected_range':[i,j],'actual_range':[a,z],
                'expected_hex':expected[i:j].hex(),'actual_hex':raw[a:z].hex()}
                for t,i,j,a,z in sm.get_opcodes() if t!='equal']
        rows.append(row);print(json.dumps(row),flush=True)
finally:
    b.port.close()
    (OUT/'report.json').write_text(json.dumps({'build':'board-build-20261010-02','rows':rows},indent=2),encoding='utf-8')
