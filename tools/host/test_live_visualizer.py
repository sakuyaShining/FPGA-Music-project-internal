import binascii
import struct
import unittest
import numpy as np
from live_visualizer import FS, FrameParser, LiveAnalysis


def frame(kind=1,seq=0,stamp=0,payload=None,fmt=1):
    if payload is None: payload=np.zeros(512,dtype='<i2').tobytes()
    body=struct.pack('<BHHIHB',kind,seq,len(payload),stamp,0,fmt)+payload
    return b'FMV1'+body+binascii.crc_hqx(body,0xffff).to_bytes(2,'big')


class LiveTests(unittest.TestCase):
    def test_filtered_format_preserves_source_time_and_observation_rate(self):
        m=LiveAnalysis();p=FrameParser()
        m.ingest(dict(frames=p.feed(frame(fmt=2,stamp=3)+frame(seq=1,fmt=2,stamp=2051)),crc_errors=0,gaps=0))
        self.assertEqual(m.discontinuities,0)
        self.assertEqual(m.sample_rate,FS/4)
        self.assertEqual(m.expected,4099)
        m.spectrum();self.assertEqual(len(m.db),513)

    def test_fragmentation_crc_resync_and_sequence_wrap(self):
        p=FrameParser();raw=frame(seq=65535)+frame(seq=0,stamp=512)
        frames=[]
        for i in range(0,len(raw),7):frames.extend(p.feed(raw[i:i+7]))
        self.assertEqual(len(frames),2);self.assertEqual(p.gaps,0)
        corrupt=bytearray(frame(seq=1));corrupt[100]^=1
        self.assertEqual(len(p.feed(corrupt+frame(seq=2))),1)
        self.assertGreater(p.errors,0);self.assertEqual(p.gaps,1)

    def test_actual_pcm_spectrum_and_accepted_event_duration(self):
        m=LiveAnalysis();p=FrameParser()
        raw=frame(2,0,10,bytes((0x80|69,12)))
        tone=(np.sin(2*np.pi*440*np.arange(8192)/FS)*.25*32767).astype('<i2')
        for i in range(16):raw+=frame(1,i+1,i*512,tone[i*512:(i+1)*512].tobytes())
        raw+=frame(2,17,4000,bytes((69,12)))
        m.ingest(dict(frames=p.feed(raw),crc_errors=0,gaps=0));m.spectrum()
        self.assertLess(abs(m.frequencies[np.argmax(m.db)]-440),FS/4096)
        self.assertEqual(len(m.events),1);self.assertFalse(m.active)
        self.assertAlmostEqual(m.events[0][1],4000/FS)

    def test_audio_gap_does_not_bridge_wave_or_fft(self):
        m=LiveAnalysis();p=FrameParser()
        m.ingest(dict(frames=p.feed(frame()+frame(seq=1,stamp=1024)),crc_errors=0,gaps=0))
        self.assertEqual(m.discontinuities,1);self.assertEqual(len(m.audio),512)
        m.spectrum();self.assertEqual(len(m.db),0)

    def test_silence_has_finite_spectrum_and_bounded_history(self):
        m=LiveAnalysis();p=FrameParser()
        for i in range(450):m.ingest(dict(frames=p.feed(frame(seq=i,stamp=i*512)),crc_errors=0,gaps=0))
        self.assertLessEqual(len(m.audio),int(FS*4));m.spectrum()
        self.assertTrue(np.all(np.isfinite(m.db)));self.assertTrue(np.all(m.db<=-119))


if __name__=='__main__':unittest.main()
