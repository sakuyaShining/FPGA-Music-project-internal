"""Fault-oriented host adapter tests. Fake registers, never a hardware result."""
from common import *
import sys,unittest,threading,binascii
sys.path.insert(0,str(R/'host'))
from config_transport_client import apply_document,CAPABILITY,checksum
from instrument_config import default_config

class Device:
    kind='test registers only'
    def __init__(self,fault=None,revision=0):
        self._transaction=threading.RLock();self.ops=[];self.reads=[];self.fault=fault
        self.regs={0xd0+i:v for i,v in enumerate(CAPABILITY)}
        self.regs.update({0xd6:0,0xe9:1,0xde:revision&255,0xdf:revision>>8,0:4})
        self.payload=bytearray();self.sequence=0;self.crc=0
    def read_reg(self,a):
        self.reads.append(a)
        if self.fault=='ack_timeout' and self.payload and a==0xd6:return None
        if self.fault=='cleanup' and self.payload and a==0xe9:return 3
        if self.fault=='selection' and self.payload and a==0x37:return 3
        return self.regs.get(a,0)
    def send(self,frames):
        for a,d,_ in frames.items:
            self.ops.append((a,d))
            if a==0xe0 and d==0xa5:
                self.regs.update({0xd6:1,0xe9:3,0xdb:0});self.payload.clear()
            elif a==0xe0 and d==0xc3:self.regs[0xe9]=1
            elif a==0xe1:self.regs[0xda]=d
            elif a in (0xe2,0xe3):self.regs[a-0xe2+0xd8]=d
            elif a==0xe4:
                self.payload.append(d)
                if self.fault=='short_write' and len(self.payload)==7:
                    self.regs[0xd6]=0;return 6
            elif a==0xe5:self.crc=d
            elif a==0xe6:self.crc|=d<<8
            elif a==0xe7:
                sequence=self.regs[0xd8]|self.regs[0xd9]<<8
                expected=checksum(self.regs[0xda],sequence,self.payload)
                assert len(self.payload)==176 and self.crc==expected
                revision=(self.regs[0xde]|self.regs[0xdf]<<8)+1
                self.regs.update({0xd6:0,0xd7:1,0xdb:176,0xdc:expected&255,0xdd:expected>>8,0xde:revision&255,0xdf:(revision>>8)&255})
                for fault,reg in [('sequence',0xd8),('slot',0xda),('count',0xdb),('crc',0xdc),('revision',0xde)]:
                    if self.fault==fault:self.regs[reg]^=1
                if self.fault=='reject':self.regs[0xd7]=2;self.regs[0xde]=(revision-1)&255
            else:self.regs[a]=d
        return len(frames.items)*2

class Tests(unittest.TestCase):
    def test_crc_known_vector(self):self.assertEqual(binascii.crc_hqx(b'123456789',0xffff),0x29b1)
    def test_success_and_revision_wrap(self):
        for rev in (0,65535):
            d=Device(revision=rev);r=apply_document(d,default_config(),sequence=0x1234)
            self.assertEqual(r['status'],'VOLATILE_CONFIG_CONFIRMED');self.assertEqual(r['commit_state'],'confirmed')
            self.assertEqual(r['ack']['revision'],(rev+1)&65535)
            self.assertEqual(d.ops[-4:],[(0xe0,0xc3),(0x37,0),(0x40,1),(0,12)])
            self.assertFalse(r['persisted']);self.assertFalse(r['audio_verified'])
    def test_old_device_never_written(self):
        d=Device();d.regs[0xd0]=0;r=apply_document(d,default_config())
        self.assertEqual(r['status'],'FAILED');self.assertFalse(d.ops)
    def test_unsupported_before_any_io(self):
        d=Device();doc=default_config();doc['vibrato']['enabled']=True
        r=apply_document(d,doc);self.assertEqual(r['status'],'FAILED');self.assertFalse(d.ops);self.assertFalse(d.reads)
    def test_all_confirmation_fields_required(self):
        for fault in ('sequence','slot','count','crc','revision'):
            with self.subTest(fault=fault):
                d=Device(fault);r=apply_document(d,default_config(),sequence=0x1234)
                self.assertEqual(r['status'],'FAILED');self.assertEqual(r['commit_state'],'unknown')
                self.assertFalse(any(a<0xd0 for a,_ in d.ops))
    def test_ambiguous_ack_no_retry(self):
        d=Device('ack_timeout');r=apply_document(d,default_config())
        self.assertEqual(r['status'],'FAILED');self.assertEqual(r['commit_state'],'unknown')
        self.assertEqual(d.ops.count((0xe0,0xa5)),1);self.assertIn('cleanup_error',r)
    def test_partial_send_no_selection(self):
        d=Device('short_write');r=apply_document(d,default_config())
        self.assertEqual(r['status'],'FAILED');self.assertFalse(r['sent_complete']);self.assertEqual(r['commit_state'],'unknown')
        self.assertFalse(any(a<0xd0 for a,_ in d.ops))
    def test_cleanup_and_selection_failure_remain_visible(self):
        for fault,key in (('cleanup','cleanup_error'),('selection','selection_error')):
            d=Device(fault);r=apply_document(d,default_config())
            self.assertEqual(r['status'],'FAILED');self.assertEqual(r['commit_state'],'confirmed');self.assertIn(key,r)
    def test_busy_no_writes(self):
        d=Device();d.regs[0xe9]=0;r=apply_document(d,default_config())
        self.assertEqual(r['status'],'FAILED');self.assertFalse(d.ops)
    def test_device_reject(self):
        d=Device('reject');r=apply_document(d,default_config())
        self.assertEqual(r['status'],'FAILED');self.assertEqual(r['commit_state'],'rejected')
    def test_explicit_preset_restores_rom(self):
        d=Device();doc=default_config();doc['preset']=2;doc['vibrato']['enabled']=True
        r=apply_document(d,doc,preset_only=True)
        rom=[int(w,16) for w in (R/'src/preset_part.hex').read_text().split()][32:48]
        self.assertEqual(r['status'],'VOLATILE_CONFIG_CONFIRMED');self.assertTrue(r['preset_only'])
        self.assertEqual(bytes(d.payload),b''.join(w.to_bytes(11,'little') for w in rom))

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    assert result.wasSuccessful()
    (E/'transport-host.json').write_text(json.dumps(dict(status='PASS fake backend only',tests=result.testsRun,hardware_tested=False,inputs={p.relative_to(R).as_posix():sha(p) for p in [Path(__file__).resolve(),R/'common.py',*list((R/'host').glob('*.py')),R/'src/preset_part.hex']}),indent=2))
