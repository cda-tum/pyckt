# from src.topogen.HL2 import *
# from src.topogen.HL3 import *

from src.topogen.common.circuit import *


def connectInstanceTerminalsOfSimpleTransconductance(
    nonInvertingStage: NonInvertingStage, tc
) -> NonInvertingStage:
    # num_review: 2
    stage = nonInvertingStage
    connect((stage, NonInvertingStage.IN1), (tc, Transconductance.INPUT1))
    connect((stage, NonInvertingStage.IN2), (tc, Transconductance.INPUT2))
    connect(
        (stage, NonInvertingStage.SOURCETRANSCONDUCTANCE), (tc, Transconductance.SOURCE)
    )

    load = None
    for inst in stage.instances:
        if inst.name == "l":
            load = inst

    assert load != None
    if hasGCC(load):
        connect((stage, NonInvertingStage.SOURCEGCC1), (tc, Transconductance.OUT1))
        connect((stage, NonInvertingStage.SOURCEGCC2), (tc, Transconductance.OUT2))
    else:
        connect((stage, NonInvertingStage.OUT1), (tc, Transconductance.OUT1))
        connect((stage, NonInvertingStage.OUT2), (tc, Transconductance.OUT2))
    return stage


def connectInstanceTerminalsOfStageBiases(
    nonInvertingStage: NonInvertingStage, stageBias1: StageBias, stageBias2: StageBias
) -> NonInvertingStage:
    # fmt: off
    stage = nonInvertingStage
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCE1), (stageBias1, StageBias.OUT))
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCE2), (stageBias2, StageBias.OUT))

    if stageBias1.tech == "n":
        connect((stage, NonInvertingStage.SOURCENMOS), (stageBias1, StageBias.SOURCE))
        connect((stage, NonInvertingStage.SOURCENMOS), (stageBias2, StageBias.SOURCE))
    else:
        connect((stage, NonInvertingStage.SOURCEPMOS), (stageBias1, StageBias.SOURCE))
        connect((stage, NonInvertingStage.SOURCEPMOS), (stageBias2, StageBias.SOURCE))

    if stageBias1.component_count == 1:
        connect((stage, NonInvertingStage.INPUTSTAGEBIAS), (stageBias1, StageBias.IN))
        connect((stage, NonInvertingStage.INPUTSTAGEBIAS), (stageBias2, StageBias.IN)) # TODO: check again ?
    else:
        connect((stage, NonInvertingStage.INSOURCESTAGEBIAS), (stageBias1, StageBias.INSOURCE))
        connect((stage, NonInvertingStage.INOUTPUTSTAGEBIAS), (stageBias1, StageBias.INOUTPUT))
        connect((stage, NonInvertingStage.INNERSTAGEBIAS1), (stageBias1, StageBias.INNER))

        connect((stage, NonInvertingStage.INSOURCESTAGEBIAS), (stageBias2, StageBias.INSOURCE))
        connect((stage, NonInvertingStage.INOUTPUTSTAGEBIAS), (stageBias2, StageBias.INOUTPUT))
        connect((stage, NonInvertingStage.INNERSTAGEBIAS2), (stageBias2, StageBias.INNER))
    return stage


def connectInstanceTerminalsOfFeedbackTransconductanceXXX(
    nonInvertingStage: NonInvertingStage, tc: Transconductance
) -> NonInvertingStage:

    stage = nonInvertingStage
    # fmt: off
    connect((stage, NonInvertingStage.IN1), (tc, Transconductance.INPUT1))
    connect((stage, NonInvertingStage.IN2), (tc, Transconductance.INPUT2))
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCE1), (tc, Transconductance.SOURCE_1))
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCE2), (tc, Transconductance.SOURCE_2))
    connect((stage, NonInvertingStage.INNERTRANSCONDUCTANCE), (tc, Transconductance.INNER))
    connect((stage, NonInvertingStage.OUT1), (tc, Transconductance.OUT1))
    connect((stage, NonInvertingStage.OUT2), (tc, Transconductance.OUT2))
    return stage


