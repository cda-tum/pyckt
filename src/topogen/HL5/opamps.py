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


def _bias_cell_of(secondStage: InvertingStage, tech: str):
    """The *tech*-side current bias of an inverting stage's analog inverter
    (transconductance if same tech as the stage, else the stage bias)."""
    analog_inverter = secondStage.instances[0]
    for inst in analog_inverter.instances:
        if inst.tech == tech:
            return inst
    return None


def _transconductance_of(secondStage: InvertingStage, tech: str):
    """Deep-copy the transconductance current bias (``getSecondStageTransconductance``)."""
    cell = _bias_cell_of(secondStage, tech)
    return deepcopy(cell) if cell is not None else None


def _is_single_diode(vb) -> bool:
    return len(vb.instances) == 1 and vb.instances[0].name == "dt"


def _floating_gate_count(vb) -> int:
    leaves = deepcopy(vb).flatten().instances
    drains = {t.drain for t in leaves}
    return len({t.gate for t in leaves if t.gate not in drains})


def _complementary_biases(stage_bias_cell, one_transistor_biases, all_biases):
    """acst ``findComplementarySecondStageStageBiases`` — pick the complementary
    stage-bias voltage biases matching the second stage's stage-bias structure."""
    sb_size = stage_bias_cell.component_count
    source_is_diode = stage_bias_cell.instances[0].name == "dt"
    out = []
    if sb_size == 1:
        for vb in one_transistor_biases:
            if _is_single_diode(vb):
                out.append(vb)
    elif source_is_diode:
        for vb in all_biases:
            output_is_diode = vb.instances[-1].name == "dt"
            if output_is_diode and _floating_gate_count(vb) == 1:
                out.append(vb)
            elif vb.component_count == 1 and not _is_single_diode(vb):
                out.append(vb)
    else:
        for vb in all_biases:
            output_is_diode = vb.instances[-1].name == "dt"
            if not (output_is_diode and _floating_gate_count(vb) == 1) and vb.component_count == 2:
                out.append(vb)
            elif _is_single_diode(vb):
                out.append(vb)
    return out


# symmetrical composition nets (acst OpAmps net names)
_INSOURCE_TC = "insourcetc"          # INSOURCETRANSCONDUCTANCECOMPLEMENTARYSECONDSTAGE
_INOUTPUT_TC = "inoutputtc"          # INOUTPUTTRANSCONDUCTANCECOMPLEMENTARYSECONDSTAGE
_INSTAGEBIAS = "instagebias"         # INSTAGEBIASCOMPLEMENTARYSECONDSTAGE
_INSOURCE_SB = "insourcestagebias"   # INSOURCESTAGEBIASCOMPLEMENTARYSECONDSTAGE
_INOUTPUT_SB = "inoutputstagebias"   # INOUTPUTSTAGEBIASCOMPLEMENTARYSECONDSTAGE


