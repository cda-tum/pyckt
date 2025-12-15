# from src.topogen.HL2 import *
# from src.topogen.HL3 import *

from src.topogen.common.circuit import *


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
    return stage


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
