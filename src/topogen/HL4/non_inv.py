# from topogen.HL2 import *
# from topogen.HL3 import *
from copy import deepcopy
from pathlib import Path
from typing import Iterator

from topogen.common.circuit import *
from topogen.HL3.l import LoadManager
from topogen.HL3.sb import StageBiasManager
from topogen.HL3.tc import TransconductanceManager
from topogen.HL4.non_inv_connections import *
from topogen.HL4.non_inv_netdef import *
from utils.loguru_loader import setup_logger

logger = setup_logger()


GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL4" / "non_inv" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)
GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "gallery"
    / "HL4"
    / "non_inv"
    / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------
def createSimpleTransconductanceNonInvertingStage(
    transconductance, load, stageBias
) -> NonInvertingStage:
    """Assemble a non-inverting stage from one simple transconductance, one
    load, and one stage bias."""
    stage = NonInvertingStage(id=1, techtype="?")
    stage.ports = [
        NonInvertingStage.OUT1,
        NonInvertingStage.OUT2,
        NonInvertingStage.IN1,
        NonInvertingStage.IN2,
        NonInvertingStage.SOURCETRANSCONDUCTANCE,
        NonInvertingStage.SOURCEPMOS,
        NonInvertingStage.SOURCENMOS,
    ]
    stage.add_instance(transconductance)
    stage.add_instance(load)
    stage.add_instance(stageBias)

    stage = addStageBiasNets(stage, stageBias)
    stage = addLoadNets(stage, load)

    stage = connectInstanceTerminalsOfSimpleTransconductance(stage, transconductance)
    stage = connectInstanceTerminalsOfLoad(stage, load)
    stage = connectInstanceTerminalsOfStageBias(stage, stageBias)

    return stage


def createComplementaryTransconductanceNonInvertingStage(
    transconductance: Transconductance,
    load: Load,
    stageBiasNmos: StageBias,
    stageBiasPmos: StageBias,
) -> NonInvertingStage:
    """Assemble a non-inverting stage from a complementary transconductance,
    a complementary load, and an NMOS+PMOS stage-bias pair."""
    stage = NonInvertingStage(id=1, techtype="?")
    stage.ports = [
        NonInvertingStage.OUT1,
        NonInvertingStage.OUT2,
        NonInvertingStage.IN1,
        NonInvertingStage.IN2,
        NonInvertingStage.SOURCETRANSCONDUCTANCENMOS,
        NonInvertingStage.SOURCETRANSCONDUCTANCEPMOS,
        NonInvertingStage.SOURCEPMOS,
        NonInvertingStage.SOURCENMOS,
    ]
    stage.add_instance(transconductance)
    stage.add_instance(load)
    stage.add_instance(stageBiasNmos)
    stage.add_instance(stageBiasPmos)

    stage = addStageBiasesNets(stage, stageBiasNmos, stageBiasPmos)
    stage = addComplementaryLoadNets(stage, load)

    stage = connectInstanceTerminalsOfComplementaryTransconductanceNonInv(
        stage, transconductance
    )
    stage = connectInstanceTerminalsOfComplementaryLoad(stage, load)
    stage = connectInstanceTerminalsOfComplementaryStageBiases(
        stage, stageBiasNmos, stageBiasPmos
    )

    return stage


def createFeedbackTransconductanceNonInvertingStage(
    transconductance: Transconductance,
    load: list[Load],
    stageBias1: StageBias,
    stageBias2: StageBias,
) -> NonInvertingStage:
    """Assemble a non-inverting stage from a feedback transconductance, one
    load, and two independent stage-bias copies (one per transconductance source)."""
    stage = NonInvertingStage(id=1, techtype=transconductance.tech)
    stage.ports = [
        NonInvertingStage.OUT1,
        NonInvertingStage.OUT2,
        NonInvertingStage.IN1,
        NonInvertingStage.IN2,
        NonInvertingStage.SOURCETRANSCONDUCTANCE1,
        NonInvertingStage.SOURCETRANSCONDUCTANCE2,
        NonInvertingStage.INNERTRANSCONDUCTANCE,
        NonInvertingStage.SOURCEPMOS,
        NonInvertingStage.SOURCENMOS,
    ]
    stage.add_instance(transconductance)
    stage.add_instance(load)
    stage.add_instance(stageBias1)
    stage.add_instance(stageBias2)

    stage = addStageBiasNets(stage, stageBias1)
    stage = addLoadNets(stage, load)

    stage = connectInstanceTerminalsOfFeedbackTransconductanceXXX(
        stage, transconductance
    )
    stage = connectInstanceTerminalsOfLoad(stage, load)
    stage = connectInstanceTerminalsOfStageBiases(stage, stageBias1, stageBias2)
    return stage


