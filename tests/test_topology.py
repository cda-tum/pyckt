import unittest
from pyckt.topology.generator import (
    TopologyGenerator,
)
from pyckt.topology.HL2.differential_pair import (
    DifferentialPairP,
    DifferentialPairN,
)
from pyckt.topology.HL2.voltage_bias import (
    VoltageBiasP1,
    VoltageBiasP2,
    VoltageBiasP3,
    VoltageBiasP4,
    VoltageBiasP5,
    VoltageBiasP6,
    VoltageBiasN1,
    VoltageBiasN2,
    VoltageBiasN3,
    VoltageBiasN4,
    VoltageBiasN5,
    VoltageBiasN6,
)
from pyckt.topology.HL2.current_bias import (
    CurrentBiasP1,
    CurrentBiasP2,
    CurrentBiasP3,
    CurrentBiasN1,
    CurrentBiasN2,
    CurrentBiasN3,
)
from pyckt.topology.HL2.analog_inverter import (
    AnalogInverter1,
    AnalogInverter2,
    AnalogInverter3,
    AnalogInverter4,
    AnalogInverter5,
    AnalogInverter6,
    AnalogInverter7,
    AnalogInverter8,
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


class TestVoltageBiasSynthesis(unittest.TestCase):
    def test_voltage_bias_p1(self):
        circuit = Circuit("VoltageBiasP1 Test")
        circuit.subcircuit(VoltageBiasP1())
        x = circuit.X("vbias", "VoltageBiasP1", "in", "out", "source")
        self.assertIn("VoltageBiasP1", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasP1")

    def test_voltage_bias_p2(self):
        circuit = Circuit("VoltageBiasP2 Test")
        circuit.subcircuit(VoltageBiasP2())
        x = circuit.X("vbias", "VoltageBiasP2", "in", "out", "source")
        self.assertIn("VoltageBiasP2", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasP2")

    def test_voltage_bias_p3(self):
        circuit = Circuit("VoltageBiasP3 Test")
        circuit.subcircuit(VoltageBiasP3())
        x = circuit.X(
            "vbias", "VoltageBiasP3", "in", "inner", "outInput", "outSource", "source"
        )
        self.assertIn("VoltageBiasP3", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasP3")

    def test_voltage_bias_p4(self):
        circuit = Circuit("VoltageBiasP4 Test")
        circuit.subcircuit(VoltageBiasP4())
        x = circuit.X(
            "vbias", "VoltageBiasP4", "in", "inner", "outInput", "outSource", "source"
        )
        self.assertIn("VoltageBiasP4", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasP4")

    def test_voltage_bias_p5(self):
        circuit = Circuit("VoltageBiasP5 Test")
        circuit.subcircuit(VoltageBiasP5())
        x = circuit.X(
            "vbias", "VoltageBiasP5", "in", "inner", "outInput", "outSource", "source"
        )
        self.assertIn("VoltageBiasP5", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasP5")

    def test_voltage_bias_p6(self):
        circuit = Circuit("VoltageBiasP6 Test")
        circuit.subcircuit(VoltageBiasP6())
        x = circuit.X(
            "vbias", "VoltageBiasP6", "in", "inner", "outInput", "outSource", "source"
        )
        self.assertIn("VoltageBiasP6", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasP6")

    def test_voltage_bias_n1(self):
        circuit = Circuit("VoltageBiasN1 Test")
        circuit.subcircuit(VoltageBiasN1())
        x = circuit.X("vbias", "VoltageBiasN1", "in", "out", "source")
        self.assertIn("VoltageBiasN1", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasN1")

    def test_voltage_bias_n2(self):
        circuit = Circuit("VoltageBiasN2 Test")
        circuit.subcircuit(VoltageBiasN2())
        x = circuit.X("vbias", "VoltageBiasN2", "in", "out", "source")
        self.assertIn("VoltageBiasN2", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasN2")

    def test_voltage_bias_n3(self):
        circuit = Circuit("VoltageBiasN3 Test")
        circuit.subcircuit(VoltageBiasN3())
        x = circuit.X(
            "vbias", "VoltageBiasN3", "in", "inner", "outInput", "outSource", "source"
        )
        self.assertIn("VoltageBiasN3", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasN3")

    def test_voltage_bias_n4(self):
        circuit = Circuit("VoltageBiasN4 Test")
        circuit.subcircuit(VoltageBiasN4())
        x = circuit.X(
            "vbias", "VoltageBiasN4", "in", "inner", "outInput", "outSource", "source"
        )
        self.assertIn("VoltageBiasN4", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasN4")

    def test_voltage_bias_n5(self):
        circuit = Circuit("VoltageBiasN5 Test")
        circuit.subcircuit(VoltageBiasN5())
        x = circuit.X(
            "vbias", "VoltageBiasN5", "in", "inner", "outInput", "outSource", "source"
        )
        self.assertIn("VoltageBiasN5", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasN5")

    def test_voltage_bias_n6(self):
        circuit = Circuit("VoltageBiasN6 Test")
        circuit.subcircuit(VoltageBiasN6())
        x = circuit.X(
            "vbias", "VoltageBiasN6", "in", "inner", "outInput", "outSource", "source"
        )
        self.assertIn("VoltageBiasN6", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "VoltageBiasN6")


class TestCurrentBiasSynthesis(unittest.TestCase):
    def test_current_bias_p1(self):
        circuit = Circuit("CurrentBiasP1 Test")
        circuit.subcircuit(CurrentBiasP1())
        x = circuit.X("cbias", "CurrentBiasP1", "in", "out", "source")
        self.assertIn("CurrentBiasP1", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "CurrentBiasP1")

    def test_current_bias_p2(self):
        circuit = Circuit("CurrentBiasP2 Test")
        circuit.subcircuit(CurrentBiasP2())
        x = circuit.X(
            "cbias", "CurrentBiasP2", "out", "source", "inOutput", "inSource", "inner"
        )
        self.assertIn("CurrentBiasP2", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "CurrentBiasP2")

    def test_current_bias_p3(self):
        circuit = Circuit("CurrentBiasP3 Test")
        circuit.subcircuit(CurrentBiasP3())
        x = circuit.X(
            "cbias", "CurrentBiasP3", "out", "source", "inOutput", "inSource", "inner"
        )
        self.assertIn("CurrentBiasP3", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "CurrentBiasP3")

    def test_current_bias_n1(self):
        circuit = Circuit("CurrentBiasN1 Test")
        circuit.subcircuit(CurrentBiasN1())
        x = circuit.X("cbias", "CurrentBiasN1", "in", "out", "source")
        self.assertIn("CurrentBiasN1", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "CurrentBiasN1")

    def test_current_bias_n2(self):
        circuit = Circuit("CurrentBiasN2 Test")
        circuit.subcircuit(CurrentBiasN2())
        x = circuit.X(
            "cbias", "CurrentBiasN2", "out", "source", "inOutput", "inSource", "inner"
        )
        self.assertIn("CurrentBiasN2", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "CurrentBiasN2")

    def test_current_bias_n3(self):
        circuit = Circuit("CurrentBiasN3 Test")
        circuit.subcircuit(CurrentBiasN3())
        x = circuit.X(
            "cbias", "CurrentBiasN3", "out", "source", "inOutput", "inSource", "inner"
        )
        self.assertIn("CurrentBiasN3", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "CurrentBiasN3")


class TestAnalogInverterSynthesis(unittest.TestCase):
    def test_analog_inverter_1(self):
        circuit = Circuit("AnalogInverter1 Test")
        circuit.subcircuit(AnalogInverter1())
        x = circuit.X(
            "ainv",
            "AnalogInverter1",
            "inCurrentBiasNmos",
            "inCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        )
        self.assertIn("AnalogInverter1", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "AnalogInverter1")

    def test_analog_inverter_2(self):
        circuit = Circuit("AnalogInverter2 Test")
        circuit.subcircuit(AnalogInverter2())
        x = circuit.X(
            "ainv",
            "AnalogInverter2",
            "inCurrentBiasPmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        )
        self.assertIn("AnalogInverter2", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "AnalogInverter2")

    def test_analog_inverter_3(self):
        circuit = Circuit("AnalogInverter3 Test")
        circuit.subcircuit(AnalogInverter3())
        x = circuit.X(
            "ainv",
            "AnalogInverter3",
            "inCurrentBiasPmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        )
        self.assertIn("AnalogInverter3", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "AnalogInverter3")

    def test_analog_inverter_4(self):
        circuit = Circuit("AnalogInverter4 Test")
        circuit.subcircuit(AnalogInverter4())
        x = circuit.X(
            "ainv",
            "AnalogInverter4",
            "inCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        )
        self.assertIn("AnalogInverter4", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "AnalogInverter4")

    def test_analog_inverter_5(self):
        circuit = Circuit("AnalogInverter5 Test")
        circuit.subcircuit(AnalogInverter5())
        x = circuit.X(
            "ainv",
            "AnalogInverter5",
            "inOutputCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasNmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasNmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        )
        self.assertIn("AnalogInverter5", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "AnalogInverter5")

    def test_analog_inverter_6(self):
        circuit = Circuit("AnalogInverter6 Test")
        circuit.subcircuit(AnalogInverter6())
        x = circuit.X(
            "ainv",
            "AnalogInverter6",
            "inOutputCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasNmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasNmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        )
        self.assertIn("AnalogInverter6", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "AnalogInverter6")

    def test_analog_inverter_7(self):
        circuit = Circuit("AnalogInverter7 Test")
        circuit.subcircuit(AnalogInverter7())
        x = circuit.X(
            "ainv",
            "AnalogInverter7",
            "inCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        )
        self.assertIn("AnalogInverter7", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "AnalogInverter7")

    def test_analog_inverter_8(self):
        circuit = Circuit("AnalogInverter8 Test")
        circuit.subcircuit(AnalogInverter8())
        x = circuit.X(
            "ainv",
            "AnalogInverter8",
            "inOutputCurrentBiasNmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasNmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasNmos",
            "innerCurrentBiasPmos",
            "output",
            "sourceCurrentBiasNmos",
            "sourceCurrentBiasPmos",
        )
        self.assertIn("AnalogInverter8", [s.name for s in circuit.subcircuits])
        self.assertEqual(x.subcircuit_name, "AnalogInverter8")


if __name__ == "__main__":
    unittest.main()
