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


def connectInstanceTerminalsOfSimpleTransconductance(tc: Circuit, differentialPair: Circuit) -> Circuit:
    connect((tc, "input1"), (differentialPair, "input1"))
    connect((tc, "input2"), (differentialPair, "input2"))
    connect((tc, "out1"), (differentialPair, "output1"))
    connect((tc, "out2"), (differentialPair, "output2"))
    connect((tc, "source"), (differentialPair, "source"))
    return tc

def connectInstanceTerminalsOfFeedbackTransconductance(tc: Circuit, differentialPair1: Circuit, differentialPair2: Circuit) -> Circuit:
    connect((tc, "input1"), (differentialPair1, "input1"))
    connect((tc, "inner"), (differentialPair1, "input2"))
    connect((tc, "out1"), (differentialPair1, "output1"))
    connect((tc, "out2"), (differentialPair1, "output2"))
    connect((tc, "source1"), (differentialPair1, "source"))


    connect((tc, "input2"), (differentialPair2, "input1"))
    connect((tc, "inner"), (differentialPair2, "input2"))
    connect((tc, "out1"), (differentialPair2, "output1"))
    connect((tc, "out2"), (differentialPair2, "output2"))
    connect((tc, "source2"), (differentialPair2, "source"))
    return tc

def connectInstanceTerminalsOfComplementaryTransconductance(tc: Circuit, differentialPairNmos: Circuit, differentialPairPmos: Circuit) -> Circuit:
    connect((tc, "input1"), (differentialPairNmos, "input1"))
    connect((tc, "input2"), (differentialPairNmos, "input2"))
    connect((tc, "out1_nmos"), (differentialPairNmos, "output1"))
    connect((tc, "out2_nmos"), (differentialPairNmos, "output2"))
    connect((tc, "source_nmos"), (differentialPairNmos, "source"))


    connect((tc, "input1"), (differentialPairPmos, "input1"))
    connect((tc, "input2"), (differentialPairPmos, "input2"))
    connect((tc, "out1_pmos"), (differentialPairPmos, "output1"))
    connect((tc, "out2_pmos"), (differentialPairPmos, "output2"))
    connect((tc, "source_pmos"), (differentialPairPmos, "source"))
    return tc

def createSimpleTransconductance(differentialPair):
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        "out1",
        "out2",
        "input1",
        "input2",
        "source",
    ]
    tc.add_instance(differentialPair)
    tc = connectInstanceTerminalsOfSimpleTransconductance(tc, differentialPair)
    return tc

def createFeedbackTransconductance(differentialPair)-> Circuit:
    differentialPair1 = deepcopy(differentialPair)
    differentialPair2 = deepcopy(differentialPair)
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        "out1",
        "out2",
        "input1",
        "input2",
        "source1",
        "source2",
    ]
    tc.add_instance(differentialPair1)
    tc.add_instance(differentialPair2)

    tc = connectInstanceTerminalsOfFeedbackTransconductance(tc, differentialPair1, differentialPair2)
    return tc

def createComplementaryTransconductance(differentialPairPmos, differentialPairNmos) -> Circuit:
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        "out1_nmos",
        "out2_nmos",
        "out1_pmos",
        "out2_pmos",
        "input1",
        "input2",
        "source_pmos",
        "source_nmos",
    ]
    tc.add_instance(differentialPairPmos)
    tc.add_instance(differentialPairNmos)
    tc = connectInstanceTerminalsOfComplementaryTransconductance(tc, differentialPairNmos, differentialPairPmos)
    return tc

class TransconductanceManager:
    def __init__(self):
        pass
    
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
