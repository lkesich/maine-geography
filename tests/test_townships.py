import unittest
from mainegeo.townships import townships

class TestHasAlias(unittest.TestCase):
    def test_has_alias(self):
        result = townships.has_alias('T7 R3 NBPP TWP')
        self.assertEqual(result, False)