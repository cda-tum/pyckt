from PySpice.Spice.Netlist import SubCircuitFactory


# HL1: Basic transistor subcircuits
class NormalTransistorP(SubCircuitFactory):
    NAME = "NormalTransistorP"
    NODES = ("drain", "gate", "source")

    def __init__(self):
        super().__init__()
        self.M(1, "drain", "gate", "source", "source", model="PMOS")


class NormalTransistorN(SubCircuitFactory):
    NAME = "NormalTransistorN"
    NODES = ("drain", "gate", "source")

    def __init__(self):
        super().__init__()
        self.M(1, "drain", "gate", "source", "source", model="NMOS")
