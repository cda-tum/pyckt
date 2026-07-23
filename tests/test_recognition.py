import unittest

from core.circuit import Circuit
from recognition.library import ArrayLibrary, Library, PairLibrary
from recognition.model import StructureCircuits
from recognition.recognizer import StructureRecognizer


class TestStructureRecognizer(unittest.TestCase):
    def test_recognize(self):
        library = Library(array_library=ArrayLibrary(), pair_library=PairLibrary())
        sr = StructureRecognizer(library)
        result = sr.recognize(Circuit("empty"))
        self.assertIsInstance(result, StructureCircuits)
        self.assertEqual(result.total_structures, 0)


if __name__ == "__main__":
    unittest.main()
