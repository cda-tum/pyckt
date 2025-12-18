# from src.topogen.HL2 import *
# from src.topogen.HL3 import *
from src.topogen.HL3.l import LoadManager
from src.topogen.HL3.sb import StageBiasManager
from src.topogen.HL3.tc import TransconductanceManager
from src.topogen.HL2.inv import InverterManager
from src.topogen.common.circuit import *


from pathlib import Path
from typing import Callable, Iterator
from itertools import chain
from copy import deepcopy

from src.utils.loguru_loader import setup_logger

logger = setup_logger()


GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL4" / "inv" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)
GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL4" / "inv" / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def addTransconductanceNets(
    stage: InvertingStage, transconductance: Transconductance
) -> InvertingStage:
    if transconductance.component_count == 2:
        stage.ports += [
            InvertingStage.INSOURCETRANSCONDUCTANCE,
            InvertingStage.INOUTPUTTRANSCONDUCTANCE,
            InvertingStage.INNERTRANSCONDUCTANCE,
        ]
    else:
        stage.ports += [InvertingStage.INTRANSCONDUCTANCE]
    return stage


def addStageBiasNets(stage: InvertingStage, stageBias: StageBias) -> InvertingStage:
    if stageBias.component_count == 2:
        stage.ports += [
            InvertingStage.INSOURCESTAGEBIAS,
            InvertingStage.INOUTPUTSTAGEBIAS,
            InvertingStage.INNERSTAGEBIAS,
        ]
    else:
        stage.ports += [InvertingStage.INSTAGEBIAS]
    return stage


def connectInstanceTerminalsPmosTransconductance(
    invertingStage: InvertingStage, analogInverter: Inverter
) -> InvertingStage:
    # fmt: off
    for inst in analogInverter.instances:
        if inst.tech == "p":
            transconductance = inst
        elif inst.tech == "n":
            stageBias = inst
    connect((invertingStage, InvertingStage.OUTPUT), (analogInverter, Inverter.OUTPUT))
    connect((invertingStage, InvertingStage.SOURCEPMOS), (analogInverter, Inverter.SOURCE_CURRENTBIASPMOS))
    connect((invertingStage, InvertingStage.SOURCENMOS), (analogInverter, Inverter.SOURCE_CURRENTBIASNMOS))

    if transconductance.component_count == 2:
        connect((invertingStage, InvertingStage.INSOURCETRANSCONDUCTANCE), (analogInverter, Inverter.INSOURCE_CURRENTBIASPMOS))
        connect((invertingStage, InvertingStage.INOUTPUTTRANSCONDUCTANCE), (analogInverter, Inverter.INOUTPUT_CURRENTBIASPMOS))
        connect((invertingStage, InvertingStage.INNERTRANSCONDUCTANCE), (analogInverter, Inverter.INNER_CURRENTBIASPMOS))
    else:
        connect((invertingStage, InvertingStage.INTRANSCONDUCTANCE), (analogInverter, Inverter.IN_CURRENTBIASPMOS))
        
    if stageBias.component_count == 2:
        connect((invertingStage, InvertingStage.INSOURCESTAGEBIAS), (analogInverter, Inverter.INSOURCE_CURRENTBIASNMOS))
        connect((invertingStage, InvertingStage.INOUTPUTSTAGEBIAS), (analogInverter, Inverter.INOUTPUT_CURRENTBIASNMOS))
        connect((invertingStage, InvertingStage.INNERSTAGEBIAS), (analogInverter, Inverter.INNER_CURRENTBIASNMOS))
    else:
        connect((invertingStage, InvertingStage.INSTAGEBIAS), (analogInverter, Inverter.IN_CURRENTBIASNMOS))
    return invertingStage


def connectInstanceTerminalsNmosTransconductance(
    invertingStage: InvertingStage, analogInverter: Inverter
) -> InvertingStage:

    # fmt: off
    for inst in analogInverter.instances:
        if inst.tech == "n":
            transconductance = inst
        elif inst.tech == "p":
            stageBias = inst

    connect((invertingStage, InvertingStage.OUTPUT), (analogInverter, Inverter.OUTPUT))
    connect((invertingStage, InvertingStage.SOURCEPMOS), (analogInverter, Inverter.SOURCE_CURRENTBIASPMOS))
    connect((invertingStage, InvertingStage.SOURCENMOS), (analogInverter, Inverter.SOURCE_CURRENTBIASNMOS))

    if transconductance.component_count == 2:
        connect((invertingStage, InvertingStage.INSOURCETRANSCONDUCTANCE), (analogInverter, Inverter.INSOURCE_CURRENTBIASNMOS))
        connect((invertingStage, InvertingStage.INOUTPUTTRANSCONDUCTANCE), (analogInverter, Inverter.INOUTPUT_CURRENTBIASNMOS))
        connect((invertingStage, InvertingStage.INNERTRANSCONDUCTANCE), (analogInverter, Inverter.INNER_CURRENTBIASNMOS))

    else:
        connect((invertingStage, InvertingStage.INNERTRANSCONDUCTANCE), (analogInverter, Inverter.IN_CURRENTBIASNMOS))

    if stageBias.component_count == 2:
        connect((invertingStage, InvertingStage.INSOURCESTAGEBIAS), (analogInverter, Inverter.INSOURCE_CURRENTBIASPMOS))
        connect((invertingStage, InvertingStage.INOUTPUTSTAGEBIAS), (analogInverter, Inverter.INOUTPUT_CURRENTBIASPMOS))
        connect((invertingStage, InvertingStage.INNERSTAGEBIAS), (analogInverter, Inverter.INNER_CURRENTBIASPMOS))
    else:
        connect((invertingStage, InvertingStage.INNERSTAGEBIAS), (analogInverter, Inverter.IN_CURRENTBIASPMOS))

    return invertingStage


