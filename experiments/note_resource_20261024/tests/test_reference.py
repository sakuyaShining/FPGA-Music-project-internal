from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reference import ResourceModel, scenarios
from verify import first_difference, mutate


def command(kind, token, layers=1, groups=0, cancel=0):
    return dict(kind=kind, token=token, layers=layers, groups=groups, cancel=cancel)


class ReferenceTests(unittest.TestCase):
    def test_complete_four_layer_admission_and_duplicate(self):
        model = ResourceModel()
        result = model.apply(command(0, 1, 15))
        self.assertEqual(result['response'][:4], [0, 1, 15, 15])
        self.assertEqual([work[0] for work in result['works']], [2, 3])
        self.assertEqual(model.apply(command(0, 1, 3))['response'][0], 5)
        self.assertEqual(len(model.notes), 1)

    def test_off_does_not_free_tail(self):
        model = ResourceModel()
        model.apply(command(0, 1, 15))
        model.apply(command(1, 1))
        self.assertEqual(model.used(), 15)
        result = model.apply(command(2, 1, groups=1))
        self.assertEqual(result['response'][0], 2)
        self.assertEqual(model.used(), 14)

    def test_young_released_instance_before_old_held_and_whole_reclaim(self):
        model = ResourceModel()
        for token in range(1, 9):
            model.apply(command(0, token, 15))
        model.apply(command(1, 8))
        result = model.apply(command(0, 9, 1))
        self.assertEqual(result['works'][0][0:4:2], [1, 8])
        self.assertEqual(result['works'][0][3], 0xf0000000)
        self.assertIn(1, model.notes)
        self.assertNotIn(8, model.notes)

    def test_cancellation_stages_leave_no_new_note(self):
        for stage in (1, 3, 4, 5, 6):
            model = ResourceModel()
            result = model.apply(command(0, 1, 15, cancel=stage))
            self.assertEqual(result['response'][0], 6)
            self.assertEqual(model.used(), 0)

    def test_retired_on_replay_and_late_off_cannot_replace_note(self):
        model = ResourceModel()
        model.apply(command(0, 1))
        model.apply(command(2, 1, groups=1))
        model.apply(command(0, 2))
        for kind in (0, 1, 2):
            self.assertEqual(model.apply(command(kind, 1, groups=1))['response'][0], 3)
        self.assertEqual(model.used(), 1)
        self.assertIn(2, model.notes)

    def test_serial_wrap_and_source_identity(self):
        model = ResourceModel()
        for token in (0x7ffffffe, 0xffffffff, 0x7fffffff, 0, 0x80000000):
            self.assertEqual(model.apply(command(0, token))['response'][0], 0)
        self.assertEqual(len(model.notes), 5)

    def test_deterministic_scenarios_and_ticket_wrap(self):
        commands, expected = scenarios(random_count=20)
        self.assertEqual((commands, expected), scenarios(random_count=20))
        tickets = [work[1] for result in expected for work in result['works']]
        self.assertGreater(len(tickets), 256)
        self.assertTrue(all(ticket == index % 8 for index, ticket in enumerate(tickets)))
        self.assertEqual(expected[-1]['snapshot'][:3], [0, 0, 0])

    def test_comparator_and_mutation_guards_reject_weakened_or_missing_data(self):
        expected = [dict(works=[[1, 0, 8, 15, 15, 0]], response=[0], snapshot=[0], entries=[])]
        observed = [dict(expected[0], works=[[1, 0, 8, 1, 15, 0]])]
        self.assertEqual(first_difference(expected, observed)['field'], 'works')
        self.assertEqual(first_difference(expected, [])['field'], 'command-count')
        with self.assertRaises(ValueError):
            mutate('not the source', 'tail-priority')


if __name__ == '__main__':
    unittest.main()