def connectInstanceTerminalsOfLoadPart1(
    nonInvertingStage: NonInvertingStage, load: Load
) -> NonInvertingStage:
    # fmt: off
    stage = nonInvertingStage
    loadPart1: LoadPart = load.instances[0]
    if not hasGCC(load) or loadPart1.component_count > 2:
        if loadPart1.ts1.tech == "n":
            connect((stage, NonInvertingStage.SOURCENMOS), (load, "source_load1"))
        else:
            connect((stage, NonInvertingStage.SOURCEPMOS), (load, "source_load1"))
    
    
    if loadPart1.bothTransistorStacksAreVoltageBiases:
        if loadPart1.component_count > 2:
            connect((stage, NonInvertingStage.OUTOUTPUT1LOAD1), (load, "out_output1_load1"))
            connect((stage, NonInvertingStage.OUTOUTPUT2LOAD1), (load, "out_output2_load1"))
            connect((stage, NonInvertingStage.OUTSOURCE1LOAD1), (load, "out_outsource1_load1"))
            connect((stage, NonInvertingStage.OUTSOURCE2LOAD1), (load, "out_outsource2_load1"))
    elif hasGCC(load):
            connect((stage, NonInvertingStage.SOURCEGCC1), (load, "source_gcc1"))
            connect((stage, NonInvertingStage.SOURCEGCC2), (load, "source_gcc2"))
            connect((stage, NonInvertingStage.INNERGCC), (load, "inner_gcc"))
            if loadPart1.component_count > 2:
                connect((stage, NonInvertingStage.INNERBIASGCC), (load, "inner_bias_gcc"))
            
    else:
        if loadPart1.component_count == 2:
            connect((stage, NonInvertingStage.INNERLOAD1), (load, "inner_load1"))
        if loadPart1.component_count > 2:
            connect((stage, NonInvertingStage.INNERSOURCELOAD1), (load, "inner_source_load1"))
            if loadPart1.ts1.instances[0].component_count == 1 and loadPart1.ts1.instances[0].name == "dt":
                connect((stage, NonInvertingStage.INNEROUTPUTLOAD1), (load, "inner_output_load1"))
        
            if loadPart1.component_count > 3:
                connect((stage, NonInvertingStage.INNEROUTPUTLOAD1), (load, "inner_output_load1"))
        
    if not hasGCC(load):
        if loadPart1.component_count > 2:
            connect((stage, NonInvertingStage.INNERTRANSISTORSTACK2LOAD1), (load, "inner_transistorstack2_load1"))
        if loadPart1.component_count > 3:
            connect((stage, NonInvertingStage.INNERTRANSISTORSTACK1LOAD1), (load, "inner_transistorstack1_load1"))
    return stage
    # fmt: on


def connectInstanceTerminalsOfLoadPart2XXX(
    nonInvertingStage: NonInvertingStage, load: Load
) -> NonInvertingStage:
    # fmt: off
    stage = nonInvertingStage
    loadPart2 = load.instances[1]
    if loadPart2.tech == "n":
        connect((stage, NonInvertingStage.SOURCENMOS), (load, "source_load2"))
    else:
        connect((stage, NonInvertingStage.SOURCEPMOS), (load, "source_load2"))

    if loadPart2.component_count == 2:
        connect((stage, NonInvertingStage.INNERLOAD2), (load, "inner_load2"))
    if loadPart2.component_count > 2:
        connect((stage, NonInvertingStage.INNERSOURCELOAD2), (load, "inner_source_load2"))
        connect(
            (stage, NonInvertingStage.INNERTRANSISTORSTACK2LOAD2),
            (load, "inner_transistorstack2_load2"),
        )
        if loadPart2.instances[0].component_count == 1 and loadPart2.instances[
            0
        ].instances[0].name.startswith("dt"):
            connect(
                (stage, NonInvertingStage.INNEROUTPUTLOAD2), (load, "inner_output_load2")
            )

    if loadPart2.component_count > 3:
        connect((stage,  NonInvertingStage.INNEROUTPUTLOAD2), (load, "inner_output_load2")) 
        connect(
            (stage, NonInvertingStage.INNERTRANSISTORSTACK1LOAD2), 
            (load, "inner_transistorstack1_load2"),
        )

    return stage


