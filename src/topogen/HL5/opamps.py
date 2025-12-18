# from src.topogen.HL2 import *
# from src.topogen.HL3 import *
# from src.topogen.HL3.l import LoadManager
# from src.topogen.HL3.sb import StageBiasManager
# from src.topogen.HL3.tc import TransconductanceManager
# from src.topogen.HL2.inv import InverterManager
from src.topogen.HL4.non_inv import NonInvertingStageManager
from src.topogen.HL4.inv import InvertingStageManager
from src.topogen.common.circuit import *


from pathlib import Path
from typing import Callable, Iterator, Union
from itertools import chain
from copy import deepcopy

from src.utils.loguru_loader import setup_logger

logger = setup_logger()


GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL5" / "opamps" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)
GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL5" / "opamps" / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def createSimpleOneStageOpAmps() -> Iterator[OpAmp]:
    for ninv in list(NonInvertingStageManager().createSimpleNonInvertingStages(16)):
        yield createSimpleOpAmp(firstStage=ninv, secondStage=None)


def createSimpleTwoStageOpAmps() -> Iterator[OpAmp]:
    for first_ninv in list(
        NonInvertingStageManager().createSimpleNonInvertingStages(16)
    ):
        for second_inv in list(InvertingStageManager().getInvertingStages()):
            yield createSimpleOpAmp(firstStage=first_ninv, secondStage=second_inv)


def createSimpleOpAmp(
    firstStage: Union[NonInvertingStage, InvertingStage],
    secondStage: Union[NonInvertingStage, InvertingStage, None],
) -> OpAmp:
    opamp = OpAmp(id=1, techtype="undef")
    opamp.ports += [
        OpAmp.IN1,
        OpAmp.IN2,
        OpAmp.IBIAS,
        OpAmp.SOURCEPMOS,
        OpAmp.SOURCENMOS,
    ]
    opamp.add_instance(firstStage)
    if secondStage != None:
        opamp.add_instance(secondStage)

    opamp = connectInstanceTerminalsSimpleOpAmp(opamp, firstStage, secondStage)
    return opamp


def connectInstanceTerminalsSimpleOpAmp(
    opamp: OpAmp,
    firstStage: Union[NonInvertingStage, InvertingStage],
    secondStage: Union[NonInvertingStage, InvertingStage, None],
):
    connect((opamp, OpAmp.IN1), (firstStage, NonInvertingStage.IN1))
    connect((opamp, OpAmp.IN2), (firstStage, NonInvertingStage.IN2))
    connect((opamp, OpAmp.SOURCEPMOS), (firstStage, NonInvertingStage.SOURCEPMOS))
    connect((opamp, OpAmp.SOURCENMOS), (firstStage, NonInvertingStage.SOURCENMOS))

    if secondStage is None:
        connect((opamp, OpAmp.OUT), (firstStage, NonInvertingStage.OUT2))
    else:
        connect((opamp, OpAmp.SOURCEPMOS), (secondStage, InvertingStage.SOURCEPMOS))
        connect((opamp, OpAmp.SOURCENMOS), (secondStage, InvertingStage.SOURCENMOS))
        connect((opamp, OpAmp.OUT), (secondStage, InvertingStage.OUTPUT))
        # connect((opamp, OpAmp.OUT1), (secondStage, InvertingStage.OUTPUT))
    return opamp


if __name__ == "__main__":
    (GALLERY_DOT_DIR / "SimpleOpamps").mkdir(parents=True, exist_ok=True)
    (GALLERY_IMAGE_DIR / "SimpleOpamps").mkdir(parents=True, exist_ok=True)

    case_id = 1
    circuits = list(createSimpleOneStageOpAmps())
    print(f"SimpleOpamps, case: {case_id}, #num={len(circuits)}")
    for circuit_id, opamp in enumerate(circuits, start=1):
        save_graphviz_figure(
            opamp,
            GALLERY_DOT_DIR / f"SimpleOpamps/opamp_{case_id}_{circuit_id}.dot",
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR / f"SimpleOpamps/opamp_{case_id}_{circuit_id}.dot",
            GALLERY_IMAGE_DIR / f"SimpleOpamps/opamp_{case_id}_{circuit_id}.png",
        )

    case_id = 2
    circuits = list(createSimpleTwoStageOpAmps())
    print(f"SimpleOpamps, case: {case_id}, #num={len(circuits)}")
    for circuit_id, opamp in enumerate(circuits, start=1):
        save_graphviz_figure(
            opamp,
            GALLERY_DOT_DIR / f"SimpleOpamps/opamp_{case_id}_{circuit_id}.dot",
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR / f"SimpleOpamps/opamp_{case_id}_{circuit_id}.dot",
            GALLERY_IMAGE_DIR / f"SimpleOpamps/opamp_{case_id}_{circuit_id}.png",
        )
