from src.topogen.common.circuit import *
from itertools import chain
from typing import Union, Iterator
from copy import deepcopy

GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "vb" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "vb" / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


class VoltageBiasManager:
    """For voltage bias subcircuit, all transistors in the VB has the same type (NMOS, PMOS)"""

    def __init__(self):
        self.initializeOneTransistorVoltageBiasesNmos()
        self.initializeOneTransistorVoltageBiasesPmos()
        self.initializeTwoTransistorVoltageBiasesNmos()
        self.initializeTwoTransistorVoltageBiasesPmos()

    def getAllVoltageBiasesPmos(self) -> Iterator[VoltageBias]:
        return chain(
            self.oneTransistorVoltageBiasesPmos_, self.twoTransistorVoltageBiasesPmos_
        )

    def getAllVoltageBiasesNmos(self) -> Iterator[VoltageBias]:
        return chain(
            self.oneTransistorVoltageBiasesNmos_, self.twoTransistorVoltageBiasesNmos_
        )

    def getDiodeTransistorVoltageBiasNmos(self) -> VoltageBias:
        for vb in self.oneTransistorVoltageBiasesNmos_:
            if vb.isSingleDiodeTransistor:
                return vb

    def getDiodeTransistorVoltageBiasPmos(self) -> VoltageBias:
        for vb in self.oneTransistorVoltageBiasesPmos_:
            if vb.isSingleDiodeTransistor:
                return vb

    def getTwoDiodeTransistorVoltageBiasNmos(self) -> VoltageBias:
        for vb in self.getTwoTransistorVoltageBiasesNmos():
            if vb.instances[0].name == "dt" and vb.instances[1].name == "dt":
                return vb

    def getTwoDiodeTransistorVoltageBiasPmos(self) -> VoltageBias:
        for vb in self.getTwoTransistorVoltageBiasesPmos():
            if vb.instances[0].name == "dt" and vb.instances[1].name == "dt":
                return vb

    def getOneTransistorVoltageBiasesPmos(self):
        return self.oneTransistorVoltageBiasesPmos_

    def getTwoTransistorVoltageBiasesPmos(self):
        return self.twoTransistorVoltageBiasesPmos_

    def getOneTransistorVoltageBiasesNmos(self):
        return self.oneTransistorVoltageBiasesNmos_

    def getTwoTransistorVoltageBiasesNmos(self):
        return self.twoTransistorVoltageBiasesNmos_

    def initializeOneTransistorVoltageBiasesPmos(self) -> None:
        normalTransistorPmos = NormalTransistor(techtype="p")
        diodeTransistorPmos = DiodeTransistor(techtype="p")
        self.oneTransistorVoltageBiasesPmos_ = self.createOneTransistorVoltageBiases(
            normalTransistorPmos, diodeTransistorPmos
        )

    def initializeTwoTransistorVoltageBiasesPmos(self) -> None:
        normalTransistorPmos = NormalTransistor(techtype="p")
        diodeTransistorPmos = DiodeTransistor(techtype="p")
        self.twoTransistorVoltageBiasesPmos_ = self.createTwoTransistorVoltageBiases(
            normalTransistorPmos, diodeTransistorPmos
        )

    def initializeOneTransistorVoltageBiasesNmos(self) -> None:
        normalTransistorNmos = NormalTransistor(techtype="n")
        diodeTransistorNmos = DiodeTransistor(techtype="n")
        self.oneTransistorVoltageBiasesNmos_ = list(
            self.createOneTransistorVoltageBiases(
                normalTransistorNmos, diodeTransistorNmos
            )
        )

    def initializeTwoTransistorVoltageBiasesNmos(self) -> None:
        normalTransistorNmos = NormalTransistor(techtype="n")
        diodeTransistorNmos = DiodeTransistor(techtype="n")
        self.twoTransistorVoltageBiasesNmos_ = list(
            self.createTwoTransistorVoltageBiases(
                normalTransistorNmos, diodeTransistorNmos
            )
        )

    def createOneTransistorVoltageBiases(
        self, normalTransistor: NormalTransistor, diodeTransistor: DiodeTransistor
    ) -> Iterator[VoltageBias]:
        firstOneTransistorVoltageBias = self.createOneTransistorCircuit(
            normalTransistor
        )
        secondOneTransistorVoltageBias = self.createOneTransistorCircuit(
            diodeTransistor
        )
        return chain([firstOneTransistorVoltageBias, secondOneTransistorVoltageBias])

    def createTwoTransistorVoltageBiases(
        self, normalTransistor: NormalTransistor, diodeTransistor: DiodeTransistor
    ) -> Iterator[VoltageBias]:
        diodeTransistor1 = deepcopy(diodeTransistor)
        diodeTransistor2 = deepcopy(diodeTransistor)

        diodeTransistor1.id = 1
        diodeTransistor2.id = 1

        normalTransistor1 = deepcopy(normalTransistor)
        normalTransistor2 = deepcopy(normalTransistor)
        normalTransistor1.id = 1
        normalTransistor2.id = 2
        twoDiodeTransistorCircuit = self.createTwoTransistorCircuit(
            diodeTransistor1, diodeTransistor2
        )
        twoNormalTransistorCircuit = self.createTwoTransistorCircuit(
            normalTransistor1, normalTransistor2
        )
        mixedCircuits = self.createTwoTransistorCircuit(
            normalTransistor, diodeTransistor
        )
        return chain(
            [twoDiodeTransistorCircuit, twoNormalTransistorCircuit, mixedCircuits]
        )

    def createOneTransistorCircuit(self, instance: Circuit) -> VoltageBias:
        vb = VoltageBias(id=1, techtype=instance.tech)
        vb.ports = [VoltageBias.IN, VoltageBias.SOURCE, VoltageBias.OUT]
        vb.add_instance(instance)
        vb = self.connectInstanceTerminalsOneTransistorVoltageBias(vb, instance)
        return vb

    def createTwoTransistorCircuit(
        self, sourceTransistor: Circuit, outputTransistor: Circuit
    ) -> Union[VoltageBias, None]:
        if outputTransistor.name == "dt":
            vb = VoltageBias(id=1, techtype=sourceTransistor.tech)
            vb.ports = [
                VoltageBias.IN,
                VoltageBias.SOURCE,
                VoltageBias.INNER,
                VoltageBias.OUTSOURCE,
                VoltageBias.OUTINPUT,
            ]
            vb.add_instance(sourceTransistor)
            vb.add_instance(outputTransistor)
            vb = self.connectInstanceTerminalsTwoTransistorVoltageBias(
                vb, sourceTransistor, outputTransistor
            )
            return vb
        if sourceTransistor.name == "nt":
            vb = VoltageBias(id=1, techtype=sourceTransistor.tech)
            vb.ports = [
                VoltageBias.IN,
                VoltageBias.SOURCE,
                VoltageBias.INNER,
                VoltageBias.OUTINPUT,
            ]
            vb.add_instance(sourceTransistor)
            vb.add_instance(outputTransistor)
            vb = self.connectInstanceTerminalsTwoTransistorVoltageBias(
                vb, sourceTransistor, outputTransistor
            )
            return vb
        return None

    def connectInstanceTerminalsOneTransistorVoltageBias(
        self, vb: VoltageBias, transistor: Circuit
    ) -> VoltageBias:
        connect((vb, VoltageBias.OUT), (transistor, "gate"))
        connect((vb, VoltageBias.IN), (transistor, "drain"))
        connect((vb, VoltageBias.SOURCE), (transistor, "source"))
        return vb

    def connectInstanceTerminalsTwoTransistorVoltageBias(
        self, vb: VoltageBias, sourceTransistor: Circuit, outputTransistor: Circuit
    ) -> VoltageBias:
        if VoltageBias.OUTSOURCE in vb.ports:
            connect((vb, VoltageBias.OUTSOURCE), (sourceTransistor, "gate"))
        else:
            connect((vb, VoltageBias.IN), (sourceTransistor, "gate"))

        connect((vb, VoltageBias.INNER), (sourceTransistor, "drain"))
        connect((vb, VoltageBias.SOURCE), (sourceTransistor, "source"))

        connect((vb, VoltageBias.OUTINPUT), (outputTransistor, "gate"))
        connect((vb, VoltageBias.IN), (outputTransistor, "drain"))
        connect((vb, VoltageBias.INNER), (outputTransistor, "source"))
        return vb


if __name__ == "__main__":
    vb_mng = VoltageBiasManager()
    all_vb = list(vb_mng.getAllVoltageBiasesNmos()) + list(
        vb_mng.getAllVoltageBiasesPmos()
    )

    case_id = 0
    for circuit_id, circuit in enumerate(all_vb):
        print(circuit)
        save_graphviz_figure(
            circuit, filename=GALLERY_DOT_DIR / f"vb_{case_id}_{circuit_id}.dot"
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR / f"vb_{case_id}_{circuit_id}.dot",
            GALLERY_IMAGE_DIR / f"vb_{case_id}_{circuit_id}.png",
        )
