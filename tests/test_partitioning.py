import unittest
from pyckt.partitioning.partitioner import Partitioner


class TestPartitioner(unittest.TestCase):
    def test_partition(self):
        p = Partitioner()
        self.assertIsNone(p.partition())


if __name__ == "__main__":
    unittest.main()