class InvertingStageManager:
    def __init__(self):
        self.initializeInvertingStages()

    def getInvertingStagesPmosTransconductance(self):
        return self.invertingStagesPmosTransconductance_

    def getInvertingStagesNmosTransconductance(self):
        return self.invertingStagesNmosTransconductance_

    # def getNonInvertingSelfBiasStages(self):
    #     return self.nonInvertingStagesSelfBias_

    def getInvertingStages(self):
        return (
            self.invertingStagesNmosTransconductance_
            + self.invertingStagesPmosTransconductance_
        )

    def initializeInvertingStages(self):
        analogInverters = InverterManager().getAnalogInverters()

        self.invertingStagesPmosTransconductance_ = list(
            self.createInvertingStagesPmosTransconductance(analogInverters)
        )
        self.invertingStagesNmosTransconductance_ = list(
            self.createInvertingStagesNmosTransconductance(analogInverters)
        )

        # nonInvertingStagesSelfBiasOut = []
        # analogSelfBiasInverters = InverterManager().getAnalogSelfBiasInverters()
        # for sbNonInv in analogSelfBiasInverters:
        #     invertingSelfBiasStage = self.createNonInvertingSelfBiasStage(sbNonInv)
        #     nonInvertingStagesSelfBiasOut.append(invertingSelfBiasStage)

        # self.nonInvertingStagesSelfBias_ = nonInvertingStagesSelfBiasOut

        # // nonInvertingStagesSelfBias_ =
        # int index = 1;
        # std::vector<const Core::Circuit*> nonInvertingStagesSelfBiasOut;
        # std::vector<const Core::Circuit*> analogSelfBiasInverters = structuralLevel.getAnalogInverters().getAnalogSelfBiasInverters();
        # for(auto & sbNonInv : analogSelfBiasInverters)
        # {
        #     const Core::Circuit & invertingSelfBiasStage = createNonInvertingSelfBiasStage(createInstance(*sbNonInv, ANALOGINVERTER_), index);
        #     nonInvertingStagesSelfBiasOut.push_back(&invertingSelfBiasStage);
        #     index++;
        # }
        # nonInvertingStagesSelfBias_ =  nonInvertingStagesSelfBiasOut;

    def createInvertingStagesPmosTransconductance(
        self, analogInverters: list[Inverter]
    ) -> Iterator[InvertingStage]:
        for analogInverter in analogInverters:

            currentBiasPmos: CurrentBias = analogInverter.find_cb_with_tech("p")
            if not sourceTransistorIsDiodeTransistor(currentBiasPmos):
                invertingStage = self.createInvertingStagePmosTransconductance(
                    analogInverter
                )
                # TODO: enable the following line
                # if(invertingStage.everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType())
                if everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType(
                    invertingStage
                ):
                    yield invertingStage

    def createInvertingStagesNmosTransconductance(
        self, analogInverters: list[Inverter]
    ) -> Iterator[InvertingStage]:
        for analogInverter in analogInverters:

            currentBiasNmos: CurrentBias = analogInverter.find_cb_with_tech("n")
            if not sourceTransistorIsDiodeTransistor(currentBiasNmos):
                invertingStage = self.createInvertingStageNmosTransconductance(
                    analogInverter
                )
                # TODO: enable the following line
                if everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType(
                    invertingStage
                ):
                    yield invertingStage

    def createInvertingStagePmosTransconductance(
        self,
        analogInverter: Inverter,
    ) -> InvertingStage:
        stage = InvertingStage(id=1, techtype="p")
        stage.ports = [
            InvertingStage.OUTPUT,
            InvertingStage.SOURCEPMOS,
            InvertingStage.SOURCENMOS,
        ]
        # transconductance = analogInverter.getMaster().findInstance(createInstanceId(AnalogInverters::CURRENTBIASPMOS_));
        # stageBias = analogInverter.getMaster().findInstance(createInstanceId(AnalogInverters::CURRENTBIASNMOS_));
        for inst in analogInverter.instances:
            if inst.tech == "p":
                transconductance = inst
            elif inst.tech == "n":
                stageBias = inst
        stage = addTransconductanceNets(stage, transconductance)
        # stage = addStageBiasNets(stage, stageBias)
        stage.add_instance(analogInverter)

        stage = connectInstanceTerminalsPmosTransconductance(stage, analogInverter)
        return stage

    def createNonInvertingSelfBiasStage(
        self, analogInverter: Inverter
    ) -> InvertingStage:
        stage = InvertingStage(id=1, techtype="p")
        stage.ports = [
            InvertingStage.OUTPUT,
            InvertingStage.SOURCEPMOS,
            InvertingStage.SOURCENMOS,
            InvertingStage.INTRANSCONDUCTANCE,
            InvertingStage.INSTAGEBIAS,
        ]

        # stage = addNetsToCircuit(stage, stage)
        # stage = addTerminalsToCircuit(stage, stage)
        stage.add_instance(analogInverter)

        connect((stage, InvertingStage.OUTPUT), (analogInverter, Inverter.OUTPUT))
        connect(
            (stage, InvertingStage.SOURCEPMOS),
            (analogInverter, Inverter.SOURCE_CURRENTBIASPMOS),
        )
        connect(
            (stage, InvertingStage.SOURCENMOS),
            (analogInverter, Inverter.SOURCE_CURRENTBIASNMOS),
        )
        connect(
            (stage, InvertingStage.INTRANSCONDUCTANCE),
            (analogInverter, Inverter.IN_CURRENTBIASPMOS),
        )
        connect(
            (stage, InvertingStage.INSTAGEBIAS),
            (analogInverter, Inverter.IN_CURRENTBIASNMOS),
        )
        return stage

    def createInvertingStageNmosTransconductance(
        self,
        analogInverter: Inverter,
    ) -> InvertingStage:
        stage = InvertingStage(id=1, techtype="n")
        stage.ports = [
            InvertingStage.OUTPUT,
            InvertingStage.SOURCEPMOS,
            InvertingStage.SOURCENMOS,
        ]
        for inst in analogInverter.instances:
            if inst.tech == "n":
                transconductance: Transconductance = inst
            elif inst.tech == "p":
                stageBias: StageBias = inst
        stage = addTransconductanceNets(stage, transconductance)
        stage = addStageBiasNets(stage, stageBias)

        stage.add_instance(analogInverter)
        stage = connectInstanceTerminalsNmosTransconductance(stage, analogInverter)
        return stage


