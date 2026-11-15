"""Numerical and rejection checks; synthetic inputs are never published as observations."""
import unittest
import numpy as np
from calculate import ndmi

class NDMIQualityTests(unittest.TestCase):
    def calculate(self, dn5=20000, dn6=15000, qa=64, sat=0):
        a=[np.array([x],dtype='uint16') for x in (dn5,dn6,qa,sat)]
        result, valid=ndmi(*a)
        return float(result[0]), bool(valid[0])

    def test_scale_offset_before_ratio(self):
        value,valid=self.calculate()
        self.assertTrue(valid)
        self.assertAlmostEqual(value, (.35-.2125)/(.35+.2125),places=7)
        self.assertGreater(abs(value-(20000-15000)/(20000+15000)),.1)

    def test_each_cloud_shadow_snow_fill_flag_rejected(self):
        for bit in range(6):
            with self.subTest(bit=bit):
                self.assertFalse(self.calculate(qa=64|(1<<bit))[1])

    def test_b5_b6_saturation_and_terrain_rejected(self):
        for bit in (4,5,11):
            with self.subTest(bit=bit):
                self.assertFalse(self.calculate(sat=1<<bit)[1])
        self.assertTrue(self.calculate(sat=1<<0)[1])

    def test_missing_or_negative_reflectance_rejected(self):
        self.assertFalse(self.calculate(dn5=0)[1])
        self.assertFalse(self.calculate(dn6=7000)[1])

    def test_equal_bands_and_band_swap(self):
        self.assertEqual(self.calculate(dn5=15000,dn6=15000)[0],0)
        self.assertAlmostEqual(self.calculate()[0],-self.calculate(dn5=15000,dn6=20000)[0])

if __name__=='__main__': unittest.main()
