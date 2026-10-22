import unittest
from right_fader_model import targets, advance


class FollowModelTest(unittest.TestCase):
    def test_two_finger_order_does_not_change_midpoint(self):
        a = [(5, 2, 100), (8, 2, 3001), (3, 7, 4095)]
        self.assertEqual(targets(a), targets(list(reversed(a))))
        values, ambiguity = targets(a)
        self.assertEqual(values[2], 1550)
        self.assertEqual(values[7], 4095)
        self.assertEqual(ambiguity, [])

    def test_release_holds_current_not_old_target(self):
        goals, _ = targets([(1, 0, 4000)])
        state = advance([0] * 8, goals, 50)
        no_fingers, _ = targets([])
        for _ in range(10):
            state = advance(state, no_fingers, 50)
        self.assertEqual(state[0], 50)
        goals, _ = targets([(9, 0, 0)])
        self.assertEqual(advance(state, goals, 20)[0], 30)

    def test_third_finger_does_not_choose_arbitrary_owner(self):
        goals, ambiguity = targets([(1, 0, 0), (2, 0, 100), (3, 0, 300), (4, 1, 400)])
        self.assertEqual(ambiguity, [0])
        self.assertEqual(advance([50] * 8, goals, 20)[:2], [50, 70])

    def test_stop_and_endpoint_bounds(self):
        self.assertEqual(advance([100], [4095], 0), [100])
        self.assertEqual(advance([4090], [4095], 100), [4095])
        self.assertEqual(advance([5], [0], 100), [0])

    def test_invalid_report_is_rejected(self):
        for points in [[(1, 0, 0), (1, 1, 1)], [(1, 8, 1)], [(1, 0, -1)], [(1, 0, 4096)]]:
            with self.assertRaises(ValueError):
                targets(points)


if __name__ == "__main__":
    unittest.main()
