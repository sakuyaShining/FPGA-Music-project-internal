import unittest
import numpy as np
from live_visualizer import FS
from check_workbench_retrigger import measurements


class RetriggerMeasurementTests(unittest.TestCase):
    def frames(self, amplitude=900, start=100):
        second=start+round(.2*FS)
        result=[]
        for stamp,level in ((start,1000),(second,amplitude)):
            result.append(dict(kind=2,timestamp=stamp&0xffffffff,payload=bytes((188,12))))
            result.append(dict(kind=2,timestamp=(stamp+round(.1*FS))&0xffffffff,payload=bytes((60,0))))
            result.append(dict(kind=1,timestamp=(stamp+round(.008*FS))&0xffffffff,format=2,
                payload=np.full(512,level,dtype='<i2').tobytes()))
        return result

    def test_window_and_gap_use_native_timestamps_once(self):
        result=measurements(self.frames(),60)
        self.assertAlmostEqual(result['ratio'],.9)
        self.assertAlmostEqual(result['rms'][0],1000/32768)
        self.assertAlmostEqual(result['gap_ms'],
            (round(.2*FS)-round(.1*FS))*1000/FS)

    def test_timestamp_wrap_retains_the_same_measurement(self):
        self.assertAlmostEqual(measurements(self.frames(start=0xffffff00),60)['ratio'],.9)

    def test_missing_samples_or_events_cannot_be_normalized_into_a_pass(self):
        frames=self.frames();frames.pop()
        with self.assertRaises(RuntimeError):measurements(frames,60)
        self.assertEqual(measurements(self.frames(amplitude=0),60)['ratio'],0)
