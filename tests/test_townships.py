import unittest
from mainegeo import townships

class TestHasAlias(unittest.TestCase):
    def test_has_alias(self):
        result = townships.has_alias('T7 R3 NBPP TWP')
        self.assertEqual(result, False)

class TestExtractAlias(unittest.TestCase):
    def test_extract_alias(self):
        result = townships.extract_alias('T7 R3 NBPP TWP')
        self.assertEqual(result, None)