import unittest
from pyckt.topology.generator import TopologyGenerator


class TestTopologyGenerator(unittest.TestCase):
    def test_generate(self):
        tg = TopologyGenerator()
        self.assertIsNone(tg.generate())


if __name__ == "__main__":
    unittest.main()