def connectInstanceTerminalsOfLoad(
    nonInvertingStage: NonInvertingStage, load
) -> NonInvertingStage:
    connect((nonInvertingStage, NonInvertingStage.OUT1), (load, "out1"))
    connect((nonInvertingStage, NonInvertingStage.OUT2), (load, "out2"))

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
    stage = nonInvertingStage
    # fmt: off
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCE), (stageBias, StageBias.OUT))
    if stageBias.tech == "n":
        connect((stage, NonInvertingStage.SOURCENMOS), (stageBias, StageBias.SOURCE))
    else:
        connect((stage, NonInvertingStage.SOURCEPMOS), (stageBias, StageBias.SOURCE))

    if stageBias.component_count == 1:
        connect((stage, NonInvertingStage.INPUTSTAGEBIAS), (stageBias, StageBias.IN))
    else:
        connect((stage, NonInvertingStage.INSOURCESTAGEBIAS), (stageBias, StageBias.INSOURCE))
        connect((stage, NonInvertingStage.INOUTPUTSTAGEBIAS), (stageBias, StageBias.INOUTPUT))
        connect((stage, NonInvertingStage.INNERSTAGEBIAS), (stageBias, StageBias.INNER))
    return stage


def connectInstanceTerminalsOfComplementaryTransconductanceNonInv(
    stage: NonInvertingStage, tc: Transconductance
) -> NonInvertingStage:
    # fmt: off
    connect((stage, NonInvertingStage.IN1), (tc, "input1"))
    connect((stage, NonInvertingStage.IN2), (tc, "input2"))
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCENMOS), (tc, Transconductance.SOURCE_NMOS))
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCEPMOS), (tc, Transconductance.SOURCE_PMOS))

    connect((stage, NonInvertingStage.INNERTRANSISTORSTACK1LOADPMOS), (tc, Transconductance.OUT1NMOS))
    connect((stage, NonInvertingStage.INNERTRANSISTORSTACK2LOADPMOS), (tc, Transconductance.OUT2NMOS))

    connect((stage, NonInvertingStage.INNERTRANSISTORSTACK1LOADNMOS), (tc, Transconductance.OUT1PMOS))
    connect((stage, NonInvertingStage.INNERTRANSISTORSTACK2LOADNMOS), (tc, Transconductance.OUT2PMOS))
    # fmt: on

    return stage