# --------------------------------------------------------------
def createSimpleTransconductanceNonInvertingStages(
    transconductance: Transconductance, loads: list[Load], stageBiases: list[StageBias]
) -> Iterator[NonInvertingStage]:
    """Yield one stage per (load, stage bias) pair sharing the same
    *transconductance* (the full cross-product, as acst
    ``createSimpleTransconductanceNonInvertingStages`` — asymmetric
    odd-transistor loads included)."""
    stageBiases = list(stageBiases)  # materialise to allow re-iteration per load
    for l in loads:
        for sb in stageBiases:
            yield createSimpleTransconductanceNonInvertingStage(transconductance, l, sb)


def createComplementaryTransconductanceNonInvertingStages(
    transconductance: Transconductance,
    loads: list[Load],
    stageBiasesNmos: list[StageBias],
    stageBiasesPmos: list[StageBias],
) -> Iterator[NonInvertingStage]:
    """Yield one stage per load, paired with the single complementary
    transconductance and index-aligned NMOS/PMOS stage-bias pairs."""

    transconductance = list(transconductance)[0]
    stageBiasesPmos = list(stageBiasesPmos)
    stageBiasesNmos = list(stageBiasesNmos)
    for load in loads:
        for i in range(len(stageBiasesPmos)):
            sb_pmos = stageBiasesPmos[i]
            sb_nmos = stageBiasesNmos[i]
            yield createComplementaryTransconductanceNonInvertingStage(
                transconductance, load, sb_nmos, sb_pmos
            )

            # TODO: translate the following C++ code
            # if(nonInvertingStage.everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType())


def createFeedbackTransconductanceNonInvertingStages(
    transconductance: Transconductance, loads: list[Load], stageBiases: list[StageBias]
) -> Iterator[NonInvertingStage]:
    """Yield one stage per (load, stage bias) pair sharing the same feedback
    *transconductance*, deep-copying the stage bias into independent
    ``sb1``/``sb2`` instances for each stage."""
    for load in loads:
        for stageBias in stageBiases:
            sb1 = deepcopy(stageBias)
            sb2 = deepcopy(stageBias)
            yield createFeedbackTransconductanceNonInvertingStage(
                transconductance, load, sb1, sb2
            )
            # TODO: add if(nonInvertingStage.everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType())


