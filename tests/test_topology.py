import unittest
from pyckt.topology.generator import (
    TopologyGenerator,
)
from pyckt.topology.hl2 import (
    DifferentialPairP,
    DifferentialPairN,
)
from PySpice.Spice.Netlist import Circuit


class TestTopologyGenerator(unittest.TestCase):
    def test_generate(self):
        tg = TopologyGenerator()
        self.assertIsNone(tg.generate())


class TestDifferentialPairSynthesis(unittest.TestCase):
    def test_generate_differential_pairs(self):
        # Create a circuit and instantiate both differential pairs
        circuit = Circuit("Test Differential Pair Synthesis")
        circuit.subcircuit(DifferentialPairP())
        circuit.subcircuit(DifferentialPairN())

        # Instantiate both in the circuit
        circuit.X(
            "diffpair_p", "DifferentialPairP", "in1", "in2", "out1", "out2", "vss"
        )
        circuit.X(
            "diffpair_n", "DifferentialPairN", "in1", "in2", "out1", "out2", "vss"
        )
        # Check that both subcircuits are present
        subckt_names = [s.name for s in circuit.subcircuits]
        self.assertIn("DifferentialPairP", subckt_names)
        self.assertIn("DifferentialPairN", subckt_names)
        # Check that both X instances are present
        # x_names = [x.name for x in circuit.X]
        # self.assertIn("diffpair_p", x_names)
        # self.assertIn("diffpair_n", x_names)


if __name__ == "__main__":
    unittest.main()
