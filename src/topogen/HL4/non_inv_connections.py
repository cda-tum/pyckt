# from src.topogen.HL2 import *
# from src.topogen.HL3 import *

from src.topogen.common.circuit import *


def connectInstanceTerminalsOfSimpleTransconductance(
    nonInvertingStage: NonInvertingStage, tc
) -> NonInvertingStage:
    # num_review: 2
    stage = nonInvertingStage
    connect((stage, "in1"), (tc, Transconductance.INPUT1))
    connect((stage, "in2"), (tc, Transconductance.INPUT2))
    connect((stage, "source_transconductance"), (tc, Transconductance.SOURCE))

    load = None
    for inst in stage.instances:
        if inst.name == "l":
            load = inst

    assert load != None
    if hasGCC(load):
        connect((stage, "source_gcc1"), (tc, Transconductance.OUT1))
        connect((stage, "source_gcc2"), (tc, Transconductance.OUT2))
    else:
        connect((stage, "out1"), (tc, Transconductance.OUT1))
        connect((stage, "out2"), (tc, Transconductance.OUT2))
    return stage


def connectInstanceTerminalsOfStageBiases(
    nonInvertingStage: NonInvertingStage, stageBias1: StageBias, stageBias2: StageBias
) -> NonInvertingStage:

    stage = nonInvertingStage
    connect((stage, "source_transconductance1"), (stageBias1, StageBias.OUT))
    connect((stage, "source_transconductance2"), (stageBias2, StageBias.OUT))

    if stageBias1.tech == "n":
        connect((stage, "source_nmos"), (stageBias1, StageBias.SOURCE))
        connect((stage, "source_nmos"), (stageBias2, StageBias.SOURCE))
    else:
        connect((stage, "source_pmos"), (stageBias1, StageBias.SOURCE))
        connect((stage, "source_pmos"), (stageBias2, StageBias.SOURCE))

    if stageBias1.component_count == 1:
        connect((stage, "input_stagebias"), (stageBias1, StageBias.IN))
        connect((stage, "input_stagebias"), (stageBias2, StageBias.IN))
    else:
        connect((stage, "in_source_stagebias"), (stageBias1, StageBias.INSOURCE))
        connect((stage, "in_output_stagebias"), (stageBias1, StageBias.INOUTPUT))
        connect((stage, "inner_stagebias1"), (stageBias1, StageBias.INNER))

        connect((stage, "in_source_stagebias"), (stageBias2, StageBias.INSOURCE))
        connect((stage, "in_output_stagebias"), (stageBias2, StageBias.INOUTPUT))
        connect((stage, "inner_stagebias2"), (stageBias2, StageBias.INNER))
    return stage


def connectInstanceTerminalsOfFeedbackTransconductanceXXX(
    nonInvertingStage: NonInvertingStage, tc: Transconductance
) -> NonInvertingStage:

    stage = nonInvertingStage

    connect((stage, "in1"), (tc, Transconductance.INPUT1))
    connect((stage, "in2"), (tc, Transconductance.INPUT2))
    connect((stage, "source_transconductance1"), (tc, Transconductance.SOURCE_1))
    connect((stage, "source_transconductance2"), (tc, Transconductance.SOURCE_2))
    connect((stage, "inner_transconductance"), (tc, Transconductance.INNER))
    connect((stage, "out1"), (tc, Transconductance.OUT1))
    connect((stage, "out2"), (tc, Transconductance.OUT2))
    return stage


def connectInstanceTerminalsOfLoadPart1(
    nonInvertingStage: NonInvertingStage, load: Load
) -> NonInvertingStage:
    # fmt: off
    loadPart1: LoadPart = load.instances[0]
    if not hasGCC(load) or loadPart1.component_count > 2:
        if loadPart1.ts1.tech == "n":
            connect((nonInvertingStage, "source_nmos"), (load, "source_load1"))
        else:
            connect((nonInvertingStage, "source_pmos"), (load, "source_load1"))
    
    
    if loadPart1.bothTransistorStacksAreVoltageBiases:
        if loadPart1.component_count > 2:
            connect((nonInvertingStage, "out_output1_load1"), (load, "out_output1_load1"))
            connect((nonInvertingStage, "out_output2_load1"), (load, "out_output2_load1"))
            connect((nonInvertingStage, "out_outsource1_load1"), (load, "out_outsource1_load1"))
            connect((nonInvertingStage, "out_outsource2_load1"), (load, "out_outsource2_load1"))
    elif hasGCC(load):
            connect((nonInvertingStage, "source_gcc1"), (load, "source_gcc1"))
            connect((nonInvertingStage, "source_gcc2"), (load, "source_gcc2"))
            connect((nonInvertingStage, "inner_gcc"), (load, "inner_gcc"))
            if loadPart1.component_count > 2:
                connect((nonInvertingStage, "inner_bias_gcc"), (load, "inner_bias_gcc"))
            
    else:
        if loadPart1.component_count == 2:
            connect((nonInvertingStage, "inner_load1"), (load, "inner_load1"))
        if loadPart1.component_count > 2:
            connect((nonInvertingStage, "inner_source_load1"), (load, "inner_source_load1"))
            if loadPart1.ts1.instances[0].component_count == 1 and loadPart1.ts1.instances[0].name == "dt":
                connect((nonInvertingStage, "inner_output_load1"), (load, "inner_output_load1"))
        
            if loadPart1.component_count > 3:
                connect((nonInvertingStage, "inner_output_load1"), (load, "inner_output_load1"))
        
    if not hasGCC(load):
        if loadPart1.component_count > 2:
            connect((nonInvertingStage, "inner_transistorstack2_load1"), (load, "inner_transistorstack2_load1"))
        if loadPart1.component_count > 3:
            connect((nonInvertingStage, "inner_transistorstack1_load1"), (load, "inner_transistorstack1_load1"))
    return nonInvertingStage
    # fmt: on


