from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('music_profiles', SCRIPTS / 'music_profiles.py')
profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profiles)


class MusicProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.weights = [256] * 1024
        self.tilts = [256] * 256

    def test_neutral_table_and_velocity_volume_are_separate(self):
        self.assertEqual(profiles.amplitude_reference(180, 192, 0, 0, self.weights, self.tilts), 135)
        self.assertEqual(profiles.amplitude_reference(90, 192, 1, 0, self.weights, self.tilts), 67)
        self.assertEqual(profiles.amplitude_reference(0, 192, 1, 0, self.weights, self.tilts), 0)

    def test_slot_partial_and_velocity_indexing(self):
        self.weights[2 * 256 + 12 * 16 + 5] = 128
        self.assertEqual(profiles.amplitude_reference(120, 192, 2, 5, self.weights, self.tilts), 45)
        self.assertEqual(profiles.amplitude_reference(120, 192, 0, 5, self.weights, self.tilts), 90)
        self.assertEqual(profiles.amplitude_reference(120, 176, 2, 5, self.weights, self.tilts), 82)

    def test_protected_partials_and_integer_rounding(self):
        self.weights[12 * 16] = 0
        self.weights[12 * 16 + 4] = 0
        self.assertEqual(profiles.amplitude_reference(180, 192, 0, 0, self.weights, self.tilts), 33)
        self.assertEqual(profiles.amplitude_reference(180, 192, 0, 4, self.weights, self.tilts), 0)

    def test_saturation_happens_before_velocity_volume(self):
        self.weights[12 * 16 + 4] = 511
        self.tilts[7 * 16 + 4] = 511
        self.assertEqual(profiles.amplitude_reference(200, 192, 0, 4, self.weights, self.tilts), 191)

    def test_reference_rejects_invalid_input(self):
        for values in [(-1, 192, 0, 0), (256, 192, 0, 0), (180, 256, 0, 0),
                       (180, 192, 4, 0), (180, 192, 0, 16)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                profiles.amplitude_reference(*values, self.weights, self.tilts)

    def test_hex_reader_checks_length_and_bounds(self):
        table = self.root / 'weights.hex'
        table.write_text('100 080 // exact\n040\n', encoding='utf-8')
        self.assertEqual(profiles.read_hex(table, 3, 511), [256, 128, 64])
        for count, maximum in [(4, 511), (3, 255)]:
            with self.assertRaises(ValueError):
                profiles.read_hex(table, count, maximum)

    def test_trace_comparison_rejects_truncation_and_byte_changes(self):
        expected, actual = self.root / 'expected', self.root / 'actual'
        expected.write_bytes(b'1 a\n2 b\n')
        actual.write_bytes(b'1 a\n')
        result = profiles.compare_trace(expected, actual)
        self.assertFalse(result['equal'])
        self.assertEqual(result['first_difference']['line'], 2)
        self.assertEqual((result['expected_lines'], result['actual_lines']), (2, 1))
        actual.write_bytes(b'1 a\r\n2 b\r\n')
        self.assertFalse(profiles.compare_trace(expected, actual)['equal'])
        actual.write_bytes(expected.read_bytes())
        self.assertTrue(profiles.compare_trace(expected, actual)['equal'])

    def test_missing_historical_contract_is_not_silently_rewritten(self):
        with self.assertRaisesRegex(ValueError, 'bench contract changed'):
            profiles.replace_required('changed', 'expected', 'new')

    def test_current_profile_keeps_velocity_and_checks_seven_group_snapshots(self):
        case = profiles.CASES[1]
        original = (profiles.engineering.ROOT / 'fpga/current' / profiles.DATA / case[2]).read_text(encoding='utf-8')
        current = profiles.build_bench(original, case, 'current')
        self.assertNotIn('force dut', current)
        self.assertEqual(current.count('profile_check('), 7)
        self.assertIn('profile_expected[64]', current)
        self.assertLess(current.index('reg [7:0] profile_expected'), current.index('!==profile_expected'))
        self.assertIn('dut.core.u_nm.gtab[a]!=90', current)
        self.assertIn('unsupported mask accepted', current)
        self.assertIn('independent custom spectrum', original)

    def test_historical_override_is_explicit_and_not_shared_with_current(self):
        case = profiles.CASES[0]
        original = 'module tb_music; endmodule'
        historical = profiles.build_bench(original, case, 'historical')
        current = profiles.build_bench(original, case, 'current')
        self.assertIn("force dut.core.vel_vscale = 9'd0", historical)
        self.assertIn("force ref_top.vel_vscale = 9'd0", historical)
        self.assertNotIn('force ', current)
        self.assertIn('PROFILE current native_defaults_checked', current)

    def test_wrong_slot_mutation_is_confined_to_isolated_rom_address(self):
        case = profiles.CASES[1]
        original = (profiles.engineering.ROOT / 'fpga/current' / profiles.DATA / case[2]).read_text(encoding='utf-8')
        result = profiles.build_bench(original, case, 'current', 'wrong-slot')
        self.assertNotIn('force ', result)
        self.assertNotIn('force ', original)
        target = self.root / 'engine/src/vel_shape.v'
        target.parent.mkdir(parents=True)
        target.write_text('wire [9:0] widx = {slot, vel, part};\n', encoding='utf-8')
        before = profiles.digest(target)
        changes = profiles.apply_source_fault(self.root, 'wrong-slot')
        self.assertEqual(changes['engine/src/vel_shape.v']['before_sha256'], before)
        self.assertEqual(changes['engine/src/vel_shape.v']['after_sha256'], profiles.digest(target))
        self.assertIn("{2'd0, vel, part}", target.read_text(encoding='utf-8'))
        self.assertNotEqual(before, profiles.digest(target))

    def test_zero_exit_or_pass_text_cannot_hide_fatal(self):
        valid = 'PROFILE current native_defaults_checked\nPASS music\n'
        self.assertTrue(profiles.successful_run(dict(returncode=0, text=valid), 'compat', 'current'))
        for returncode, text in [(0, valid + 'FATAL: hidden'), (1, valid), (0, 'PASS music')]:
            self.assertFalse(profiles.successful_run(dict(returncode=returncode, text=text), 'compat', 'current'))

    def test_layer_pass_requires_all_oracle_checkpoints(self):
        text = 'PROFILE current native_defaults_checked\nPASS layers\n'
        self.assertFalse(profiles.successful_run(dict(returncode=0, text=text), 'layers', 'current'))
        text += 'PROFILE amplitude checked\n' * 7
        self.assertTrue(profiles.successful_run(dict(returncode=0, text=text), 'layers', 'current'))

    def test_counterexample_requires_targeted_failure_not_compile_error_or_timeout(self):
        valid = dict(returncode=1, text='PROFILE current native_defaults_checked\nFATAL: PROFILE custom spectrum')
        self.assertTrue(profiles.expected_fault(valid))
        for returncode, text in [(124, valid['text']), (0, valid['text']),
                                 (1, 'compile failure'), (1, 'PROFILE current native_defaults_checked\nFATAL: watchdog')]:
            self.assertFalse(profiles.expected_fault(dict(returncode=returncode, text=text)))


if __name__ == '__main__':
    unittest.main()
