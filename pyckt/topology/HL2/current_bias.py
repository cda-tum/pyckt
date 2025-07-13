from PySpice.Spice.Netlist import SubCircuitFactory
from pyckt.topology.HL1.normal_transistor import NormalTransistorP, NormalTransistorN
from pyckt.topology.HL1.diode_transistor import DiodeTransistorP, DiodeTransistorN


class CurrentBiasP1(SubCircuitFactory):
    NAME = "CurrentBiasP1"
    NODES = ("in", "out", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorP", "out", "in", "source")


class CurrentBiasP2(SubCircuitFactory):
    NAME = "CurrentBiasP2"
    NODES = ("out", "source", "inOutput", "inSource", "inner")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorP", "out", "inOutput", "inner")
        self.X("M2", "NormalTransistorP", "inner", "inSource", "source")


class CurrentBiasP3(SubCircuitFactory):
    NAME = "CurrentBiasP3"
    NODES = ("out", "source", "inOutput", "inSource", "inner")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorP", "out", "inOutput", "inner")
        self.X("M2", "DiodeTransistorP", "inner", "inSource", "source")


class CurrentBiasN1(SubCircuitFactory):
    NAME = "CurrentBiasN1"
    NODES = ("in", "out", "source")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorN", "out", "in", "source")


class CurrentBiasN2(SubCircuitFactory):
    NAME = "CurrentBiasN2"
    NODES = ("out", "source", "inOutput", "inSource", "inner")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorN", "out", "inOutput", "inner")
        self.X("M2", "NormalTransistorN", "inner", "inSource", "source")


class CurrentBiasN3(SubCircuitFactory):
    NAME = "CurrentBiasN3"
    NODES = ("out", "source", "inOutput", "inSource", "inner")

    def __init__(self):
        super().__init__()
        self.X("M1", "NormalTransistorN", "out", "inOutput", "inner")
        self.X("M2", "DiodeTransistorN", "inner", "inSource", "source")
