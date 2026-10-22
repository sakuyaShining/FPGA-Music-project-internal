from common import *
import unittest,io
from board_check import Board,analyze
class Fake:
    def __init__(self):
        self.regs={0xC0:0x72,0xC1:0x19,0xC3:1,0xA4:0xD3,0xA9:32,0xA7:8,0x80:2};self.rx=bytearray();self.writes=[];self.bad_echo=False;self.start_ignores=0
    def write(self,data):
        self.writes.append(data)
        if data[0]==0xC1:
            if self.start_ignores:self.start_ignores-=1
            else:self.regs[0xC1]|=32;self.regs[0xC2]=data[1]
        if data[0]==15:
            if data[1]==0xA8:self.rx.extend(bytes([0xA8])+b''.join((i-1024 & 0xFFFFFF).to_bytes(3,'little') for i in range(2048)))
            else:self.rx.extend(bytes([0 if self.bad_echo else data[1],self.regs.get(data[1],0)]))
        return len(data)
    def read(self,n):
        n=min(n,17);out=bytes(self.rx[:n]);del self.rx[:n]
        if not out:raise TimeoutError('fake exhausted')
        return out
class Checks(unittest.TestCase):
    def test_identity(self):self.assertEqual(Board(Fake()).identify()['profile'],0x72)
    def test_wrong_profile(self):
        f=Fake();f.regs[0xC0]=0
        with self.assertRaises(RuntimeError):Board(f).identify()
        self.assertTrue(all(x[0]==15 for x in f.writes))
    def test_wrong_abi(self):
        f=Fake();f.regs[0xC3]=2
        with self.assertRaises(RuntimeError):Board(f).identify()
    def test_bad_echo(self):
        f=Fake();f.bad_echo=True
        with self.assertRaises(RuntimeError):Board(f).read(0xC0)
    def test_signed_chunked_capture(self):self.assertEqual(Board(Fake()).capture(),list(range(-1024,1024)))
    def test_wrong_capture_size(self):
        f=Fake();f.regs[0xA7]=4
        with self.assertRaises(RuntimeError):Board(f).capture()
        self.assertEqual(f.writes,[bytes([15,0xA7])])
    def test_snapshot_endian(self):
        f=Fake();f.regs.update({0x89:0x12,0x8A:0x34,0x8B:0x56,0x8C:0x78,0x91:2,0x93:2});self.assertEqual(Board(f).snapshot()['active'],0x78563412)
    def test_analysis(self):
        a=analyze([0,8388607,-8388608,0]);self.assertEqual(a['saturated'],2);self.assertEqual(a['nonzero'],2)
    def test_start_retry(self):
        f=Fake();f.start_ignores=1;Board(f).start_case(3);self.assertEqual(f.writes.count(bytes([0xC1,3])),2)
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
(E/'host-tests.log').write_text(stream.getvalue(),encoding='utf-8');assert result.wasSuccessful(),stream.getvalue()
(E/'host-validation.json').write_text(json.dumps(dict(status='PASS offline only',tests=result.testsRun,hardware_connected=False,inputs={p.relative_to(R).as_posix():sha(p) for p in [R/'board_check.py',Path(__file__).resolve(),R/'common.py']}),indent=2),encoding='utf-8')
print('PASS offline board host protocol: %d tests'%result.testsRun)
