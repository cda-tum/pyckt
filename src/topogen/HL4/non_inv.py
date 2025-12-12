from src.topogen.HL2 import *
from src.topogen.HL3 import *

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


def connectInstanceTerminalsOfSimpleTransconductance(
    nonInvertingStage: NonInvertingStage, transconductance
) -> NonInvertingStage:
    connect((nonInvertingStage, "in1"), (transconductance, "input1"))
    connect((nonInvertingStage, "in2"), (transconductance, "input2"))
    connect(
        (nonInvertingStage, "source_transconductance"), (transconductance, "source")
    )
    if hasGCC(nonInvertingStage.get_instance_by_name("l")[0]):
        connect(
            (nonInvertingStage, "source_gcc1"),
            (transconductance, "out1"),
        )
    # TODO: check GCCE warning here
    connect((nonInvertingStage, "out1"), (transconductance, "out1"))
    connect((nonInvertingStage, "out2"), (transconductance, "out2"))
    return nonInvertingStage


def connectInstanceTerminalsOfLoad(
    nonInvertingStage: NonInvertingStage, load
) -> NonInvertingStage:
    connect((nonInvertingStage, "out1"), (load, "out1"))
    connect((nonInvertingStage, "out2"), (load, "out2"))
    # connect((nonInvertingStage, "source_pmos"), (load, "source"))
    return nonInvertingStage


def connectInstanceTerminalsOfStageBias(
    nonInvertingStage: NonInvertingStage, stageBias
) -> NonInvertingStage:
    connect((nonInvertingStage, "source_transconductance"), (stageBias, "out"))
    return nonInvertingStage


# --------------------------------------------------------------
# net configurations


def addLoadPart1Nets(stage: NonInvertingStage, load: Load) -> NonInvertingStage:
    loadPart1: LoadPart = load.get_instance_by_name("lp")[0]
    if loadPart1 is None:
        logger.error("Load part1 (lp) instance not found in load.")
        return load
    if loadPart1.ts1.instances[0].name.startswith("vb") and loadPart1.ts2.instances[
        0
    ].name.startswith("vb"):
        if loadPart1.component_count == 2:
            stage.ports += [
                "out_output1_load1",
                "out_output2_load1",
                "out_source1_load1",
                "out_source2_load1",
            ]
    elif hasGCC(load):
        stage.ports += [
            "source_gcc1",
            "source_gcc2",
            "inner_gcc",
        ]
        if loadPart1.component_count > 2:
            stage.ports += ["inner_bias_gcc"]
    else:
        if loadPart1.component_count == 2:
            stage.ports += ["inner_load1"]
        if loadPart1.component_count > 2:
            stage.ports += ["inner_source_load1"]
            if len(
                loadPart1.ts1.instances[0].instances
            ) == 1 and loadPart1.ts1.instances[0].instances[0].name.startswith("dt"):
                stage.ports += ["inner_output_load1"]
        if loadPart1.component_count > 3:
            stage.ports += ["inner_output_load1"]

    if hasGCC(load) == False:
        if loadPart1.component_count > 2:
            stage.ports += ["inner_transistorstack2_load1"]
        if loadPart1.component_count > 3:
            stage.ports += ["inner_transistorstack1_load1"]
    return load


def addLoadPart2Nets(stage: NonInvertingStage, load: Circuit) -> NonInvertingStage:
    loadPart2: LoadPart = load.get_instance_by_name("lp")[1]
    if loadPart2.component_count == 2:
        stage.ports += ["inner_load2"]
    if loadPart2.component_count > 2:
        stage.ports += ["inner_source_load2", "inner_transistorstack2_load2"]
        if len(loadPart2.ts1.instances[0].instances) == 1 and loadPart2.ts1.instances[
            0
        ].instances[0].name.startswith("dt"):
            stage.ports += ["inner_output_load2"]
    if loadPart2.component_count > 3:
        stage.ports += ["inner_output_load2", "inner_transistorstack1_load2"]
    return stage


def addLoadNets(stage: NonInvertingStage, load: Load) -> NonInvertingStage:
    addLoadPart1Nets(stage, load)
    if len(load.instances) == 2:
        addLoadPart2Nets(stage, load)
    return stage