def createSymmetricalOpAmp(
    firstStage: NonInvertingStage,
    secondStage: InvertingStage,
    complementaryTransconductance,
    complementaryBias,
    tc_tech: str,
    tc_size: int,
    sb_size: int,
    load_size: int = 2,
    load_stack_floating: int = 0,
) -> OpAmp:
    """Assemble a one-stage symmetrical op-amp (acst ``createSymmetricalOpAmp`` /
    ``connectInstanceTerminalsSymmetricalOpAmp``) for a simple (2-transistor)
    first-stage load.

    The differential first stage drives two mirror outputs (``out1``/``out2``);
    the inverting second stage senses ``out1`` and the complementary second
    stage (a copy of the second-stage transconductance + a voltage bias) mirrors
    ``out2`` through ``innercomp``.  Transconductance and stage-bias wiring
    branch on their transistor counts (*tc_size* = complementary transconductance,
    *sb_size* = second-stage stage bias), matching acst's size-keyed sub-cases.
    """
    rail_tc = OpAmp.SOURCENMOS if tc_tech == "n" else OpAmp.SOURCEPMOS
    rail_bias = OpAmp.SOURCEPMOS if tc_tech == "n" else OpAmp.SOURCENMOS
    bias_size = complementaryBias.component_count
    bias_is_diode = _is_single_diode(complementaryBias)

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
    if load_size == 2:
        connect((op, _OUT1FS), (firstStage, NonInvertingStage.OUT1))
        connect((op, _OUT2FS), (firstStage, NonInvertingStage.OUT2))

    # second stage output + rails; complementary transconductance/bias rails
    connect((op, OpAmp.OUT), (secondStage, InvertingStage.OUTPUT))
    connect((op, OpAmp.SOURCEPMOS), (secondStage, InvertingStage.SOURCEPMOS))
    connect((op, OpAmp.SOURCENMOS), (secondStage, InvertingStage.SOURCENMOS))
    connect((op, rail_tc), (complementaryTransconductance, CurrentBias.SOURCE))
    connect((op, rail_bias), (complementaryBias, VoltageBias.SOURCE))

    # complementary second stage feeds innercomp
    connect((op, _INNERCOMP), (complementaryTransconductance, CurrentBias.OUT))
    connect((op, _INNERCOMP), (complementaryBias, VoltageBias.IN))

    # ---- transconductance wiring (senses out1 / mirrors out2) --------------
    if load_size == 2 and tc_size == 1:
        connect((op, _OUT1FS), (secondStage, InvertingStage.INTRANSCONDUCTANCE))
        connect((op, _OUT2FS), (complementaryTransconductance, CurrentBias.IN))
    elif load_size == 2:  # two-transistor cascode transconductance
        connect((op, _OUT1FS), (secondStage, InvertingStage.INSOURCETRANSCONDUCTANCE))
        connect((op, _INOUTPUT_TC), (secondStage, InvertingStage.INOUTPUTTRANSCONDUCTANCE))
        connect((op, _OUT2FS), (complementaryTransconductance, CurrentBias.INSOURCE))
        connect((op, _INOUTPUT_TC), (complementaryTransconductance, CurrentBias.INOUTPUT))
    else:
        # cascode first-stage load (acst else-branch, OpAmps.cpp:848-869):
        # the second stage senses the two cascode nodes of load branch 1
        # (OutSource1/OutOutput1); the complementary transconductance mirrors
        # branch 2 (OutSource2/OutOutput2), with the OUTOUTPUT2 sub-case picked
        # by the load stack's floating-gate count.
        connect((op, _OUT1FS), (firstStage, NonInvertingStage.OUTSOURCE1LOAD1))
        connect((op, _OUT2FS), (firstStage, NonInvertingStage.OUTOUTPUT1LOAD1))
        connect((op, _OUT1FS), (secondStage, InvertingStage.INSOURCETRANSCONDUCTANCE))
        connect((op, _OUT2FS), (secondStage, InvertingStage.INOUTPUTTRANSCONDUCTANCE))
        connect((op, _INSOURCE_TC), (firstStage, NonInvertingStage.OUTSOURCE2LOAD1))
        connect((op, _INSOURCE_TC), (complementaryTransconductance, CurrentBias.INSOURCE))
        if load_stack_floating == 1:
            connect((op, _OUT2FS), (firstStage, NonInvertingStage.OUTOUTPUT2LOAD1))
            connect((op, _OUT2FS), (complementaryTransconductance, CurrentBias.INOUTPUT))
        else:
            connect((op, _INOUTPUT_TC), (firstStage, NonInvertingStage.OUTOUTPUT2LOAD1))
            connect((op, _INOUTPUT_TC), (complementaryTransconductance, CurrentBias.INOUTPUT))

    # ---- stage-bias wiring -------------------------------------------------
    if bias_size == 1:
        connect((op, _INSTAGEBIAS), (complementaryBias, VoltageBias.OUT))
        if sb_size == 1:
            connect((op, _INSTAGEBIAS), (secondStage, InvertingStage.INSTAGEBIAS))
        else:
            connect((op, _INSTAGEBIAS), (secondStage, InvertingStage.INSOURCESTAGEBIAS))
            if not bias_is_diode:
                connect((op, _INNERCOMP), (secondStage, InvertingStage.INOUTPUTSTAGEBIAS))
    else:  # two-transistor complementary bias
        connect((op, _INSOURCE_SB), (complementaryBias, VoltageBias.OUTSOURCE))
        connect((op, _INOUTPUT_SB), (complementaryBias, VoltageBias.OUTINPUT))
        connect((op, _INSOURCE_SB), (secondStage, InvertingStage.INSOURCESTAGEBIAS))
        connect((op, _INOUTPUT_SB), (secondStage, InvertingStage.INOUTPUTSTAGEBIAS))
    return op


