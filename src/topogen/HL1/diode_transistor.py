from PySpice.Spice.Netlist import SubCircuitFactory


# If not already present, define DiodeTransistorP and DiodeTransistorN
class DiodeTransistorP(SubCircuitFactory):
    NAME = "DiodeTransistorP"
    NODES = ("drain", "gate", "source")

    def __init__(self):
        super().__init__()
        self.M(1, "drain", "drain", "source", "source", model="PMOS")


class DiodeTransistorN(SubCircuitFactory):
    NAME = "DiodeTransistorN"
    NODES = ("drain", "gate", "source")

    def __init__(self):
        super().__init__()
        self.M(1, "drain", "drain", "source", "source", model="NMOS")