def addStageBiasNets(stage: Circuit, stageBias: Circuit):
    if stageBias.component_count == 1:
        stage.ports += ["input_stagebias"]
    else:
        stage.ports += ["in_output_stagebias", "in_source_stagebias"]
        if stageBias.instance_id == -1:
            stage.ports += ["inner_stagebias"]
        else:
            stage.ports += ["inner_stagebias1", "inner_stagebias2"]
    return stage


# --------------------------------------------------------------
def createSimpleTransconductanceNonInvertingStage(
    transconductance, load, stageBias
) -> NonInvertingStage:
    stage = NonInvertingStage(id=1, techtype="?")
    stage.ports = [
        "out1",
        "out2",
        "in1",
        "in2",
        "source_transconductance",
        "source_pmos",
        "source_nmos",
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


def addStageBiasesNets(
    stage: NonInvertingStage, stageBiasNmos: StageBias, stageBiasPmos: StageBias
) -> NonInvertingStage:
    if stageBiasPmos.component_count == 1:
        stage.ports += ["input_stagebias_nmos", "input_stagebias_pmos"]
    else:
        stage.ports += [
            "inner_stagebias_nmos",
            "in_output_stagebias_nmos",
            "in_source_stagebias_nmos",
            "inner_stagebias_pmos",
            "in_output_stagebias_pmos",
            "in_source_stagebias_pmos",
        ]
    return stage


def addComplementaryLoadNets(stage: NonInvertingStage, load: Load) -> NonInvertingStage:
    stage.ports += [
        "inner_output_load_nmos",
        "inner_source_load_nmos",
        "inner_output_load_nmos",
        "inner_source_load_pmos",
        "inner_transistorstack1_load_nmos",
        "inner_transistorstack2_load_nmos",
        "inner_transistorstack1_load_pmos",
        "inner_transistorstack2_load_pmos",
    ]
    return stage


def connectInstanceTerminalsOfComplementaryTransconductance(
    stage: NonInvertingStage, transconductance: Transconductance
) -> NonInvertingStage:
    # fmt: off
    connect((stage, "in1"), (transconductance, "input1"))
    connect((stage, "in2"), (transconductance, "input2"))
    connect((stage, "source_transconductance_nmos"), (transconductance, "source_nmos"))
    connect((stage, "source_transconductance_pmos"), (transconductance, "source_pmos"))

    connect((stage, "inner_transistorstack1_load_pmos"), (transconductance, "out1_nmos"))
    connect((stage, "inner_transistorstack2_load_pmos"), (transconductance, "out2_nmos"))

    connect((stage, "inner_transistorstack1_load_nmos"), (transconductance, "out1_pmos"))
    connect((stage, "inner_transistorstack2_load_nmos"), (transconductance, "out2_pmos"))
    # fmt: on

    return stage


def connectInstanceTerminalsOfComplementaryLoad(
    nonInvertingStage: NonInvertingStage, load: Load
) -> NonInvertingStage:
    # fmt: off
    loadPart1 = load.instances[0]
    loadPart2 = load.instances[1]

    connect((nonInvertingStage, "out1"), (load, "out1"))
    connect((nonInvertingStage, "out2"), (load, "out2"))

    if loadPart1.tech == "n":
        connect((nonInvertingStage, "source_nmos"), (load, "source_load1"))
        connect((nonInvertingStage, "source_pmos"), (load, "source_load2"))

        if hasGCC(load):
            connect((nonInvertingStage, "inner_transistorstack1_load_nmos"), (load, "source_gcc1"))
            connect((nonInvertingStage, "inner_transistorstack2_load_nmos"), (load, "source_gcc2"))
            connect((nonInvertingStage, "inner_output_load_nmos"), (load, "inner_gcc"))
            connect((nonInvertingStage, "inner_source_load_nmos"), (load, "inner_bias_gcc"))
        else:
            connect((nonInvertingStage, "inner_transistorstack1_load_nmos"), (load, "inner_transistorstack1_load1"))
            connect((nonInvertingStage, "inner_transistorstack2_load_nmos"), (load, "inner_transistorstack2_load1"))
            connect((nonInvertingStage, "inner_output_load_nmos"), (load, "inner_output_load1"))
            connect((nonInvertingStage, "inner_source_load_nmos"), (load, "inner_source_load1"))
        
        connect((nonInvertingStage, "inner_transistorstack1_load_pmos"), (load, "inner_transistorstack1_load2"))
        connect((nonInvertingStage, "inner_transistorstack2_load_pmos"), (load, "inner_transistorstack2_load2"))
        connect((nonInvertingStage, "inner_output_load_pmos"), (load, "inner_output_load2"))
        connect((nonInvertingStage, "inner_source_load_pmos"), (load, "inner_source_load2"))
        return nonInvertingStage

    else:
        connect((nonInvertingStage, "source_pmos"), (load, "source_load1"))
        connect((nonInvertingStage, "source_nmos"), (load, "source_load2"))

        if hasGCC(load):
            connect((nonInvertingStage, "inner_transistorstack1_load_pmos"), (load, "source_gcc1"))
            connect((nonInvertingStage, "inner_transistorstack2_load_pmos"), (load, "source_gcc2"))
            connect((nonInvertingStage, "inner_output_load_pmos"), (load, "inner_gcc"))
            connect((nonInvertingStage, "inner_source_load_pmos"), (load, "inner_bias_gcc"))
        else:
            connect((nonInvertingStage, "inner_transistorstack1_load_pmos"), (load, "inner_transistorstack1_load1"))
            connect((nonInvertingStage, "inner_transistorstack2_load_pmos"), (load, "inner_transistorstack2_load1"))
            connect((nonInvertingStage, "inner_output_load_pmos"), (load, "inner_output_load1"))
            connect((nonInvertingStage, "inner_source_load_pmos"), (load, "inner_source_load1"))

        connect((nonInvertingStage, "inner_transistorstack1_load_pmos"), (load, "inner_transistorstack1_load2"))
        connect((nonInvertingStage, "inner_transistorstack2_load_pmos"), (load, "inner_transistorstack2_load2"))
        connect((nonInvertingStage, "inner_output_load_nmos"), (load, "inner_output_load2"))
        connect((nonInvertingStage, "inner_source_load_nmos"), (load, "inner_source_load2"))
        return nonInvertingStage
    # fmt: on


def connectInstanceTerminalsOfComplementaryStageBiases(
    nonInvertingStage: NonInvertingStage,
    stageBiasNmos: StageBias,
    stageBiasPmos: StageBias,
) -> NonInvertingStage:
    connect((nonInvertingStage, "source_transconductance_nmos"), (stageBiasNmos, "out"))
    connect((nonInvertingStage, "source_transconductance_pmos"), (stageBiasPmos, "out"))

    connect((nonInvertingStage, "source_nmos"), (stageBiasNmos, "source"))
    connect((nonInvertingStage, "source_pmos"), (stageBiasPmos, "source"))

    if stageBiasNmos.component_count == 1:
        connect((nonInvertingStage, "input_stagebias_nmos"), (stageBiasNmos, "in"))
        connect((nonInvertingStage, "input_stagebias_pmos"), (stageBiasPmos, "in"))
    else:
        connect(
            (nonInvertingStage, "insource_stagebias_nmos"), (stageBiasNmos, "insource")
        )
        connect(
            (nonInvertingStage, "in_output_stagebias_nmos"), (stageBiasNmos, "inoutput")
        )
        connect((nonInvertingStage, "inner_stagebias_nmos"), (stageBiasNmos, "inner"))

        connect(
            (nonInvertingStage, "insource_stagebias_pmos"), (stageBiasPmos, "insource")
        )
        connect(
            (nonInvertingStage, "in_output_stagebias_pmos"), (stageBiasPmos, "inoutput")
        )
        connect((nonInvertingStage, "inner_stagebias_pmos"), (stageBiasPmos, "inner"))
    return nonInvertingStage


def createComplementaryTransconductanceNonInvertingStage(
    transconductance: Transconductance,
    load: Load,
    stageBiasNmos: StageBias,
    stageBiasPmos: StageBias,
) -> NonInvertingStage:
    stage = NonInvertingStage(id=1, techtype="?")
    stage.ports = [
        "out1",
        "out2",
        "in1",
        "in2",
        "source_transconductance_nmos",
        "source_transconductance_pmos",
        "source_pmos",
        "source_nmos",
    ]
    stage.add_instance(transconductance)
    stage.add_instance(load)
    stage.add_instance(stageBiasNmos)
    stage.add_instance(stageBiasPmos)

    stage = addStageBiasesNets(stage, stageBiasNmos, stageBiasPmos)
    stage = addComplementaryLoadNets(stage, load)

    stage = connectInstanceTerminalsOfComplementaryTransconductance(
        stage, transconductance
    )
    stage = connectInstanceTerminalsOfComplementaryLoad(stage, load)
    stage = connectInstanceTerminalsOfComplementaryStageBiases(
        stage, stageBiasNmos, stageBiasPmos
    )

    return stage


def createSimpleTransconductanceNonInvertingStages(
    transconductance: Transconductance, loads: list[Load], stageBiases: list[StageBias]
) -> Iterator[NonInvertingStage]:
    for load in loads:
        if load.component_count % 2 == 1:
            continue
        for stageBias in stageBiases:
            yield createSimpleTransconductanceNonInvertingStage(
                transconductance, load, stageBias
            )


def createComplementaryTransconductanceNonInvertingStages(
    transconductance: Transconductance,
    loads: list[Load],
    stageBiasesNmos: list[StageBias],
    stageBiasesPmos: list[StageBias],
) -> Iterator[NonInvertingStage]:
    for load in loads:
        for i in range(len(stageBiasesPmos)):
            stageBiasPmos = stageBiasesPmos[i]
            stageBiasNmos = stageBiasesNmos[i]
            yield createComplementaryTransconductanceNonInvertingStage(
                transconductance, load, stageBiasNmos, stageBiasPmos
            )

            # TODO: translate the following C++ code
            # if(nonInvertingStage.everyGateNetIsNotConnectedToMoreThanOneDrainOfComponentWithSameTechType())


# case 1
def case_1() -> Iterator[Circuit]:
    return createSimpleTransconductanceNonInvertingStages(
        list(TransconductanceManager().createSimpleTransconductance())[0],
        list(LoadManager().createSimpleMixedLoadNmos()),
        list(StageBiasManager().getOneTransistorStageBiasesNmos()),
    )


def case_2() -> Iterator[Circuit]:
    tc = list(TransconductanceManager().getComplementaryTransconductance())
    assert len(tc) == 1
    tc = tc[0]

    return createComplementaryTransconductanceNonInvertingStages(
        tc,
        list(LoadManager().createLoadsForComplementaryNonInvertingStage()),
        list(StageBiasManager().getOneTransistorStageBiasesNmos()),
        list(StageBiasManager().getOneTransistorStageBiasesPmos()),
    )


def main():
    methods: list[Callable[[], Iterator[Circuit]]] = [case_1, case_2]
    for case_id, create_method in enumerate(methods, start=1):
        circuits = list(create_method())
        print(f"case {case_id}: {create_method.__name__}, len = {len(circuits)}")
        for circuit_id, non_inv_stage in enumerate(circuits, start=1):
            save_graphviz_figure(
                non_inv_stage,
                GALLERY_DOT_DIR / f"n_inv_{case_id}_{circuit_id}.dot",
            )
            convert_dot_to_png(
                GALLERY_DOT_DIR / f"n_inv_{case_id}_{circuit_id}.dot",
                GALLERY_IMAGE_DIR / f"n_inv_{case_id}_{circuit_id}.png",
            )


def test_2_10():
    tc = list(TransconductanceManager().getComplementaryTransconductance())
    assert len(tc) == 1
    tc = tc[0]

    load = list(LoadManager().createLoadsForComplementaryNonInvertingStage())[9]
    sb_nmos = list(StageBiasManager().getOneTransistorStageBiasesNmos())[0]
    sb_pmos = list(StageBiasManager().getOneTransistorStageBiasesPmos())[0]
    non_inv_stage = createComplementaryTransconductanceNonInvertingStage(
        tc, load, sb_nmos, sb_pmos
    )
    case_id = 1
    circuit_id = 10
    save_graphviz_figure(
        non_inv_stage,
        GALLERY_DOT_DIR / f"n_inv_{case_id}_{circuit_id}xxx.dot",
    )
    convert_dot_to_png(
        GALLERY_DOT_DIR / f"n_inv_{case_id}_{circuit_id}xxx.dot",
        GALLERY_IMAGE_DIR / f"n_inv_{case_id}_{circuit_id}xxx.png",
    )
    print("num components:", non_inv_stage.component_count)


if __name__ == "__main__":
    main()
    # test_2_10()
