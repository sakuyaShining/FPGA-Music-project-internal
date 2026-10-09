"""Prevent serial reconfiguration during a capture and preserve failure bytes."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import test_board_hardware as h

class Port:
    def __init__(self,short=False):
        self._timeout=1;self.started=False;self.log=[];self.short=short
    @property
    def timeout(self):return self._timeout
    @timeout.setter
    def timeout(self,value):
        self.log.append(('timeout',value,self.started));self._timeout=value
    def write(self,data):
        if data==bytes([15,0xa8]):self.started=True;self.log.append(('request',))
    def read(self,count):
        # Model the observed corruption when SetCommState runs after request.
        bad=any(x[0]=='timeout' and x[2] for x in self.log)
        self.started=False
        return bytes([0xa8])+bytes(count-1-int(bad or self.short))

class TransportTests(unittest.TestCase):
    def board(self,port):
        b=h.Board.__new__(h.Board);b.port=port;b.writes=0;b.reads=0
        b.read=lambda addr:2;b.word=lambda addr,count=2:2048
        return b
    def test_configure_before_request_and_restore_after_read(self):
        p=Port();b=self.board(p)
        with tempfile.TemporaryDirectory() as d,patch.object(h,'OUT',Path(d)),patch.object(h.time,'sleep'):
            x=b.capture('good',2048)
            self.assertEqual(len(x),2048)
            self.assertEqual(p.log,[('timeout',5,False),('request',),('timeout',1,False)])
            self.assertEqual(len((Path(d)/'good.stream.bin').read_bytes()),6145)
    def test_short_stream_remains_failure_with_raw_evidence(self):
        p=Port(short=True);b=self.board(p)
        with tempfile.TemporaryDirectory() as d,patch.object(h,'OUT',Path(d)),patch.object(h.time,'sleep'):
            with self.assertRaises(AssertionError):b.capture('bad')
            self.assertEqual(len((Path(d)/'bad.stream.bin').read_bytes()),6144)
            self.assertFalse((Path(d)/'bad.npy').exists())
            self.assertEqual(p.timeout,1)
    def test_cleanup_includes_midi127_and_all32_contacts(self):
        b=self.board(Port());notes=[];contacts=[]
        b.note=lambda n,on:notes.append((n,on))
        b.finger=lambda *args:contacts.append(args)
        with patch.object(h.time,'sleep'):b.clear_events(32)
        self.assertEqual(notes,[(n,False) for n in range(128)])
        self.assertEqual(contacts,[(f,f,0,2) for f in range(32)])

if __name__=='__main__':unittest.main()
