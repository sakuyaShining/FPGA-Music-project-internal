from common import *
import sys
sys.path.insert(0,str(R/'host'))
from config_transport_client import payload_for,checksum
words=[int(x,16) for x in (R/'config-fast.hex').read_text().split()];payload=payload_for(words)
(R/'transport-payload.hex').write_text(''.join('%02x\n'%x for x in payload),encoding='ascii')
bad=bytearray(payload);bad[175]|=0x10
(R/'transport_fixture.vh').write_text('`define GOOD_CRC 16\'h%04x\n`define BAD_FIELD_CRC 16\'h%04x\n'%(checksum(0,0x1234,payload),checksum(0,0x1234,bad)),encoding='ascii')
files=sources()+[R/'tb_transport.v'];run([IV,'-g2012','-I',str(R),'-I',str(R/'src'),'-s','tb_transport','-o',str(E/'transport.vvp'),*map(str,files)],'compile-transport')
log=run([VVP,str(E/'transport.vvp')],'run-transport',R/'src')
(E/'transport-validation.json').write_text(json.dumps(dict(status='PASS decoded register transport/table checks in simulation',log=log,inputs={p.relative_to(R).as_posix():sha(p) for p in files+[R/'transport_fixture.vh',R/'transport-payload.hex',R/'config-fast.hex',R/'host/config_transport_client.py',Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
