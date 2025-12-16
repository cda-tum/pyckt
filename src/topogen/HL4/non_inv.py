# from src.topogen.HL2 import *
# from src.topogen.HL3 import *
from src.topogen.HL3.l import LoadManager
from src.topogen.HL3.sb import StageBiasManager
from src.topogen.HL3.tc import TransconductanceManager

from src.topogen.HL4.non_inv_connections import *
from src.topogen.HL4.non_inv_netdef import *
from src.topogen.common.circuit import *


from pathlib import Path
from typing import Callable, Iterator
from itertools import chain
from copy import deepcopy

from src.utils.loguru_loader import setup_logger

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
    for l in loads:
        if l.component_count % 2 == 1:
            continue
        for sb in stageBiases:
            yield createSimpleTransconductanceNonInvertingStage(transconductance, l, sb)


def createComplementaryTransconductanceNonInvertingStages(
    transconductance: Transconductance,
    loads: list[Load],
    stageBiasesNmos: list[StageBias],
    stageBiasesPmos: list[StageBias],
) -> Iterator[NonInvertingStage]:

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
    for load in loads:
        for stageBias in stageBiases:
            sb1 = deepcopy(stageBias)
            sb2 = deepcopy(stageBias)
            yield createFeedbackTransconductanceNonInvertingStage(
                transconductance, load, sb1, sb2
            )
            # TODO: add if(nonInvertingStage.everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType())


class NonInvertingStageManager:
    def __init__(self):
        self.feedbackNonInvertingStagesPmosTransconductance_ = None
        self.feedbackNonInvertingStagesNmosTransconductance_ = None
        pass

    def createSimpleNonInvertingStages(
        self, caseNumber: int
    ) -> Iterator[NonInvertingStage]:
        create_fn = createSimpleTransconductanceNonInvertingStages
        tc_mn, l_mn, sb_mn = (
            TransconductanceManager(),
            LoadManager(),
            StageBiasManager(),
        )

        def case_1():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createSimpleMixedLoadNmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_2():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createSimpleMixedLoadPmos(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_3():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createSimpleMixedLoadNmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_4():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createSimpleMixedLoadPmos(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_5():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_6():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_7():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_8():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_9():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsTwoLoadPartsCascodeGCCMixedPmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_10():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsTwoLoadPartsCascodeGCCMixedNmos(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_11():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsTwoLoadPartsCascodeGCCMixedPmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_12():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsTwoLoadPartsCascodeGCCMixedNmos(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_13():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsTwoLoadPartsMixedCurrentBiasesPmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_14():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsTwoLoadPartsMixedCurrentBiasesNmos(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_15():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsTwoLoadPartsMixedCurrentBiasesPmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_16():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsTwoLoadPartsMixedCurrentBiasesNmos(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_unknown():
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
        create_fn = createSimpleTransconductanceNonInvertingStages
        tc_mn = TransconductanceManager()
        l_mn = LoadManager()
        sb_mn = StageBiasManager()

        def case_1():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosForFullyDifferentialNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_2():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosForFullyDifferentialNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_3():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosForFullyDifferentialNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_4():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosForFullyDifferentialNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_unknown():
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

        create_fn = createComplementaryTransconductanceNonInvertingStages
        tc_mn = TransconductanceManager()
        l_mn = LoadManager()
        sb_mn = StageBiasManager()

        def case_1():
            return create_fn(
                tc_mn.getComplementaryTransconductance(),
                l_mn.createLoadsForComplementaryNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesNmos(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_2():
            return create_fn(
                tc_mn.getComplementaryTransconductance(),
                l_mn.createLoadsForComplementaryNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_unknown():
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
        create_fn = createSimpleTransconductanceNonInvertingStages
        tc_mn = TransconductanceManager()
        l_mn = LoadManager()
        sb_mn = StageBiasManager()

        def case_1():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_2():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_3():

            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_4():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_5():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesPmos(),
            )

        def case_6():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getOneTransistorStageBiasesNmos(),
            )

        def case_7():
            return create_fn(
                tc_mn.getSimpleTransconductancePmos(),
                l_mn.createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesPmos(),
            )

        def case_8():
            return create_fn(
                tc_mn.getSimpleTransconductanceNmos(),
                l_mn.createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage(),
                sb_mn.getTwoTransistorStageBiasesNmos(),
            )

        def case_unknown():
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
        if self.feedbackNonInvertingStagesPmosTransconductance_ is None:
            self.initializeFeedbackNonInvertingStages()

        return self.feedbackNonInvertingStagesPmosTransconductance_

    def getFeedbackNonInvertingStagesNmosTransconductance(self):
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