def connectInstanceTerminalsOfComplementaryLoad(
    nonInvertingStage: NonInvertingStage, load: Load
) -> NonInvertingStage:
    # fmt: off
    loadPart1 = load.instances[0]
    loadPart2 = load.instances[1]
    stage = nonInvertingStage

    connect((stage, NonInvertingStage.OUT1), (load, "out1"))
    connect((stage, NonInvertingStage.OUT2), (load, "out2"))

    if loadPart1.tech == "n":
        connect((stage, NonInvertingStage.SOURCENMOS), (load, "source_load1"))
        connect((stage, NonInvertingStage.SOURCEPMOS), (load, "source_load2"))

        if hasGCC(load):
            connect((stage, NonInvertingStage.INNERTRANSISTORSTACK1LOADNMOS), (load, "source_gcc1"))
            connect((stage, NonInvertingStage.INNERTRANSISTORSTACK2LOADNMOS), (load, "source_gcc2"))
            connect((stage, NonInvertingStage.INNEROUTPUTLOADNMOS), (load, "inner_gcc"))
            connect((stage, NonInvertingStage.INNERSOURCELOADNMOS), (load, "inner_bias_gcc"))
        else:
            connect((stage, NonInvertingStage.INNERTRANSISTORSTACK1LOADNMOS), (load, "inner_transistorstack1_load1"))
            connect((stage, NonInvertingStage.INNERTRANSISTORSTACK2LOADNMOS), (load, "inner_transistorstack2_load1"))
            connect((stage, NonInvertingStage.INNEROUTPUTLOADNMOS), (load, "inner_output_load1"))
            connect((stage, NonInvertingStage.INNERSOURCELOADNMOS), (load, "inner_source_load1"))
        
        connect((stage, NonInvertingStage.INNERTRANSISTORSTACK1LOADPMOS), (load, "inner_transistorstack1_load2"))
        connect((stage, NonInvertingStage.INNERTRANSISTORSTACK2LOADPMOS), (load, "inner_transistorstack2_load2"))
        connect((stage, NonInvertingStage.INNEROUTPUTLOADPMOS), (load, "inner_output_load2"))
        connect((stage, NonInvertingStage.INNERSOURCELOADPMOS), (load, "inner_source_load2"))
        return stage

    else:
        connect((nonInvertingStage, NonInvertingStage.SOURCEPMOS), (load, "source_load1"))
        connect((nonInvertingStage, NonInvertingStage.SOURCENMOS), (load, "source_load2"))

        if hasGCC(load):
            connect((nonInvertingStage, NonInvertingStage.INNERTRANSISTORSTACK1LOADPMOS), (load, "source_gcc1")) 
            connect((nonInvertingStage, NonInvertingStage.INNERTRANSISTORSTACK2LOADPMOS), (load, "source_gcc2"))
            connect((nonInvertingStage, NonInvertingStage.INNEROUTPUTLOADPMOS), (load, "inner_gcc"))
            connect((nonInvertingStage, NonInvertingStage.INNERSOURCELOADPMOS), (load, "inner_bias_gcc"))
        else:
            connect((nonInvertingStage, NonInvertingStage.INNERTRANSISTORSTACK1LOADPMOS), (load, "inner_transistorstack1_load1"))
            connect((nonInvertingStage, NonInvertingStage.INNERTRANSISTORSTACK2LOADPMOS), (load, "inner_transistorstack2_load1"))
            connect((nonInvertingStage, NonInvertingStage.INNEROUTPUTLOADPMOS), (load, "inner_output_load1"))
            connect((nonInvertingStage, NonInvertingStage.INNERSOURCELOADPMOS), (load, "inner_source_load1"))

        connect((nonInvertingStage, NonInvertingStage.INNERTRANSISTORSTACK1LOADPMOS), (load, "inner_transistorstack1_load2"))
        connect((nonInvertingStage, NonInvertingStage.INNERTRANSISTORSTACK2LOADPMOS), (load, "inner_transistorstack2_load2"))
        connect((nonInvertingStage, NonInvertingStage.INNEROUTPUTLOADNMOS), (load, "inner_output_load2"))
        connect((nonInvertingStage, NonInvertingStage.INNERSOURCELOADNMOS), (load, "inner_source_load2"))
        return nonInvertingStage
    # fmt: on


def connectInstanceTerminalsOfComplementaryStageBiases(
    nonInvertingStage: NonInvertingStage,
    stageBiasNmos: StageBias,
    stageBiasPmos: StageBias,
) -> NonInvertingStage:
    # fmt: off
    stage = nonInvertingStage
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCENMOS), (stageBiasNmos, StageBias.OUT))
    connect((stage, NonInvertingStage.SOURCETRANSCONDUCTANCEPMOS), (stageBiasPmos, StageBias.OUT))

    connect((stage, NonInvertingStage.SOURCENMOS), (stageBiasNmos, StageBias.SOURCE))
    connect((stage, NonInvertingStage.SOURCEPMOS), (stageBiasPmos, StageBias.SOURCE))

    if stageBiasNmos.component_count == 1:
        connect((stage, NonInvertingStage.INPUTSTAGEBIASNMOS), (stageBiasNmos, StageBias.IN))
        connect((stage, NonInvertingStage.INPUTSTAGEBIASPMOS), (stageBiasPmos, StageBias.IN))
    else:
        connect((stage, NonInvertingStage.INSOURCESTAGEBIASNMOS), (stageBiasNmos, StageBias.INSOURCE))
        connect((stage, NonInvertingStage.INOUTPUTSTAGEBIASNMOS), (stageBiasNmos, StageBias.INOUTPUT))
        connect((stage, NonInvertingStage.INNERSTAGEBIASNMOS), (stageBiasNmos, StageBias.INNER))
        connect((stage, NonInvertingStage.INSOURCESTAGEBIASPMOS), (stageBiasPmos, StageBias.INSOURCE))
        connect((stage, NonInvertingStage.INOUTPUTSTAGEBIASPMOS), (stageBiasPmos, StageBias.INOUTPUT))
        connect((stage, NonInvertingStage.INNERSTAGEBIASPMOS), (stageBiasPmos, StageBias.INNER))
    return nonInvertingStage
