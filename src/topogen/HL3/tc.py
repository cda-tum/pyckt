from src.topogen.HL3.lp import *
from src.topogen.HL2.vb import *
from src.topogen.HL2.dp import *

from src.topogen.common.circuit import *


from pathlib import Path
from typing import Callable, Iterator
from itertools import chain
from copy import deepcopy

# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "tc" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "tc" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

tc = Transconductance
def connectInstanceTerminalsOfSimpleTransconductance(tc: Transconductance, dp: DiffPair) -> Transconductance:
    connect((tc, Transconductance.INPUT1), (dp, DiffPair.INPUT1))
    connect((tc, Transconductance.INPUT2), (dp, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1), (dp, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2), (dp, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE), (dp, DiffPair.SOURCE))
    return tc

def connectInstanceTerminalsOfFeedbackTransconductance(tc: Transconductance, dp1: DiffPair, dp2: DiffPair) -> Transconductance:
    connect((tc, Transconductance.INPUT1), (dp1, DiffPair.INPUT1))
    connect((tc, Transconductance.INNER), (dp1, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1), (dp1, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2), (dp1, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE_1), (dp1, DiffPair.SOURCE))


    connect((tc, Transconductance.INPUT2), (dp2, DiffPair.INPUT1))
    connect((tc, Transconductance.INNER), (dp2, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1), (dp2, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2), (dp2, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE_2), (dp2, DiffPair.SOURCE))
    return tc

def connectInstanceTerminalsOfComplementaryTransconductance(tc: Transconductance, dp_nmos: DiffPair, dp_pmos: DiffPair) -> Transconductance:
    connect((tc, Transconductance.INPUT1), (dp_nmos, DiffPair.INPUT1))
    connect((tc, Transconductance.INPUT2), (dp_nmos, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1NMOS), (dp_nmos, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2NMOS), (dp_nmos, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE_NMOS), (dp_nmos, DiffPair.SOURCE))


    connect((tc, Transconductance.INPUT1), (dp_pmos, DiffPair.INPUT1))
    connect((tc, Transconductance.INPUT2), (dp_pmos, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1PMOS), (dp_pmos, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2PMOS), (dp_pmos, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE_PMOS), (dp_pmos, DiffPair.SOURCE))
    return tc

def createSimpleTransconductance(differentialPair):
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        Transconductance.OUT1,
        Transconductance.OUT2,
        Transconductance.INPUT1,
        Transconductance.INPUT2,
        Transconductance.SOURCE,
    ]
    tc.add_instance(differentialPair)
    tc = connectInstanceTerminalsOfSimpleTransconductance(tc, differentialPair)
    return tc

def createFeedbackTransconductance(differentialPair)-> Circuit:
    differentialPair1 = deepcopy(differentialPair)
    differentialPair2 = deepcopy(differentialPair)
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        Transconductance.OUT1,
        Transconductance.OUT2,
        Transconductance.INPUT1,
        Transconductance.INPUT2,
        Transconductance.SOURCE_1,
        Transconductance.SOURCE_2,
    ]
    tc.add_instance(differentialPair1)
    tc.add_instance(differentialPair2)

    tc = connectInstanceTerminalsOfFeedbackTransconductance(tc, differentialPair1, differentialPair2)
    return tc

def createComplementaryTransconductance(differentialPairPmos, differentialPairNmos) -> Circuit:
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        Transconductance.OUT1NMOS,
        Transconductance.OUT2NMOS,
        Transconductance.OUT1PMOS,
        Transconductance.OUT2PMOS,
        Transconductance.INPUT1,
        Transconductance.INPUT2,
        Transconductance.SOURCE_PMOS,
        Transconductance.SOURCE_NMOS,
    ]
    tc.add_instance(differentialPairPmos)
    tc.add_instance(differentialPairNmos)
    tc = connectInstanceTerminalsOfComplementaryTransconductance(tc, differentialPairNmos, differentialPairPmos)
    return tc

class TransconductanceManager:
    def __init__(self):
        self.initializeTransconductances()
    
    def createSimpleTransconductance(self) -> Iterator[Circuit]:
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()
        return iter([createSimpleTransconductance(differentialPairPmos), createSimpleTransconductance(differentialPairNmos)])
    
    def createFeedbackTransconductance(self) -> Iterator[Circuit]:
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()
        return iter([createFeedbackTransconductance(differentialPairPmos), createFeedbackTransconductance(differentialPairNmos)])
    
    def createComplementaryTransconductance(self) -> Iterator[Circuit]:
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()
        return iter([createComplementaryTransconductance(differentialPairPmos, differentialPairNmos)])

    def getComplementaryTransconductance(self) -> Iterator[Circuit]:
        return self.createComplementaryTransconductance()
    
    def getSimpleTransconductancePmos(self) -> Iterator[Transconductance]:
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        return createSimpleTransconductance(differentialPairPmos)

    def getSimpleTransconductanceNmos(self) -> Iterator[Transconductance]:
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()
        return createSimpleTransconductance(differentialPairNmos)
    
    def initializeTransconductances(self):
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()

        # initial all
        self.simpleTransconductancePmos_ = createSimpleTransconductance(differentialPairPmos)
        self.simpleTransconductanceNmos_ = createSimpleTransconductance(differentialPairNmos)

        self.feedbackTransconductancePmos_ = createFeedbackTransconductance(differentialPairPmos)
        self.feedbackTransconductanceNmos_ = createFeedbackTransconductance(differentialPairNmos)

        self.complementaryTransconductance_ = createComplementaryTransconductance(differentialPairPmos, differentialPairNmos)
        

    def getFeedbackTransconductanceNmos(self) -> Iterator[Transconductance]:
        return self.feedbackTransconductanceNmos_
    
    def getFeedbackTransconductancePmos(self) -> Iterator[Transconductance]:
        return self.feedbackTransconductancePmos_



if __name__ == "__main__":
    mng = TransconductanceManager()
    methods: list[Callable[[], Iterator[Circuit]]] = [
        mng.createSimpleTransconductance,
        mng.createFeedbackTransconductance,
        mng.createComplementaryTransconductance,
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