if __name__ == "__main__":
    inv_manager = InvertingStageManager()
    # fmt: off

    # create simple non inverting stages
    (GALLERY_DOT_DIR / "InvertingStagesPmosTransconductance").mkdir(parents=True, exist_ok=True)
    (GALLERY_IMAGE_DIR / "InvertingStagesPmosTransconductance").mkdir(parents=True, exist_ok=True)

    # for case_id, create_method in enumerate([1], start=1):
    case_id = 1
    circuits = list(inv_manager.getInvertingStagesPmosTransconductance())
    print(f"InvertingStagesPmosTransconductance, case: {case_id}, #num={len(circuits)}")
    for circuit_id, inv_stage in enumerate(circuits, start=1):
        save_graphviz_figure(
            inv_stage,
            GALLERY_DOT_DIR
            / f"InvertingStagesPmosTransconductance/inv_{case_id}_{circuit_id}.dot",
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR
            / f"InvertingStagesPmosTransconductance/inv_{case_id}_{circuit_id}.dot",
            GALLERY_IMAGE_DIR
            / f"InvertingStagesPmosTransconductance/inv_{case_id}_{circuit_id}.png",
        )


    case_id = 2
    (GALLERY_DOT_DIR / "InvertingStagesNmosTransconductance").mkdir(parents=True, exist_ok=True)
    (GALLERY_IMAGE_DIR / "InvertingStagesNmosTransconductance").mkdir(parents=True, exist_ok=True)
    circuits = list(inv_manager.getInvertingStagesNmosTransconductance())
    print(f"InvertingStagesNmosTransconductance, case: {case_id}, #num={len(circuits)}")
    for circuit_id, inv_stage in enumerate(circuits, start=1):
        save_graphviz_figure(
            inv_stage,
            GALLERY_DOT_DIR
            / f"InvertingStagesNmosTransconductance/inv_{case_id}_{circuit_id}.dot",
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR
            / f"InvertingStagesNmosTransconductance/inv_{case_id}_{circuit_id}.dot",
            GALLERY_IMAGE_DIR
            / f"InvertingStagesNmosTransconductance/inv_{case_id}_{circuit_id}.png",
        )