def connectInstanceTerminalsOfLoadPart2XXX(
    nonInvertingStage: NonInvertingStage, load: Load
) -> NonInvertingStage:
    loadPart2 = load.instances[1]
    if loadPart2.tech == "n":
        connect((nonInvertingStage, "source_nmos"), (load, "source_load2"))
    else:
        connect((nonInvertingStage, "source_pmos"), (load, "source_load2"))

    if loadPart2.component_count == 2:
        connect((nonInvertingStage, "inner_load2"), (load, "inner_load2"))
    if loadPart2.component_count > 2:
        connect((nonInvertingStage, "inner_source_load2"), (load, "inner_source_load2"))
        connect(
            (nonInvertingStage, "inner_transistorstack2_load2"),
            (load, "inner_transistorstack2_load2"),
        )
        if loadPart2.instances[0].component_count == 1 and loadPart2.instances[
            0
        ].instances[0].name.startswith("dt"):
            connect(
                (nonInvertingStage, "inner_output_load2"), (load, "inner_output_load2")
            )

    if loadPart2.component_count > 3:
        connect((nonInvertingStage, "inner_output_load2"), (load, "inner_output_load2"))
        connect(
            (nonInvertingStage, "inner_transistorstack1_load2"),
            (load, "inner_transistorstack1_load2"),
        )

    return nonInvertingStage


def connectInstanceTerminalsOfLoad(
    nonInvertingStage: NonInvertingStage, load
) -> NonInvertingStage:
    connect((nonInvertingStage, "out1"), (load, "out1"))
    connect((nonInvertingStage, "out2"), (load, "out2"))

    # TODO: uncomment the following line.
    nonInvertingStage = connectInstanceTerminalsOfLoadPart1(nonInvertingStage, load)
    if len(load.instances) == 2:
        nonInvertingStage = connectInstanceTerminalsOfLoadPart2XXX(
            nonInvertingStage, load
        )
    return nonInvertingStage


def connectInstanceTerminalsOfStageBias(
    nonInvertingStage: NonInvertingStage, stageBias: StageBias
) -> NonInvertingStage:
    connect((nonInvertingStage, "source_transconductance"), (stageBias, StageBias.OUT))
    if stageBias.tech == "n":
        connect((nonInvertingStage, "source_nmos"), (stageBias, StageBias.SOURCE))
    else:
        connect((nonInvertingStage, "source_pmos"), (stageBias, StageBias.SOURCE))

    if stageBias.component_count == 1:
        connect((nonInvertingStage, "input_stage_bias"), (stageBias, StageBias.IN))
    else:
        connect(
            (nonInvertingStage, "in_source_stage_bias"), (stageBias, StageBias.INSOURCE)
        )
        connect(
            (nonInvertingStage, "in_output_stage_bias"), (stageBias, StageBias.INOUTPUT)
        )
        connect((nonInvertingStage, "inner_stage_bias"), (stageBias, StageBias.INNER))
    return nonInvertingStage


def connectInstanceTerminalsOfComplementaryTransconductanceNonInv(
    stage: NonInvertingStage, tc: Transconductance
) -> NonInvertingStage:
    # fmt: off
    connect((stage, "in1"), (tc, "input1"))
    connect((stage, "in2"), (tc, "input2"))
    connect((stage, "source_transconductance_nmos"), (tc, Transconductance.SOURCE_NMOS))
    connect((stage, "source_transconductance_pmos"), (tc, Transconductance.SOURCE_PMOS))

    connect((stage, "inner_transistorstack1_load_pmos"), (tc, Transconductance.OUT1NMOS))
    connect((stage, "inner_transistorstack2_load_pmos"), (tc, Transconductance.OUT2NMOS))

    connect((stage, "inner_transistorstack1_load_nmos"), (tc, Transconductance.OUT1PMOS))
    connect((stage, "inner_transistorstack2_load_nmos"), (tc, Transconductance.OUT2PMOS))
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
    # fmt: off
    connect((nonInvertingStage, "source_transconductance_nmos"), (stageBiasNmos, StageBias.OUT))
    connect((nonInvertingStage, "source_transconductance_pmos"), (stageBiasPmos, StageBias.OUT))

    connect((nonInvertingStage, "source_nmos"), (stageBiasNmos, StageBias.SOURCE))
    connect((nonInvertingStage, "source_pmos"), (stageBiasPmos, StageBias.SOURCE))

    if stageBiasNmos.component_count == 1:
        connect((nonInvertingStage, "input_stagebias_nmos"), (stageBiasNmos, StageBias.IN))
        connect((nonInvertingStage, "input_stagebias_pmos"), (stageBiasPmos, StageBias.IN))
    else:
        connect(
            (nonInvertingStage, "insource_stagebias_nmos"), (stageBiasNmos, StageBias.INSOURCE)
        )
        connect(
            (nonInvertingStage, "in_output_stagebias_nmos"), (stageBiasNmos, StageBias.INOUTPUT)
        )
        connect((nonInvertingStage, "inner_stagebias_nmos"), (stageBiasNmos, StageBias.INNER))

        connect(
            (nonInvertingStage, "insource_stagebias_pmos"), (stageBiasPmos, StageBias.INSOURCE)
        )
        connect(
            (nonInvertingStage, "in_output_stagebias_pmos"), (stageBiasPmos, StageBias.INOUTPUT)
        )
        connect((nonInvertingStage, "inner_stagebias_pmos"), (stageBiasPmos, StageBias.INNER))
    return nonInvertingStage
