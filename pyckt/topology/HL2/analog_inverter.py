from PySpice.Spice.Netlist import SubCircuitFactory
from pyckt.topology.HL2.current_bias import (
    CurrentBiasN1,
    CurrentBiasN2,
    CurrentBiasN3,
    CurrentBiasP1,
    CurrentBiasP2,
    CurrentBiasP3,
)


class AnalogInverter1(SubCircuitFactory):
    NAME = "AnalogInverter1"
    NODES = (
        "inCurrentBiasNmos",
        "inCurrentBiasPmos",
        "output",
        "sourceCurrentBiasNmos",
        "sourceCurrentBiasPmos",
    )

    def __init__(self):
        super().__init__()
        self.X(
            "Nmos",
            "CurrentBiasN1",
            "inCurrentBiasNmos",
            "output",
            "sourceCurrentBiasNmos",
        )
        self.X(
            "Pmos",
            "CurrentBiasP1",
            "inCurrentBiasPmos",
            "output",
            "sourceCurrentBiasPmos",
        )


class AnalogInverter2(SubCircuitFactory):
    NAME = "AnalogInverter2"
    NODES = (
        "inCurrentBiasPmos",
        "inOutputCurrentBiasNmos",
        "inSourceCurrentBiasNmos",
        "innerCurrentBiasNmos",
        "output",
        "sourceCurrentBiasNmos",
        "sourceCurrentBiasPmos",
    )

    def __init__(self):
        super().__init__()
        self.X(
            "Nmos",
            "CurrentBiasN2",
            "output",
            "sourceCurrentBiasNmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
        )
        self.X(
            "Pmos",
            "CurrentBiasP1",
            "inCurrentBiasPmos",
            "output",
            "sourceCurrentBiasPmos",
        )


class AnalogInverter3(SubCircuitFactory):
    NAME = "AnalogInverter3"
    NODES = (
        "inCurrentBiasPmos",
        "inOutputCurrentBiasNmos",
        "inSourceCurrentBiasNmos",
        "innerCurrentBiasNmos",
        "output",
        "sourceCurrentBiasNmos",
        "sourceCurrentBiasPmos",
    )

    def __init__(self):
        super().__init__()
        self.X(
            "Nmos",
            "CurrentBiasN3",
            "output",
            "sourceCurrentBiasNmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
        )
        self.X(
            "Pmos",
            "CurrentBiasP1",
            "inCurrentBiasPmos",
            "output",
            "sourceCurrentBiasPmos",
        )


class AnalogInverter4(SubCircuitFactory):
    NAME = "AnalogInverter4"
    NODES = (
        "inCurrentBiasNmos",
        "inOutputCurrentBiasPmos",
        "inSourceCurrentBiasPmos",
        "innerCurrentBiasPmos",
        "output",
        "sourceCurrentBiasNmos",
        "sourceCurrentBiasPmos",
    )

    def __init__(self):
        super().__init__()
        self.X(
            "Nmos",
            "CurrentBiasN1",
            "inCurrentBiasNmos",
            "output",
            "sourceCurrentBiasNmos",
        )
        self.X(
            "Pmos",
            "CurrentBiasP2",
            "output",
            "sourceCurrentBiasPmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
        )


class AnalogInverter5(SubCircuitFactory):
    NAME = "AnalogInverter5"
    NODES = (
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

    def __init__(self):
        super().__init__()
        self.X(
            "Nmos",
            "CurrentBiasN2",
            "output",
            "sourceCurrentBiasNmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
        )
        self.X(
            "Pmos",
            "CurrentBiasP2",
            "output",
            "sourceCurrentBiasPmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
        )


class AnalogInverter6(SubCircuitFactory):
    NAME = "AnalogInverter6"
    NODES = (
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

    def __init__(self):
        super().__init__()
        self.X(
            "Nmos",
            "CurrentBiasN3",
            "output",
            "sourceCurrentBiasNmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
        )
        self.X(
            "Pmos",
            "CurrentBiasP3",
            "output",
            "sourceCurrentBiasPmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
        )


class AnalogInverter7(SubCircuitFactory):
    NAME = "AnalogInverter7"
    NODES = (
        "inCurrentBiasNmos",
        "inOutputCurrentBiasPmos",
        "inSourceCurrentBiasPmos",
        "innerCurrentBiasPmos",
        "output",
        "sourceCurrentBiasNmos",
        "sourceCurrentBiasPmos",
    )

    def __init__(self):
        super().__init__()
        self.X(
            "Nmos",
            "CurrentBiasN1",
            "inCurrentBiasNmos",
            "output",
            "sourceCurrentBiasNmos",
        )
        self.X(
            "Pmos",
            "CurrentBiasP2",
            "output",
            "sourceCurrentBiasPmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
        )


class AnalogInverter8(SubCircuitFactory):
    NAME = "AnalogInverter8"
    NODES = (
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

    def __init__(self):
        super().__init__()
        self.X(
            "Nmos",
            "CurrentBiasN3",
            "output",
            "sourceCurrentBiasNmos",
            "inOutputCurrentBiasNmos",
            "inSourceCurrentBiasNmos",
            "innerCurrentBiasNmos",
        )
        self.X(
            "Pmos",
            "CurrentBiasP3",
            "output",
            "sourceCurrentBiasPmos",
            "inOutputCurrentBiasPmos",
            "inSourceCurrentBiasPmos",
            "innerCurrentBiasPmos",
        )
