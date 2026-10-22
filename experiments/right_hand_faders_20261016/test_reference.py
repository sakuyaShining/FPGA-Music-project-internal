import unittest
from reference import resolve,Touch

class FaderRules(unittest.TestCase):
    def setUp(self):
        self.axes=[50,150];self.zones=[(0,100),(100,200)];self.held=[300,200]
    def run_case(self,points,radius=100):
        return resolve(self.axes,self.zones,[Touch(*p) for p in points],self.held,radius)
    def test_same_side_nearest_wins_in_either_report_order(self):
        pts=[(5,10,100),(2,45,400)]
        for p in (pts,list(reversed(pts))):self.assertEqual(self.run_case(p)[0],[400,200])
    def test_each_side_selects_nearest_then_midpoint(self):
        self.assertEqual(self.run_case([(0,10,0),(1,40,100),(2,60,300),(3,90,479)])[0],[200,200])
    def test_no_attraction_across_zone_even_with_huge_radius(self):
        self.assertEqual(self.run_case([(0,99,100)],1023)[0],[100,200])
    def test_boundary_belongs_only_to_right_zone(self):
        self.assertEqual(self.run_case([(0,100,50)],1023)[0],[300,50])
    def test_touch_removal_holds_affected_fader(self):
        held,_=self.run_case([(0,40,100),(1,160,400)])
        result,_=resolve(self.axes,self.zones,[Touch(1,160,350)],held,100)
        self.assertEqual(result,[100,350])
        self.assertEqual(resolve(self.axes,self.zones,[],result,100)[0],result)
    def test_on_axis_overrides_both_side_candidates(self):
        self.assertEqual(self.run_case([(2,50,125),(0,49,450),(1,51,300)])[0],[125,200])
    def test_distance_tie_is_id_stable(self):
        self.assertEqual(self.run_case([(7,40,50),(1,40,350)])[0],[350,200])
    def test_adjustable_range_and_inclusive_limit(self):
        self.assertEqual(self.run_case([(1,40,50)],9)[0],self.held)
        self.assertEqual(self.run_case([(1,40,50)],10)[0],[50,200])
    def test_midpoint_is_wide_then_clamped_not_wrapped(self):
        self.assertEqual(self.run_case([(1,40,1023),(2,60,1023)])[0],[479,200])
        self.assertEqual(self.run_case([(1,40,700),(2,60,100)])[0],[400,200])
    def test_half_pixel_rounds_to_smaller_pixel_y(self):
        self.assertEqual(self.run_case([(1,40,100),(2,60,101)])[0],[100,200])
    def test_overlapping_regions_and_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):resolve(self.axes,[(0,120),(100,200)],[],self.held,50)
        with self.assertRaises(ValueError):self.run_case([(1,40,0),(1,60,100)])

if __name__=='__main__':unittest.main()
