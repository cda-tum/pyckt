# from topogen.HL2 import *
# from topogen.HL3 import *
# from topogen.HL3.l import LoadManager
# from topogen.HL3.sb import StageBiasManager
# from topogen.HL3.tc import TransconductanceManager
# from topogen.HL2.inv import InverterManager
from pathlib import Path
from typing import Iterator, Union

from topogen.common.circuit import *
from topogen.HL4.inv import InvertingStageManager
from topogen.HL4.non_inv import NonInvertingStageManager
from utils.loguru_loader import setup_logger

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
    """Yield one-stage op-amps, one per non-inverting-stage case 16 variant
    (the last/most-complex ``createSimpleNonInvertingStages`` case), with no
    second stage."""
    for ninv in list(NonInvertingStageManager().createSimpleNonInvertingStages(16)):
        yield createSimpleOpAmp(firstStage=ninv, secondStage=None)


def createSimpleTwoStageOpAmps() -> Iterator[OpAmp]:
    """Yield two-stage op-amps pairing every non-inverting-stage case 16
    variant with every available inverting stage (full cross-product)."""
    for first_ninv in list(
        NonInvertingStageManager().createSimpleNonInvertingStages(16)
    ):
        for second_inv in list(InvertingStageManager().getInvertingStages()):
            yield createSimpleOpAmp(firstStage=first_ninv, secondStage=second_inv)


def createSimpleOpAmp(
    firstStage: Union[NonInvertingStage, InvertingStage],
    secondStage: Union[NonInvertingStage, InvertingStage, None],
) -> OpAmp:
    """Assemble an :class:`OpAmp` from a first (non-inverting) stage and an
    optional second (inverting) stage; one-stage when *secondStage* is ``None``."""
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
    """Wire *firstStage*'s inputs/sources into *opamp*, and either
    *firstStage*'s ``OUT2`` (one-stage) or *secondStage*'s sources/output
    (two-stage) into ``OpAmp.OUT``."""
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


def createFullyDifferentialOpAmp(
    firstStage: NonInvertingStage,
    feedbackStage: NonInvertingStage,
) -> OpAmp:
    """Assemble a one-stage fully-differential op-amp from a differential
    *firstStage* and a common-mode *feedbackStage* (acst
    ``OpAmps::createFullyDifferentialOpAmp`` + ``connectInstanceTerminals``).

    The first stage drives the two differential outputs ``out1``/``out2``; the
    feedback stage senses them (``IN1←out2``, ``IN2←out1``), references
    ``vref`` on its inner transconductance, and its output (``outfeedback``)
    drives the first stage's current-mirror load gate (``InnerLoad1``) — the
    common-mode feedback that biases the first stage's load.
    """
    opamp = OpAmp(id=1, techtype="undef")
    opamp.ports += [
        OpAmp.IN1, OpAmp.IN2, OpAmp.IBIAS,
        OpAmp.OUT1, OpAmp.OUT2, OpAmp.VREF,
        OpAmp.SOURCEPMOS, OpAmp.SOURCENMOS,
    ]
    opamp.add_instance(firstStage)
    opamp.add_instance(feedbackStage)

    # first (differential) stage
    connect((opamp, OpAmp.IN1), (firstStage, NonInvertingStage.IN1))
    connect((opamp, OpAmp.IN2), (firstStage, NonInvertingStage.IN2))
    connect((opamp, OpAmp.SOURCEPMOS), (firstStage, NonInvertingStage.SOURCEPMOS))
    connect((opamp, OpAmp.SOURCENMOS), (firstStage, NonInvertingStage.SOURCENMOS))
    connect((opamp, OpAmp.OUT1), (firstStage, NonInvertingStage.OUT1))
    connect((opamp, OpAmp.OUT2), (firstStage, NonInvertingStage.OUT2))

    # feedback (common-mode) stage
    connect((opamp, OpAmp.OUT2), (feedbackStage, NonInvertingStage.IN1))
    connect((opamp, OpAmp.OUT1), (feedbackStage, NonInvertingStage.IN2))
    connect((opamp, OpAmp.VREF), (feedbackStage, NonInvertingStage.INNERTRANSCONDUCTANCE))
    connect((opamp, OpAmp.SOURCEPMOS), (feedbackStage, NonInvertingStage.SOURCEPMOS))
    connect((opamp, OpAmp.SOURCENMOS), (feedbackStage, NonInvertingStage.SOURCENMOS))

    # common-mode feedback node: feedback-stage output drives the first stage's
    # mirror-load gate (acst connectedLoadInstanceTerminalToFeedbackStage)
    connect((opamp, OpAmp.OUTFEEDBACK), (feedbackStage, NonInvertingStage.OUT2))
    connect((opamp, OpAmp.OUTFEEDBACK), (firstStage, NonInvertingStage.INNERLOAD1))
    return opamp


class OpAmpFactory:
    """Thin wrapper around the module-level op-amp creation functions.

    Provides a class-based interface so that the synthesis generator can
    treat it uniformly alongside the other HL2–HL4 manager classes.
    """

    def create_one_stage_opamps(self) -> list[OpAmp]:
        """Return all simple one-stage op-amps (case 1–16 of NonInvertingStageManager)."""
        return list(createSimpleOneStageOpAmps())

    def create_two_stage_opamps(self) -> list[OpAmp]:
        """Return all simple two-stage op-amps (cases 1–16 × all InvertingStages)."""
        return list(createSimpleTwoStageOpAmps())


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