def createSymmetricalOpAmps() -> Iterator[OpAmp]:
    """Yield every one-stage symmetrical op-amp for a simple (2-transistor)
    first-stage load (acst ``createSymmetricalOpAmps``).

    For each such symmetrical first stage and each inverting second stage of the
    transconductance tech passing the ``≥ 0.5 × load`` filter, mirror the
    second-stage transconductance as the complementary second stage and pair it
    with each complementary voltage bias (``findComplementarySecondStageStageBiases``).
    Cascode (>2-transistor) first-stage loads are not yet composed.
    """
    non_inv = NonInvertingStageManager()
    inv = InvertingStageManager()
    vb = VoltageBiasManager()

    for case in range(1, 9):
        input_tech = "p" if case % 2 == 1 else "n"
        tc_tech = "n" if input_tech == "p" else "p"
        bias_tech = "p" if tc_tech == "n" else "n"

        inv_stages = list(
            inv.getInvertingStagesNmosTransconductance()
            if tc_tech == "n"
            else inv.getInvertingStagesPmosTransconductance()
        )
        one_transistor_biases = list(
            vb.getOneTransistorVoltageBiasesPmos()
            if bias_tech == "p"
            else vb.getOneTransistorVoltageBiasesNmos()
        )
        all_biases = list(
            vb.getAllVoltageBiasesPmos()
            if bias_tech == "p"
            else vb.getAllVoltageBiasesNmos()
        )

        for firstStage in non_inv.createSymmetricalNonInvertingStages(case):
            load_size = _symmetrical_load_size(firstStage)
            load_floating = _symmetrical_load_stack_floating(firstStage)
            for secondStage in inv_stages:
                tc = _bias_cell_of(secondStage, tc_tech)
                if tc is None or 2 * tc.component_count < load_size:
                    continue  # acst's ≥ 0.5 × load filter
                sb = _bias_cell_of(secondStage, bias_tech)
                for bias in _complementary_biases(sb, one_transistor_biases, all_biases):
                    yield createSymmetricalOpAmp(
                        deepcopy(firstStage), deepcopy(secondStage),
                        _transconductance_of(secondStage, tc_tech), deepcopy(bias),
                        tc_tech, tc.component_count, sb.component_count,
                        load_size, load_floating,
                    )


def _symmetrical_load_size(firstStage: NonInvertingStage) -> int:
    """Total transistor count of the symmetrical first stage's load (acst's
    ``getDeviceNamesOfFlatCircuit(load).size()`` — 2 for the simple two-diode
    load, 4+ for cascode loads)."""
    for inst in firstStage.instances:
        if inst.name == "l":
            return inst.component_count
    return 0


def _symmetrical_load_stack_floating(firstStage: NonInvertingStage) -> int:
    """Per-branch count of the first-stage load's gate nets not tied to a drain
    (acst ``load.LOADPART1.TRANSISTORSTACK1.getGateNetsNotConnectedToADrain()``).

    The symmetrical load has two identical branches; flatten the whole load,
    count its floating gates, and halve — a diode cascode yields 0, a biased
    cascode top yields 1.  Selects acst's ``OUTOUTPUT2LOAD1`` sub-wiring.
    """
    for inst in firstStage.instances:
        if inst.name == "l":
            flat = deepcopy(inst).flatten()
            drains = {t.drain for t in flat.instances}
            floating = {t.gate for t in flat.instances if t.gate not in drains}
            return len(floating) // 2
    return 0


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
