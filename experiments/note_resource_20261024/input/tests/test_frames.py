from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frame_transport import ports, wrapper
from build_frames import wrapper as timing_wrapper
from verify_frames import FAULTS, FrameOracle, bench, compare, fixture, mutate


class FrameSourceTests(unittest.TestCase):
    def test_ports_match_exported_wrapper_and_full26_contact_dimensions(self):
        text = wrapper()
        self.assertEqual((Path(__file__).resolve().parents[1]/'rtl/note_frame_transport.v').read_bytes(), text.encode('utf-8'))
        self.assertEqual(dict(ports(26)[0])['position'], 234)
        self.assertIn('input wire [NF*9-1:0] position', text)

    def test_bench_preserves_escaped_script_newline_and_stall_mode(self):
        text = bench(26, True)
        self.assertIn('%d\\n",kind', text)
        self.assertIn('.NF(26)', text)
        self.assertIn('delay_mode=17', text)
        self.assertIn('HELD_RETRIGGER', text)

    def test_timing_wrapper_contains_all_public_frame_transport_ports(self):
        text = timing_wrapper()
        self.assertIn('note_frame_transport dut(', text)
        inputs, outputs = ports()
        for name, width in inputs+outputs:
            self.assertIn('.'+name+'('+name+')', text)

    def test_frame_sequence_wrap_is_not_a_discontinuity(self):
        oracle = FrameOracle(4)
        oracle.frame(0xffffffff, 1, 0, [10]*4, 90, 0, 15)
        oracle.frame(0, 1, 0, [20]*4, 90, 0, 15)
        self.assertEqual(oracle.flags & 1, 0)
        self.assertEqual(len(oracle.channels['ON']), 1)
        self.assertEqual(oracle.channels['OFF'], [])

    def test_frame_oracle_preserves_held_after_resource_retirement(self):
        oracle = FrameOracle(4)
        oracle.frame(1, 1, 0, [10]*4, 90, 0, 15)
        oracle.rows[0].update(groups=0, layers=0)
        oracle.frame(2, 1, 0, [50]*4, 90, 0, 15)
        self.assertEqual(len(oracle.channels['ON']), 1)
        self.assertEqual(oracle.channels['MOVE'], [])
        oracle.frame(3, 0, 0, [50]*4, 90, 0, 15)
        oracle.frame(4, 1, 0, [50]*4, 90, 0, 15)
        self.assertEqual(len(oracle.channels['ON']), 2)

    def test_invalid_frame_quarantine_requires_a_real_release(self):
        oracle = FrameOracle(4)
        oracle.frame(1, 1, 0, [10]*4, 90, 0, 15)
        for sequence in range(2, 5):
            oracle.frame(sequence, 1, 1, [30]*4, 90, 0, 15)
        self.assertEqual(oracle.channels['OFF'], [[0]])
        oracle.frame(5, 1, 0, [30]*4, 90, 0, 15)
        self.assertEqual(len(oracle.channels['ON']), 1)

    def test_zero_layer_admission_does_not_hang_or_retrigger_held_contact(self):
        oracle = FrameOracle(4)
        oracle.frame(1, 1, 0, [10]*4, 90, 0, 0)
        oracle.frame(2, 1, 0, [10]*4, 90, 0, 15)
        self.assertEqual(oracle.channels['ON'], [])
        self.assertTrue(oracle.flags & 16)
        oracle.frame(3, 0, 0, [10]*4, 90, 0, 15)
        oracle.frame(4, 1, 0, [10]*4, 90, 0, 15)
        self.assertEqual(len(oracle.channels['ON']), 1)

    def test_fixture_covers_generation_wrap_default_capacity_and_fault_flags(self):
        for nf in (4, 26):
            commands, channels = fixture(nf)
            self.assertEqual(channels['FLAGS'], [[31]])
            self.assertEqual(len(channels['CANCEL']), 1)
            self.assertEqual(channels['ON'][nf-1][0], nf-1)
            if nf == 4:
                self.assertGreater(len(channels['ON']), 256)

    def test_comparison_requires_complete_known_semantic_channels(self):
        expected = dict(ON=[[1]], OFF=[], BOUNDARY=[[1, 0, 0]])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trace.txt'
            path.write_text('ON 2\nBOUNDARY 1 0 0\n', encoding='utf-8')
            self.assertEqual(compare(path, expected)['channel'], 'ON')
            self.assertIsNone(compare(path, expected, ['BOUNDARY']))
            path.write_text('ON x\n', encoding='utf-8')
            self.assertEqual(compare(path, expected)['channel'], 'unknown-state')

    def test_fault_anchors_are_exact(self):
        text = (Path(__file__).resolve().parents[1]/'rtl/contact_frame_source.v').read_text(encoding='utf-8')
        for fault in FAULTS:
            self.assertNotEqual(mutate(text, fault), text)
            with self.assertRaises(ValueError):
                mutate('', fault)


if __name__ == '__main__':
    unittest.main()
