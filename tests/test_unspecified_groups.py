import unittest
from mainegeo import unspecified_groups

class TestHasMultiCounty(unittest.TestCase):
    def test_has_multi_county(self):
        result = unspecified_groups.has_multi_county_regtown(['PISCATAQUIS TWPS'], 'MILLINOCKET')
        self.assertEqual(result, True)