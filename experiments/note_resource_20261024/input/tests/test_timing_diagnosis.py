from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from diagnose_timing import constraint_text, outcome, output_path, registered_wrapper


class TimingDiagnosisTests(unittest.TestCase):
    def setUp(self):
        self.original = (ROOT/'constraints/router_probe.sdc').read_text(encoding='utf-8')

    def test_full_constraints_are_not_rewritten(self):
        self.assertEqual(constraint_text(self.original, 'full'), self.original)

    def test_explicit_bus_spelling_keeps_all_full_constraints(self):
        explicit = constraint_text(self.original, 'full-explicit')
        self.assertEqual(explicit.replace('data_in[0] data_in[1] data_in[2] data_in[3]', 'data_in[*]'), self.original)
        for bit in range(4):
            self.assertEqual(explicit.count('data_in['+str(bit)+']'), 2)
        with self.assertRaises(ValueError):
            constraint_text(self.original.replace('data_in[*]', 'wrong'), 'full-explicit')

    def test_reduced_constraints_have_explicit_boundaries(self):
        clock = constraint_text(self.original, 'clock')
        self.assertIn('create_clock ', clock)
        self.assertNotIn('set_', clock)
        uncertainty = constraint_text(self.original, 'uncertainty')
        self.assertIn('set_clock_uncertainty ', uncertainty)
        self.assertNotIn('set_input_delay ', uncertainty)
        self.assertNotIn('set_output_delay ', uncertainty)
        inputs = constraint_text(self.original, 'input')
        outputs = constraint_text(self.original, 'output')
        combined = constraint_text(self.original, 'io')
        self.assertNotIn('set_output_delay ', inputs)
        self.assertNotIn('set_input_delay ', outputs)
        self.assertNotIn('set_clock_uncertainty ', combined)
        self.assertIn('set_input_delay ', combined)
        self.assertIn('set_output_delay ', combined)

    def test_unknown_commands_cannot_be_silently_dropped(self):
        with self.assertRaises(ValueError):
            constraint_text(self.original+'set_false_path -from nowhere\n', 'clock')
        with self.assertRaises(ValueError):
            constraint_text(self.original, 'unknown')

    def test_input_min_max_are_independently_selected(self):
        maximum = constraint_text(self.original, 'input-max')
        minimum = constraint_text(self.original, 'input-min')
        self.assertIn(' -max 5.0 ', maximum)
        self.assertNotIn(' -min ', maximum)
        self.assertIn(' -min 1.0 ', minimum)
        self.assertNotIn(' -max ', minimum)
        self.assertNotIn('set_output_delay ', maximum+minimum)

    def test_registered_shell_keeps_router_wiring_and_all_input_alignment(self):
        original = (ROOT/'rtl/note_router_timing_probe.v').read_text(encoding='utf-8')
        registered = registered_wrapper(original)
        self.assertEqual(original.split('    note_event_router dut(')[1],
                         registered.split('    note_event_router dut(')[1])
        self.assertIn('load_q<=load;shift_q<=shift;capture_q<=capture;data_in_q<=data_in;', registered)
        self.assertIn('if(shift_q)staging<={staging[231:0],data_in_q};', registered)
        self.assertIn('if(load_q)controls<=staging;', registered)
        self.assertIn('if(capture_q)observation<=', registered)
        self.assertIn('else if(shift_q)observation<=', registered)
        with self.assertRaises(ValueError):
            registered_wrapper(original.replace('if(load)', 'if(other)'))

    def test_input_port_selection_is_explicit_and_guarded(self):
        for selection, ports in [('controls', 'load shift capture'), ('data', 'data_in[*]'),
                                 ('load', 'load'), ('shift', 'shift'), ('capture', 'capture')]:
            selected = constraint_text(self.original, 'input', selection)
            self.assertEqual(selected.count('[get_ports {'+ports+'}]'), 2)
            self.assertNotIn('set_output_delay ', selected)
        for mode, selection in [('full', 'data'), ('input', 'unknown')]:
            with self.assertRaises(ValueError):
                constraint_text(self.original, mode, selection)
        with self.assertRaises(ValueError):
            constraint_text(self.original.replace('load shift capture data_in[*]', 'renamed'), 'input', 'data')

    def test_completion_needs_success_report_and_image(self):
        marker = 'Bitstream generation completed'
        self.assertEqual(outcome(0, marker, True, True, []), 'ROUTE_COMPLETED_DIAGNOSTIC_ONLY')
        for code, console, report, image in ((1, marker, True, True), (0, '', True, True),
                                            (0, marker, False, True), (0, marker, True, False),
                                            (0, marker+'\nERROR (PR0004)', True, True)):
            self.assertEqual(outcome(code, console, report, image, []), 'FAILED_OR_INCOMPLETE_DIAGNOSTIC')
        self.assertEqual(outcome(0, marker, True, True, ['changed.v']), 'SOURCE_CHANGED_REJECTED')

    def test_existing_and_repository_outputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                output_path(Path(temporary))
        with self.assertRaises(ValueError):
            output_path(ROOT/'unused-diagnostic-output')


if __name__ == '__main__':
    unittest.main()
