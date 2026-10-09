"""Causal comparison: configure timeout before/after stream request, no read delay."""
import sys,json,time,random
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'tools/scripts'))
from test_board_hardware import Board
OUT=Path(__file__).parent/'timeout-order02';OUT.mkdir(exist_ok=False)
x=np.load(Path(__file__).parent/'transport-probe02/two_finger_indexed.npy')
expected=bytes([0xa8])+b''.join((int(v)&0xffffff).to_bytes(3,'little') for v in x)
conditions=['before']*30+['after']*30;random.Random(20261010).shuffle(conditions)
b=Board('COM6');rows=[]
try:
    assert b.read(0xa4)==0xd3 and b.read(0xa5)==2
    for k,condition in enumerate(conditions):
        if condition=='before':b.port.timeout=2
        b.write(15,0xa8)
        if condition=='after':b.port.timeout=2
        raw=b.port.read(6145);(OUT/('stream%02d.bin'%k)).write_bytes(raw)
        row={'attempt':k,'timeout_config_order':condition,'length':len(raw),'equals_indexed':raw==expected}
        rows.append(row);print(json.dumps(row),flush=True)
finally:
    b.port.close()
    (OUT/'report.json').write_text(json.dumps({'build':'board-build-20261010-02','read_delay':0,'seed':20261010,'rows':rows},indent=2),encoding='utf-8')
