# from topogen.HL2 import *
# from topogen.HL3 import *
# from topogen.HL3.l import LoadManager
# from topogen.HL3.sb import StageBiasManager
# from topogen.HL3.tc import TransconductanceManager
# from topogen.HL2.inv import InverterManager
from copy import deepcopy
from pathlib import Path
from typing import Iterator, Union

from topogen.common.circuit import *
from topogen.HL2.vb import VoltageBiasManager
from topogen.HL4.inv import InvertingStageManager
from topogen.HL4.non_inv import NonInvertingStageManager
from utils.loguru_loader import setup_logger

logger = setup_logger()

# symmetrical op-amp internal nets
_OUT1FS = "out1fs"          # first-stage output 1 (drives the inverting 2nd stage)
_OUT2FS = "out2fs"          # first-stage output 2 (mirrored by the complementary 2nd stage)
_INNERCOMP = "innercomp"    # complementary-second-stage node biasing the 2nd-stage stage bias


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


def _transconductance_of(secondStage: InvertingStage, tech: str):
    """Deep-copy the *tech*-side current bias of an inverting stage's analog
    inverter — the transconductance acst mirrors as the complementary second
    stage (``OpAmps::getSecondStageTransconductance``)."""
    analog_inverter = secondStage.instances[0]
    for inst in analog_inverter.instances:
        if inst.tech == tech:
            return deepcopy(inst)
    return None


def createSymmetricalOpAmp(
    firstStage: NonInvertingStage,
    secondStage: InvertingStage,
    complementaryTransconductance,
    complementaryBias,
    tc_tech: str,
) -> OpAmp:
    """Assemble a one-stage symmetrical op-amp (acst ``createSymmetricalOpAmp``).

    The differential first stage drives two current-mirror outputs
    (``out1fs``/``out2fs``); the inverting second stage mirrors ``out1fs`` to the
    output, and a complementary second stage (a copy of the second-stage
    transconductance plus a diode voltage bias) mirrors ``out2fs`` through
    ``innercomp`` to bias the second stage's stage bias.  *tc_tech* is the
    transconductance tech (``"n"`` for a p-input first stage).
    """
    rail_tc = OpAmp.SOURCENMOS if tc_tech == "n" else OpAmp.SOURCEPMOS
    rail_bias = OpAmp.SOURCEPMOS if tc_tech == "n" else OpAmp.SOURCENMOS

    op = OpAmp(id=1, techtype="undef")
    op.ports += [
        OpAmp.IN1, OpAmp.IN2, OpAmp.IBIAS, OpAmp.OUT,
        OpAmp.SOURCEPMOS, OpAmp.SOURCENMOS,
    ]
    op.add_instance(firstStage)
    op.add_instance(secondStage)
    op.add_instance(complementaryTransconductance)
    op.add_instance(complementaryBias)

    # first stage → two mirror outputs
    connect((op, OpAmp.IN1), (firstStage, NonInvertingStage.IN1))
    connect((op, OpAmp.IN2), (firstStage, NonInvertingStage.IN2))
    connect((op, OpAmp.SOURCEPMOS), (firstStage, NonInvertingStage.SOURCEPMOS))
    connect((op, OpAmp.SOURCENMOS), (firstStage, NonInvertingStage.SOURCENMOS))
    connect((op, _OUT1FS), (firstStage, NonInvertingStage.OUT1))
    connect((op, _OUT2FS), (firstStage, NonInvertingStage.OUT2))

    # inverting second stage: transconductor senses out1fs, stage bias ← innercomp
    connect((op, OpAmp.OUT), (secondStage, InvertingStage.OUTPUT))
    connect((op, OpAmp.SOURCEPMOS), (secondStage, InvertingStage.SOURCEPMOS))
    connect((op, OpAmp.SOURCENMOS), (secondStage, InvertingStage.SOURCENMOS))
    connect((op, _OUT1FS), (secondStage, InvertingStage.INTRANSCONDUCTANCE))
    connect((op, _INNERCOMP), (secondStage, InvertingStage.INSTAGEBIAS))

    # complementary transconductance mirrors out2fs → innercomp
    connect((op, _OUT2FS), (complementaryTransconductance, CurrentBias.IN))
    connect((op, _INNERCOMP), (complementaryTransconductance, CurrentBias.OUT))
    connect((op, rail_tc), (complementaryTransconductance, CurrentBias.SOURCE))

    # complementary stage bias: diode on innercomp
    connect((op, _INNERCOMP), (complementaryBias, VoltageBias.IN))
    connect((op, _INNERCOMP), (complementaryBias, VoltageBias.OUT))
    connect((op, rail_bias), (complementaryBias, VoltageBias.SOURCE))
    return op


def createSymmetricalOpAmps() -> Iterator[OpAmp]:
    """Yield every one-stage symmetrical op-amp (acst ``createSymmetricalOpAmps``).

    For each symmetrical first stage (cases 1–8) and each single-transistor
    inverting second stage of the transconductance tech, mirror the second-stage
    transconductance as the complementary second stage and pair it with each
    one-transistor complementary voltage bias.  (Two-transistor cascode second
    stages are not yet composed.)
    """
    non_inv = NonInvertingStageManager()
    inv = InvertingStageManager()
    vb = VoltageBiasManager()

    for case in range(1, 9):
        input_tech = "p" if case % 2 == 1 else "n"
        tc_tech = "n" if input_tech == "p" else "p"
        bias_tech = "p" if tc_tech == "n" else "n"

        inv_stages = (
            inv.getInvertingStagesNmosTransconductance()
            if tc_tech == "n"
            else inv.getInvertingStagesPmosTransconductance()
        )
        comp_biases = (
            vb.getOneTransistorVoltageBiasesPmos()
            if bias_tech == "p"
            else vb.getOneTransistorVoltageBiasesNmos()
        )

        for firstStage in non_inv.createSymmetricalNonInvertingStages(case):
            for secondStage in inv_stages:
                tc = _transconductance_of(secondStage, tc_tech)
                if tc is None or tc.component_count != 1:
                    continue  # single-transistor transconductance only, for now
                for bias in comp_biases:
                    if bias.component_count != 1:
                        continue
                    yield createSymmetricalOpAmp(
                        deepcopy(firstStage), deepcopy(secondStage),
                        deepcopy(tc), deepcopy(bias), tc_tech,
                    )


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
