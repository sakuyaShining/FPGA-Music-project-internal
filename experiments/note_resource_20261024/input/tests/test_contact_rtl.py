from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from contact_rtl_reference import INPUTS, OUTPUTS, generate, pack, unpack
from verify_contact_rtl import FAULTS, bench, compare, mutate
from build_contact import wrapper


class ContactRtlTests(unittest.TestCase):
    def test_bench_substitutions_preserve_parameter_identifiers(self):
        text = bench(1, 31, 17)
        self.assertIn('.SOURCE(1),.SERIAL_W(31),.INITIAL_SERIAL(2147483645)', text)
        self.assertIn('cycle<17', text)
        self.assertNotIn('SOURCE_VALUE', text)

    def test_diagnostic_wrapper_preserves_every_contact_port(self):
        text = wrapper()
        self.assertIn('note_contact_adapter dut(.clk(clk),', text)
        for name, width in INPUTS+OUTPUTS:
            self.assertIn('.'+name+'('+name+')', text)
        self.assertNotIn('INPUT_WIDTH', text)

    def test_directed_cases_include_wrap_cancellation_and_layer_races(self):
        for source, width in ((0, 31), (1, 31), (0, 3)):
            inputs, expected, coverage = generate(source, width)
            self.assertEqual(len(inputs), len(expected))
            self.assertGreater(coverage['event_stalls'], 0)
            self.assertEqual(coverage['reply_stalls'], 4)
            self.assertGreaterEqual(coverage['rejected_responses'], 5)
            self.assertGreater(coverage['cancellations'], 0)
            self.assertTrue(coverage['old_tail_finish_new_on'])
            self.assertEqual(coverage['generation_wrap'], width == 31)
            self.assertEqual(coverage['serial_exhaustion'], width == 3)

    def test_pack_roundtrip_preserves_every_field_and_signed_bits(self):
        for fields in (INPUTS, OUTPUTS):
            values = {name: -3 for name, width in fields}
            restored = unpack(fields, pack(fields, values))
            self.assertEqual(restored, {name: -3 & ((1 << width)-1) for name, width in fields})

    def test_negative_requires_designated_field_and_complete_known_trace(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'trace.hex'
            path.write_text(format(pack(OUTPUTS, dict(event_token=7)), 'x')+'\n', encoding='utf-8')
            self.assertEqual(compare(path, [0])['field'], 'event_token')
            self.assertIsNone(compare(path, [0], {'query_groups'}))
            self.assertEqual(compare(path, [0], {'event_token'})['field'], 'event_token')
            self.assertEqual(compare(path, [0, 0])['field'], 'trace-length')
            path.write_text('xx\n', encoding='utf-8')
            self.assertEqual(compare(path, [0], {'event_token'})['field'], 'unknown-state')

    def test_mutation_anchors_are_exact_and_never_silently_skipped(self):
        original = (Path(__file__).resolve().parents[1]/'rtl/note_contact_adapter.v').read_text(encoding='utf-8')
        self.assertEqual(mutate(original, 'candidate'), original)
        for fault in FAULTS:
            self.assertNotEqual(mutate(original, fault), original)
            with self.assertRaises(ValueError):
                mutate('', fault)


if __name__ == '__main__':
    unittest.main()
