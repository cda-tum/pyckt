from ..HL1.normal_transistor import NormalTransistorP, NormalTransistorN
from PySpice.Spice.Netlist import SubCircuitFactory


# HL2: Differential pair subcircuits
class DifferentialPairP(SubCircuitFactory):
    NAME = "DifferentialPairP"
    NODES = ("input1", "input2", "output1", "output2", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorP", "output1", "input1", "source")
        self.X("M2", "NormalTransistorP", "output2", "input2", "source")


class DifferentialPairN(SubCircuitFactory):
    NAME = "DifferentialPairN"
    NODES = ("input1", "input2", "output1", "output2", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorN", "output1", "input1", "source")
        self.X("M2", "NormalTransistorN", "output2", "input2", "source")
