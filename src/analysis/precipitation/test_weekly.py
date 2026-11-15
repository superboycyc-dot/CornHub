import datetime as dt
import unittest
import numpy as np
from weekly import summarize,weekly_groups

class WeeklyTests(unittest.TestCase):
 def test_area_weighted_depth_not_sum_of_locations(self):
  v=np.tile([1.,4.],(7,1));w=np.array([[1.,3.]])
  mean,area,valid=summarize(v,w)
  self.assertEqual(mean[0],22.75);self.assertEqual(area[0],4)
 def test_missing_day_excludes_cell_instead_of_zero(self):
  v=np.tile([1.,4.],(7,1));v[2,1]=np.nan
  mean,area,valid=summarize(v,np.array([[1.,3.]]))
  self.assertEqual(mean[0],7);self.assertEqual(area[0],1);self.assertFalse(valid[1])
 def test_no_complete_cell_is_nan(self):
  mean,area,_=summarize(np.array([[np.nan,1.],[2.,np.nan]]),np.array([[1.,3.]]))
  self.assertTrue(np.isnan(mean[0]));self.assertEqual(area[0],0)
 def test_cross_year_iso_and_partial_edges(self):
  dates=[dt.date(2021,1,1)+dt.timedelta(days=i) for i in range(10)]
  groups=weekly_groups(dates)
  self.assertEqual(groups[0][0],dt.date(2020,12,28));self.assertEqual(len(groups[0][1]),3)
  self.assertEqual(groups[1][0],dt.date(2021,1,4));self.assertEqual(len(groups[1][1]),7)
  self.assertEqual(groups[0][0].isocalendar().year,2020)
 def test_zero_is_valid_precipitation(self):
  mean,area,_=summarize(np.zeros((7,2)),np.array([[1.,3.]]))
  self.assertEqual(mean[0],0);self.assertEqual(area[0],4)

if __name__=='__main__':unittest.main()