class NonInvertingStageManager:
    """Top-level HL4 dispatcher for non-inverting (first/input) stages.

    Each ``create*NonInvertingStages(caseNumber)`` method enumerates a fixed
    list of ``case_N`` closures — one per (transconductance tech, load
    variant, stage-bias transistor count) combination — and dispatches to the
    one matching *caseNumber* (1-indexed; ``case_unknown`` covers anything
    out of range). Every ``case_N`` builds its combination via the relevant
    HL3 managers (:class:`~topogen.HL3.tc.TransconductanceManager`,
    :class:`~topogen.HL3.l.LoadManager`,
    :class:`~topogen.HL3.sb.StageBiasManager`) and the matching module-level
    ``create*NonInvertingStages`` generator.
    """

    def __init__(self):
        """Defer feedback-stage construction until first requested (see
        :meth:`getFeedbackNonInvertingStagesPmosTransconductance` /
        :meth:`getFeedbackNonInvertingStagesNmosTransconductance`)."""
        self.feedbackNonInvertingStagesPmosTransconductance_ = None
        self.feedbackNonInvertingStagesNmosTransconductance_ = None
        pass

    def createSimpleNonInvertingStages(
        self, caseNumber: int
    ) -> Iterator[NonInvertingStage]:
        """Dispatch to one of 16 simple-transconductance non-inverting-stage
        cases (PMOS/NMOS transconductance x mixed/folded-GCC/cascode-GCC load
        x one-/two-transistor stage bias); see class docstring."""
        create_fn = createSimpleTransconductanceNonInvertingStages
        tc_mn, l_mn, sb_mn = (
            TransconductanceManager(),
            LoadManager(),
            StageBiasManager(),
        )

        def case_1():
            """PMOS transconductance + NMOS mixed load + one-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createSimpleMixedLoadNmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_2():
            """NMOS/PMOS mirror of ``case_1``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createSimpleMixedLoadPmos(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_3():
            """PMOS transconductance + NMOS mixed load + two-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createSimpleMixedLoadNmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_4():
            """NMOS/PMOS mirror of ``case_3``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createSimpleMixedLoadPmos(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_5():
            """PMOS transconductance + folded-GCC NMOS mixed load + one-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_6():
            """NMOS/PMOS mirror of ``case_5``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_7():
            """PMOS transconductance + folded-GCC NMOS mixed load + two-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_8():
            """NMOS/PMOS mirror of ``case_7``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_9():
            """PMOS transconductance + cascode-GCC PMOS mixed load + one-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsTwoLoadPartsCascodeGCCMixedPmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_10():
            """NMOS/PMOS mirror of ``case_9``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsTwoLoadPartsCascodeGCCMixedNmos(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_11():
            """PMOS transconductance + cascode-GCC PMOS mixed load + two-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsTwoLoadPartsCascodeGCCMixedPmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_12():
            """NMOS/PMOS mirror of ``case_11``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsTwoLoadPartsCascodeGCCMixedNmos(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_13():
            """PMOS transconductance + non-GCC PMOS mixed/current-bias load + one-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsTwoLoadPartsMixedCurrentBiasesPmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_14():
            """NMOS/PMOS mirror of ``case_13``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsTwoLoadPartsMixedCurrentBiasesNmos(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_15():
            """PMOS transconductance + non-GCC PMOS mixed/current-bias load + two-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsTwoLoadPartsMixedCurrentBiasesPmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_16():
            """NMOS/PMOS mirror of ``case_15``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsTwoLoadPartsMixedCurrentBiasesNmos(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_unknown():
            """Raise — *caseNumber* is outside the valid 1-16 range."""
            raise NotImplementedError("unknow case.")

        case_fn = [
            case_unknown,
            case_1,
            case_2,
            case_3,
            case_4,
            case_5,
            case_6,
            case_7,
            case_8,
            case_9,
            case_10,
            case_11,
            case_12,
            case_13,
            case_14,
            case_15,
            case_16,
        ]
        return case_fn[caseNumber]()

    def createFullyDifferentialNonInvertingStages(
        self,
        caseNumber: int,
    ) -> Iterator[NonInvertingStage]:
        """Dispatch to one of 4 fully-differential non-inverting-stage cases
        (PMOS/NMOS transconductance x one-/two-transistor stage bias, paired
        with the opposite-tech fully-differential load); see class docstring."""
        create_fn = createSimpleTransconductanceNonInvertingStages
        tc_mn = TransconductanceManager()
        l_mn = LoadManager()
        sb_mn = StageBiasManager()

        def case_1():
            """PMOS transconductance + NMOS fully-differential load + one-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosForFullyDifferentialNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_2():
            """NMOS/PMOS mirror of ``case_1``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosForFullyDifferentialNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_3():
            """PMOS transconductance + NMOS fully-differential load + two-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosForFullyDifferentialNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_4():
            """NMOS/PMOS mirror of ``case_3``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosForFullyDifferentialNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_unknown():
            """Raise — *caseNumber* is outside the valid 1-4 range."""
            raise NotImplementedError("unknow case.")

        case_fn = [
            case_unknown,
            case_1,
            case_2,
            case_3,
            case_4,
        ]
        return case_fn[caseNumber]()

    def createComplementaryNonInvertingStages(
        self,
        caseNumber: int,
    ) -> Iterator[NonInvertingStage]:
        """Dispatch to one of 2 complementary non-inverting-stage cases
        (one-transistor vs. two-transistor NMOS+PMOS stage-bias pairs); see
        class docstring."""

        create_fn = createComplementaryTransconductanceNonInvertingStages
        tc_mn = TransconductanceManager()
        l_mn = LoadManager()
        sb_mn = StageBiasManager()

        def case_1():
            """Complementary transconductance + complementary load + one-transistor NMOS/PMOS stage biases."""
            return create_fn(
                tc_mn.getComplementaryTransconductance(),
                l_mn.createLoadsForComplementaryNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesNmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_2():
            """Complementary transconductance + complementary load + two-transistor NMOS/PMOS stage biases."""
            return create_fn(
                tc_mn.getComplementaryTransconductance(),
                l_mn.createLoadsForComplementaryNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_unknown():
            """Raise — *caseNumber* is outside the valid 1-2 range."""
            raise NotImplementedError("unknow case.")

        case_fn = [
            case_unknown,
            case_1,
            case_2,
        ]
        return case_fn[caseNumber]()

    def createSymmetricalNonInvertingStages(
        self, caseNumber: int
    ) -> Iterator[NonInvertingStage]:
        """Dispatch to one of 8 symmetrical-op-amp non-inverting-stage cases
        (PMOS/NMOS transconductance x two-/four-transistor voltage-bias load
        x one-/two-transistor stage bias); see class docstring."""
        create_fn = createSimpleTransconductanceNonInvertingStages
        tc_mn = TransconductanceManager()
        l_mn = LoadManager()
        sb_mn = StageBiasManager()

        def case_1():
            """PMOS transconductance + NMOS two-transistor symmetrical load + one-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_2():
            """NMOS/PMOS mirror of ``case_1``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_3():
            """PMOS transconductance + NMOS two-transistor symmetrical load + two-transistor PMOS stage bias."""

            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_4():
            """NMOS/PMOS mirror of ``case_3``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_5():
            """PMOS transconductance + NMOS four-transistor symmetrical load + one-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_6():
            """NMOS/PMOS mirror of ``case_5``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_7():
            """PMOS transconductance + NMOS four-transistor symmetrical load + two-transistor PMOS stage bias."""
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_8():
            """NMOS/PMOS mirror of ``case_7``."""
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_unknown():
            """Raise — *caseNumber* is outside the valid 1-8 range."""
            raise NotImplementedError("unknow case.")

        case_fn = [
            case_unknown,
            case_1,
            case_2,
            case_3,
            case_4,
            case_5,
            case_6,
            case_7,
            case_8,
        ]
        return case_fn[caseNumber]()

    def initializeFeedbackNonInvertingStages(self) -> None:
        """Build the feedback-transconductance PMOS and NMOS non-inverting
        stages and cache them on ``self`` (called lazily by the getters below)."""
        transconductanceNmos = (
            TransconductanceManager().getFeedbackTransconductanceNmos()
        )
        transconductancePmos = (
            TransconductanceManager().getFeedbackTransconductancePmos()
        )

        loadsPmos = LoadManager().getLoadsPmosForFeedbackNonInvertingStage()
        loadsNmos = LoadManager().getLoadsNmosForFeedbackNonInvertingStage()

        stageBiasesNmos = StageBiasManager().getAllStageBiasesNmos()
        stageBiasesPmos = StageBiasManager().getAllStageBiasesPmos()

        self.feedbackNonInvertingStagesPmosTransconductance_ = (
            createFeedbackTransconductanceNonInvertingStages(
                transconductancePmos, loadsNmos, stageBiasesPmos
            )
        )
        self.feedbackNonInvertingStagesNmosTransconductance_ = (
            createFeedbackTransconductanceNonInvertingStages(
                transconductanceNmos, loadsPmos, stageBiasesNmos
            )
        )

    def getFeedbackNonInvertingStagesPmosTransconductance(self):
        """Return the feedback PMOS-transconductance stages, building them on first call."""
        if self.feedbackNonInvertingStagesPmosTransconductance_ is None:
            self.initializeFeedbackNonInvertingStages()

        return self.feedbackNonInvertingStagesPmosTransconductance_

    def getFeedbackNonInvertingStagesNmosTransconductance(self):
        """Return the feedback NMOS-transconductance stages, building them on first call."""
        if self.feedbackNonInvertingStagesNmosTransconductance_ is None:
            self.initializeFeedbackNonInvertingStages()

        return self.feedbackNonInvertingStagesNmosTransconductance_


if __name__ == "__main__":
    non_inv_manager = NonInvertingStageManager()
    # fmt: off

    # create simple non inverting stages
    (GALLERY_DOT_DIR / "SimpleNonInvertingStages").mkdir(parents=True, exist_ok=True)
    (GALLERY_IMAGE_DIR / "SimpleNonInvertingStages").mkdir(parents=True, exist_ok=True)

    for case_id, create_method in enumerate(range(16), start=1):
        circuits = list(non_inv_manager.createSimpleNonInvertingStages(case_id))
        print(f"createSimpleNonInvertingStages, case: {case_id}, #num={len(circuits)}")
        for circuit_id, non_inv_stage in enumerate(circuits, start=1):
            save_graphviz_figure(
                non_inv_stage,
                GALLERY_DOT_DIR
                / f"SimpleNonInvertingStages/n_inv_{case_id}_{circuit_id}.dot",
            )
            convert_dot_to_png(
                GALLERY_DOT_DIR
                / f"SimpleNonInvertingStages/n_inv_{case_id}_{circuit_id}.dot",
                GALLERY_IMAGE_DIR
                / f"SimpleNonInvertingStages/n_inv_{case_id}_{circuit_id}.png",
            )

    # create fully differential non inverting stages
    (GALLERY_DOT_DIR / "FullyDifferentialNonInvertingStages").mkdir(parents=True, exist_ok=True)
    (GALLERY_IMAGE_DIR / "FullyDifferentialNonInvertingStages").mkdir(parents=True, exist_ok=True)

    for case_id, create_method in enumerate(range(4), start=1):
        circuits = list(non_inv_manager.createFullyDifferentialNonInvertingStages(case_id))
        print(f"createFullyDifferentialNonInvertingStages, case: {case_id}, #num={len(circuits)}")
        for circuit_id, non_inv_stage in enumerate(circuits, start=1):
            save_graphviz_figure(
                non_inv_stage,
                GALLERY_DOT_DIR
                / f"FullyDifferentialNonInvertingStages/n_inv_{case_id}_{circuit_id}.dot",
            )
            convert_dot_to_png(
                GALLERY_DOT_DIR
                / f"FullyDifferentialNonInvertingStages/n_inv_{case_id}_{circuit_id}.dot",
                GALLERY_IMAGE_DIR
                / f"FullyDifferentialNonInvertingStages/n_inv_{case_id}_{circuit_id}.png",
            )


    (GALLERY_DOT_DIR / "ComplementaryNonInvertingStages").mkdir(parents=True, exist_ok=True)
    (GALLERY_IMAGE_DIR / "ComplementaryNonInvertingStages").mkdir(parents=True, exist_ok=True)

    for case_id, create_method in enumerate(range(2), start=1):
        circuits = list(non_inv_manager.createComplementaryNonInvertingStages(case_id))
        print(f"createComplementaryNonInvertingStages, case: {case_id}, #num={len(circuits)}")
        for circuit_id, non_inv_stage in enumerate(circuits, start=1):
            save_graphviz_figure(
                non_inv_stage,
                GALLERY_DOT_DIR
                / f"ComplementaryNonInvertingStages/n_inv_{case_id}_{circuit_id}.dot",
            )
            convert_dot_to_png(
                GALLERY_DOT_DIR
                / f"ComplementaryNonInvertingStages/n_inv_{case_id}_{circuit_id}.dot",
                GALLERY_IMAGE_DIR
                / f"ComplementaryNonInvertingStages/n_inv_{case_id}_{circuit_id}.png",
            )


    (GALLERY_DOT_DIR / "FeedbackNonInvertingStages").mkdir(parents=True, exist_ok=True)
    (GALLERY_IMAGE_DIR / "FeedbackNonInvertingStages").mkdir(parents=True, exist_ok=True)

    for case_id, create_method in enumerate(range(2), start=1):
        if case_id == 1:
            circuits = list(non_inv_manager.getFeedbackNonInvertingStagesPmosTransconductance())
        else:
            circuits = list(non_inv_manager.getFeedbackNonInvertingStagesNmosTransconductance())

        print(f"createFeedbackNonInvertingStages, case: {case_id}, #num={len(circuits)}")
        for circuit_id, non_inv_stage in enumerate(circuits, start=1):
            save_graphviz_figure(
                non_inv_stage,
                GALLERY_DOT_DIR
                / f"FeedbackNonInvertingStages/n_inv_{case_id}_{circuit_id}.dot",
            )
            convert_dot_to_png(
                GALLERY_DOT_DIR
                / f"FeedbackNonInvertingStages/n_inv_{case_id}_{circuit_id}.dot",
                GALLERY_IMAGE_DIR
                / f"FeedbackNonInvertingStages/n_inv_{case_id}_{circuit_id}.png",
            )
