from PySpice.Spice.Netlist import SubCircuitFactory
from pyckt.topology.HL1.normal_transistor import NormalTransistorP, NormalTransistorN
from pyckt.topology.HL1.diode_transistor import DiodeTransistorP, DiodeTransistorN


# VoltageBias[p, 1]
class VoltageBiasP1(SubCircuitFactory):
    NAME = "VoltageBiasP1"
    NODES = ("in", "out", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorP", "in", "out", "source")


# VoltageBias[p, 2]
class VoltageBiasP2(SubCircuitFactory):
    NAME = "VoltageBiasP2"
    NODES = ("in", "out", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "DiodeTransistorP", "in", "out", "source")


# VoltageBias[p, 3]
class VoltageBiasP3(SubCircuitFactory):
    NAME = "VoltageBiasP3"
    NODES = ("in", "inner", "outInput", "outSource", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "DiodeTransistorP", "in", "outInput", "inner")
        self.X("M2", "DiodeTransistorP", "inner", "outSource", "source")


# VoltageBias[p, 4]
class VoltageBiasP4(SubCircuitFactory):
    NAME = "VoltageBiasP4"
    NODES = ("in", "inner", "outInput", "outSource", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorP", "in", "outInput", "inner")
        self.X("M2", "NormalTransistorP", "inner", "in", "source")


# VoltageBias[p, 5]
class VoltageBiasP5(SubCircuitFactory):
    NAME = "VoltageBiasP5"
    NODES = ("in", "inner", "outInput", "outSource", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "DiodeTransistorP", "in", "outInput", "inner")
        self.X("M2", "NormalTransistorP", "inner", "outSource", "source")


# VoltageBias[p, 6]
class VoltageBiasP6(SubCircuitFactory):
    NAME = "VoltageBiasP6"
    NODES = ("in", "inner", "outInput", "outSource", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "DiodeTransistorP", "in", "outInput", "inner")
        self.X("M2", "NormalTransistorP", "inner", "in", "source")


# VoltageBias[n, 1]
class VoltageBiasN1(SubCircuitFactory):
    NAME = "VoltageBiasN1"
    NODES = ("in", "out", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorN", "in", "out", "source")


# VoltageBias[n, 2]
class VoltageBiasN2(SubCircuitFactory):
    NAME = "VoltageBiasN2"
    NODES = ("in", "out", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "DiodeTransistorN", "in", "out", "source")


# VoltageBias[n, 3]
class VoltageBiasN3(SubCircuitFactory):
    NAME = "VoltageBiasN3"
    NODES = ("in", "inner", "outInput", "outSource", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "DiodeTransistorN", "in", "outInput", "inner")
        self.X("M2", "DiodeTransistorN", "inner", "outSource", "source")


# VoltageBias[n, 4]
class VoltageBiasN4(SubCircuitFactory):
    NAME = "VoltageBiasN4"
    NODES = ("in", "inner", "outInput", "outSource", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorN", "in", "outInput", "inner")
        self.X("M2", "NormalTransistorN", "inner", "in", "source")


# VoltageBias[n, 5]
class VoltageBiasN5(SubCircuitFactory):
    NAME = "VoltageBiasN5"
    NODES = ("in", "inner", "outInput", "outSource", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "DiodeTransistorN", "in", "outInput", "inner")
        self.X("M2", "NormalTransistorN", "inner", "outSource", "source")


# VoltageBias[n, 6]
class VoltageBiasN6(SubCircuitFactory):
    NAME = "VoltageBiasN6"
    NODES = ("in", "inner", "outInput", "outSource", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "DiodeTransistorN", "in", "outInput", "inner")
        self.X("M2", "NormalTransistorN", "inner", "in", "source")
