import unittest
from pyckt.recognition.recognizer import StructureRecognizer


class TestStructureRecognizer(unittest.TestCase):
    def test_recognize(self):
        sr = StructureRecognizer()
        self.assertIsNone(sr.recognize())


if __name__ == "__main__":
    unittest.main()
