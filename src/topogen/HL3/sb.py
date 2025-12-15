from src.topogen.HL3.lp import *
from src.topogen.HL2.vb import *
from src.topogen.common.circuit import *


from pathlib import Path
from typing import Callable, Iterator
from itertools import chain


# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "sb" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "sb" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

def connectInstanceTerminalsOfOneTransistorStageBias(stageBias:Circuit, currentBias:Circuit) -> Circuit:
    connect((stageBias, "in"), (currentBias, "in"))
    connect((stageBias, "out"), (currentBias, "out"))
    connect((stageBias, "source"), (currentBias, "source"))
    return stageBias

def connectInstanceTerminalsOfTwoTransistorStageBias(stageBias:Circuit, currentBias:Circuit) -> Circuit:
    connect((stageBias, "inoutput"), (currentBias, "inoutput"))
    connect((stageBias, "insource"), (currentBias, "insource"))
    connect((stageBias, "inner"), (currentBias, "inner"))
    connect((stageBias, "out"), (currentBias, "out"))
    connect((stageBias, "source"), (currentBias, "source"))
    return stageBias

def createOneTransistorStageBias(currentBias) -> Circuit:
    sb = StageBias(id=1, techtype="?")
    sb.ports = [
        "out",
        "in",
        "source",
    ]
    sb.add_instance(currentBias)
    sb = connectInstanceTerminalsOfOneTransistorStageBias(sb, currentBias)
    return sb

def createTwoTransistorStageBias(currentBias) -> Circuit:
    sb = StageBias(id=1, techtype="?")
    sb.ports = [
        "out",
        "inoutput",
        "insource",
        "inner",
        "source",
    ]
    sb.add_instance(currentBias)
    sb = connectInstanceTerminalsOfTwoTransistorStageBias(sb, currentBias)
    return sb

def createOneTransistorStageBiases(oneTransistorCurrentBiases: list[Circuit])->Iterator[Circuit]:
    for currentBias in oneTransistorCurrentBiases:
        yield createOneTransistorStageBias(currentBias)

def createTwoTransistorStageBiases(twoTransistorCurrentBiases) ->Iterator[Circuit]:
    for currentBias in twoTransistorCurrentBiases:
        yield createTwoTransistorStageBias(currentBias)

def initializeStageBiasesPmos():
    oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
    twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
    return chain(createOneTransistorStageBiases(oneTransistorCurrentBiases), createTwoTransistorStageBiases(twoTransistorCurrentBiases))

def initializeStageBiasesNmos():
    oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
    twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
    return chain(createOneTransistorStageBiases(oneTransistorCurrentBiases), createTwoTransistorStageBiases(twoTransistorCurrentBiases))


class StageBiasManager:
    def __init__(self):
        self.initializeStageBiasesPmos()
        self.initializeStageBiasesNmos()
        pass
    def createStageBiasesPmos(self) ->Iterator[Circuit]:
        return initializeStageBiasesPmos()
    def createStageBiasesNmos(self) ->Iterator[Circuit]:
        return initializeStageBiasesNmos()
    
    def getOneTransistorStageBiasesNmos(self) ->Iterator[Circuit]:
        oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        return createOneTransistorStageBiases(oneTransistorCurrentBiases)
    def getTwoTransistorStageBiasesNmos(self) ->Iterator[Circuit]:
        twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        return createTwoTransistorStageBiases(twoTransistorCurrentBiases)
    

    def getOneTransistorStageBiasesPmos(self) ->Iterator[Circuit]:
        oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        return createOneTransistorStageBiases(oneTransistorCurrentBiases)
    def getTwoTransistorStageBiasesPmos(self) ->Iterator[Circuit]:
        twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        return createTwoTransistorStageBiases(twoTransistorCurrentBiases)

    def initializeStageBiasesNmos(self)-> None:
        oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()

        self.oneTransistorBiasesNmos_ = createOneTransistorStageBiases(oneTransistorCurrentBiases)
        self.twoTransistorBiasesNmos_ = createTwoTransistorStageBiases(twoTransistorCurrentBiases)

    def initializeStageBiasesPmos(self)-> None:

        oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()

        self.oneTransistorBiasesPmos_ = createOneTransistorStageBiases(oneTransistorCurrentBiases)
        self.twoTransistorBiasesPmos_ = createTwoTransistorStageBiases(twoTransistorCurrentBiases)


    def getAllStageBiasesNmos(self):
        assert self.oneTransistorBiasesNmos_ is not None
        assert self.twoTransistorBiasesNmos_ is not None
        return  list(self.oneTransistorBiasesNmos_) + list(self.twoTransistorBiasesNmos_)
    
    def getAllStageBiasesPmos(self):
        assert self.oneTransistorBiasesPmos_ is not None
        assert self.twoTransistorBiasesPmos_ is not None
        return  list(self.oneTransistorBiasesPmos_) + list(self.twoTransistorBiasesPmos_)


if __name__ == "__main__":
    mng = StageBiasManager()
    methods: list[Callable[[], Iterator[Circuit]]] = [
        mng.createStageBiasesPmos,
        mng.createStageBiasesNmos,
    ]

    for case_id, create_method in enumerate(methods, start=1):
        circuits = list(create_method())
        print(f"case {case_id}: {create_method.__name__}, len = {len(circuits)}")
        for circuit_id, load in enumerate(circuits, start=1):
            save_graphviz_figure(
                load,
                GALLERY_DOT_DIR / f"l_{case_id}_{circuit_id}.dot",
            )
            convert_dot_to_png(
                GALLERY_DOT_DIR / f"l_{case_id}_{circuit_id}.dot",
                GALLERY_IMAGE_DIR / f"l_{case_id}_{circuit_id}.png",
            )
