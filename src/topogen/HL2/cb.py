from src.topogen.common.circuit import *

from copy import deepcopy
from itertools import chain
from typing import Iterator

GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "cb" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "cb" / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


class CurrentBiasManager:

    def __init__(self):
        self.initializeOneTransistorCurrentBiasesNmos()
        self.initializeOneTransistorCurrentBiasesPmos()
        self.initializeTwoTransistorCurrentBiasesNmos()
        self.initializeTwoTransistorCurrentBiasesPmos()

    def getAllCurrentBiasesPmos(self) -> list[CurrentBias]:
        return [self.oneTransistorCurrentBiasesPmos_] + list(
            self.twoTransistorCurrentBiasesPmos_
        )

    def getAllCurrentBiasesNmos(self) -> list[CurrentBias]:
        return [self.oneTransistorCurrentBiasesNmos_] + list(
            self.twoTransistorCurrentBiasesNmos_
        )

    def getOneTransistorCurrentBiasesPmos(self) -> list[CurrentBias]:
        return [self.oneTransistorCurrentBiasesPmos_]

    def getTwoTransistorCurrentBiasesPmos(self) -> list[CurrentBias]:
        return list(self.twoTransistorCurrentBiasesPmos_)

    def getOneTransistorCurrentBiasesNmos(self) -> list[CurrentBias]:
        return self.oneTransistorCurrentBiasesNmos_

    def getTwoTransistorCurrentBiasesNmos(self) -> list[CurrentBias]:
        return list(self.twoTransistorCurrentBiasesNmos_)

    def getNormalTransistorCurrentBias(self, techtype: str):
        if techtype == "n":
            for cb in self.oneTransistorCurrentBiasesNmos_:
                if len(cb.instances) == 1 and cb.instances[0].name == "nt":
                    return cb
        else:
            for cb in self.oneTransistorCurrentBiasesPmos_:
                if len(cb.instances) == 1 and cb.instances[0].name == "nt":
                    return cb

    def initializeOneTransistorCurrentBiasesPmos(self):
        normalTransistor = NormalTransistor(techtype="p")
        self.oneTransistorCurrentBiasesPmos_ = self.createOneTransistorCurrentBias(
            normalTransistor
        )

    def initializeTwoTransistorCurrentBiasesPmos(self):
        normalTransistorPmos = NormalTransistor(techtype="p")
        diodeTransistorPmos = DiodeTransistor(techtype="p")
        self.twoTransistorCurrentBiasesPmos_ = self.createTwoTransistorCurrentBias(
            normalTransistorPmos, diodeTransistorPmos
        )

    def initializeOneTransistorCurrentBiasesNmos(self):
        normalTransistor = NormalTransistor(techtype="n")
        self.oneTransistorCurrentBiasesNmos_ = self.createOneTransistorCurrentBias(
            normalTransistor
        )

    def initializeTwoTransistorCurrentBiasesNmos(self):
        normalTransistorNmos = NormalTransistor(techtype="n")
        diodeTransistorNmos = DiodeTransistor(techtype="n")
        self.twoTransistorCurrentBiasesNmos_ = self.createTwoTransistorCurrentBias(
            normalTransistorNmos, diodeTransistorNmos
        )

    def createTwoTransistorCurrentBias(
        self, normalTransistor: Circuit, diodeTransistor: Circuit
    ) -> Iterator[CurrentBias]:
        nt1 = deepcopy(normalTransistor)
        nt2 = deepcopy(normalTransistor)
        nt2.id = 2
        firstTwoTransistorCurrentBias = self.createTwoTransistorCircuit(nt1, nt2)
        secondTwoTransistorCurrentBias = self.createTwoTransistorCircuit(
            diodeTransistor, normalTransistor
        )
        return chain([firstTwoTransistorCurrentBias, secondTwoTransistorCurrentBias])

    def createOneTransistorCurrentBias(self, normalTransistor: Circuit) -> CurrentBias:
        cb = CurrentBias(id=1, techtype=normalTransistor.tech)
        cb.ports = [CurrentBias.IN, CurrentBias.OUT, CurrentBias.SOURCE]
        cb.add_instance(normalTransistor)
        cb = self.connectInstanceTerminalsOneTransistorCurrentBias(cb, normalTransistor)
        return cb

    def createTwoTransistorCircuit(
        self, sourceTransistor: Circuit, outputTransistor: Circuit
    ) -> CurrentBias:
        cb = CurrentBias(id=1, techtype=sourceTransistor.tech)
        cb.ports = [
            CurrentBias.INSOURCE,
            CurrentBias.INOUTPUT,
            CurrentBias.INNER,
            CurrentBias.OUT,
            CurrentBias.SOURCE,
        ]
        cb.add_instance(sourceTransistor)
        cb.add_instance(outputTransistor)
        cb = self.connectInstanceTerminalsTwoTransistorCurrentBias(
            cb, sourceTransistor, outputTransistor
        )
        return cb

    def connectInstanceTerminalsOneTransistorCurrentBias(
        self, cb: CurrentBias, transistor: Circuit
    ) -> CurrentBias:
        connect((cb, CurrentBias.IN), (transistor, "gate"))
        connect((cb, CurrentBias.OUT), (transistor, "drain"))
        connect((cb, CurrentBias.SOURCE), (transistor, "source"))
        return cb

    def connectInstanceTerminalsTwoTransistorCurrentBias(
        self, cb: CurrentBias, sourceTransistor: Circuit, outputTransistor: Circuit
    ) -> CurrentBias:
        connect((cb, CurrentBias.INSOURCE), (sourceTransistor, "gate"))
        connect((cb, CurrentBias.INNER), (sourceTransistor, "drain"))
        connect((cb, CurrentBias.SOURCE), (sourceTransistor, "source"))

        connect((cb, CurrentBias.INOUTPUT), (outputTransistor, "gate"))
        connect((cb, CurrentBias.OUT), (outputTransistor, "drain"))
        connect((cb, CurrentBias.INNER), (outputTransistor, "source"))
        return cb


if __name__ == "__main__":

    cb_mng = CurrentBiasManager()

    all_cb = list(cb_mng.getAllCurrentBiasesNmos()) + list(
        cb_mng.getAllCurrentBiasesPmos()
    )
    case_id = 0
    for circuit_id, circuit in enumerate(all_cb):
        print(circuit)
        save_graphviz_figure(
            circuit, filename=GALLERY_DOT_DIR / f"cb_{case_id}_{circuit_id}.dot"
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR / f"cb_{case_id}_{circuit_id}.dot",
            GALLERY_IMAGE_DIR / f"cb_{case_id}_{circuit_id}.png",
        )
