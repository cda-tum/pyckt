from src.topogen.HL3.lp import *
from src.topogen.HL2.vb import *
from src.topogen.common.circuit import *


from pathlib import Path
from typing import Callable, Iterator
from itertools import chain


# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "l" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "l" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

def connectInstanceTerminalsOfLoadPart1WithoutGCC(load: Load, loadPart: LoadPart):
    # Connect the loadPart instances to the load terminals
    # Assuming loadPart has two instances representing two transistor stacks

    # fmt: off
    connectInstanceTerminal(load, loadPart, "out1", "out1")
    connectInstanceTerminal(load, loadPart, "out2", "out2")
    connectInstanceTerminal(load, loadPart, "source_load1", "source")

    if loadPart.ts1.instances[0].name.startswith("vb") and loadPart.ts2.instances[
        0
    ].name.startswith("vb"):
        if loadPart.component_count > 2:
            connectInstanceTerminal(load, loadPart, "outoutput1_load1", "outoutput1")
            connectInstanceTerminal(load, loadPart, "outoutput2_load1", "outoutput2")
            connectInstanceTerminalInOrder((load, "outsource1_load1"), (loadPart, "outsource1"))
            connectInstanceTerminalInOrder((load, "outsource2_load1"), (loadPart, "outsource2"))
    else:
        if loadPart.component_count == 2:
            connectInstanceTerminal(load, loadPart, "inner_load1", "inner")

        if loadPart.component_count > 2:
            connectInstanceTerminal(load, loadPart, "inner_source_load1", "inner_source")

            if len(loadPart.ts1.instances) == 1 and loadPart.ts1.instances[
                0
            ].name.startswith("dt"):
                connectInstanceTerminal(
                    load, loadPart, "inner_output_load1", "inner_output"
                )

        if loadPart.component_count > 3:
            connectInstanceTerminal(load, loadPart, "inner_output_load1", "inner_output")
    if loadPart.component_count > 2:
        connectInstanceTerminal(
            load, loadPart, "inner_transistorstack2_load1", "inner_transistorstack2"
        )
    if loadPart.component_count > 3:
        connectInstanceTerminal(
            load, loadPart, "inner_transistorstack1_load1", "inner_transistorstack1"
        )
    return load

def addLoad1WithoutGCCNets(loadPart: LoadPart):
    # num_reviews: 1

    new_ports = ["source_load1"]
    if loadPart.instances[0].instances[0].name.startswith("vb") and loadPart.instances[1].instances[0].name.startswith("vb"):
        if loadPart.component_count > 2:
            new_ports += ["outoutput1_load1", "outoutput2_load1", "outsource1_load1", "outsource2_load1"]
    else:
        if loadPart.component_count ==2:
            new_ports += ["inner_load1"]
        
        if loadPart.component_count > 2:
            new_ports += ["inner_source_load1"]

            if loadPart.ts1.instances[0].component_count ==  1 and loadPart.ts1.instances[0].name.startswith("dt"):
                new_ports += ["inner_output_load1"]
        
        if loadPart.component_count > 3:
            new_ports += ["inner_output_load1"]

    if loadPart.component_count > 2:
        new_ports += ["inner_transistorstack2_load1"]
    if loadPart.component_count > 3:
        new_ports += ["inner_transistorstack1_load1"]
    return new_ports

def createOneLoadPartLoad(loadPart):
    l = Load(id=1, techtype="p")
    l.ports = [
        "out1",
        "out2",
        "source_load1",
    ]
    l.add_instance(loadPart)

    # fmt: off

    
    l.ports += addLoad1WithoutGCCNets(loadPart)
    l = connectInstanceTerminalsOfLoadPart1WithoutGCC(l, loadPart)
    # print (l.ports)
    # fmt: on

    # lp.add_instance(ts1)
    # lp.add_instance(ts2)

    # if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith(
    #     "vb"
    # ):
    #     lp.ports.append(["outoutput1", "outoutput2", "outsource1", "outsource2"])
    # else:
    #     lp.ports.append(["inneroutput", "innersouce"])

    # lp = connectInstanceTerminalsOfFourTransistorLoadPart(lp, ts1, ts2)
    # return lp
    return l

def addLoad2Nets(loadPart2: LoadPart):
    new_ports = []
    new_ports += ["source_load2"]

    # if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) == 2:
    if loadPart2.component_count == 2:
        new_ports += ["inner_load2"]
    # if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) > 2:
    if loadPart2.component_count > 2:
        new_ports += ["inner_source_load2", "inner_transistorstack2_load2"]

        if loadPart2.ts1.instances[0].component_count == 1 and loadPart2.ts1.instances[
            0
        ].name.startswith("dt"):
            new_ports += ["inner_output_load2"]
        
    # if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) > 3:
    if loadPart2.component_count > 3:
        new_ports += ["inner_output_load2", "inner_source_load2", "inner_transistorstack1_load2"]
    return new_ports

def connectInstanceTerminalsOfLoadPart2(load: Load, loadPart2: LoadPart):
    connectInstanceTerminal(load, loadPart2, "out1", "out1")
    connectInstanceTerminal(load, loadPart2, "out2", "out2")
    connectInstanceTerminal(load, loadPart2, "source_load2", "source")

    if loadPart2.component_count == 2:
        connectInstanceTerminal(load, loadPart2, "inner_load2", "inner")
    if loadPart2.component_count > 2:
        connectInstanceTerminal(load, loadPart2, "inner_source_load2", "inner_source")
        connectInstanceTerminal(load, loadPart2, "inner_transistorstack2_load2", "inner_transistorstack2")

        if loadPart2.ts1.instances[0].component_count == 1 and loadPart2.ts1.instances[
            0
        ].name.startswith("dt"):
            # connectInstanceTerminal(load, loadPart2, "inner_output_load2", "inner_output")
            connect((load, "inner_output_load2"), (loadPart2, "inner_output"))
    
    if loadPart2.component_count > 3:
        connectInstanceTerminal(load, loadPart2, "inner_output_load2", "inner_output")
        connectInstanceTerminal(load, loadPart2, "inner_transistorstack1_load2", "inner_transistorstack1")
    return load
def createTwoLoadPartLoadWithGCC(loadPartWithGCC, secondLoadPart):
    l = Load(id=1, techtype="p")
    l.ports = [
        "out1",
        "out2",
        # "source_load1",
    ]
    l.add_instance(loadPartWithGCC)
    l.add_instance(secondLoadPart)


    # fmt: off
    def addLoad1WithGCCNets(loadPart1: LoadPart):
        new_ports = []
        new_ports += ["source_gcc1", "source_gcc2", "inner_gcc"]
        if loadPart1.component_count > 2:
            new_ports += ["source_load1", "inner_bias_gcc"]
        return new_ports


    
    def connectInstanceTerminalsOfLoadPart1WithGCC(load: Load, loadPartWithGCC: LoadPart):
        connectInstanceTerminal(load, loadPartWithGCC, "out1", "out1")
        connectInstanceTerminal(load, loadPartWithGCC, "out2", "out2")

        if loadPartWithGCC.component_count == 2:
            connectInstanceTerminal(load, loadPartWithGCC, "source_gcc1", "source1")
            connectInstanceTerminal(load, loadPartWithGCC, "source_gcc2", "source2")
            connectInstanceTerminal(load, loadPartWithGCC, "inner_gcc", "inner")
        else:
            connectInstanceTerminal(load, loadPartWithGCC, "source_gcc1", "inner_transistorstack1")
            connectInstanceTerminal(load, loadPartWithGCC, "source_gcc2", "inner_transistorstack2")
            connectInstanceTerminal(load, loadPartWithGCC, "inner_gcc", "inner_output")
            connectInstanceTerminal(load, loadPartWithGCC, "source_load1", "source")
            connectInstanceTerminal(load, loadPartWithGCC, "inner_bias_gcc", "inner_source")
        return load



    l.ports += addLoad1WithGCCNets(loadPartWithGCC)
    l.ports += addLoad2Nets(secondLoadPart)

    l = connectInstanceTerminalsOfLoadPart1WithGCC(l, loadPartWithGCC)
    l = connectInstanceTerminalsOfLoadPart2(l, secondLoadPart)
    return l

def createTwoLoadPartLoadWithoutGCC(mixedLoadPart, currentBiasLoadPart):
    l = Load(id=1, techtype="p")
    l.ports = [
        "out1",
        "out2",
        # "source_load1",
    ]
    l.add_instance(mixedLoadPart)
    l.add_instance(currentBiasLoadPart)


    # fmt: off
    def addLoad1WithoutGCCNets(loadPart1: LoadPart):
        new_ports = []
        new_ports += ["source_load1"]
        if loadPart1.ts1.instances[0].name.startswith("vb") and loadPart1.ts2.instances[0].name.startswith("vb"):
            if loadPart1.component_count > 2:
                new_ports += ["outoutput1_load1", "outoutput2_load1", "outsource1_load1", "outsource2_load1"]
        else:
            if loadPart1.component_count ==2 :
                new_ports += ["inner_load1"]
            
            if loadPart1.component_count > 2:
                new_ports += ["inner_source_load1"]

                if loadPart1.ts1.instances[0].component_count ==  1 and loadPart1.ts1.instances[0].instances[0].name.startswith("dt"):
                    new_ports += ["inner_output_load1"]
            
            if loadPart1.component_count > 3:
                new_ports += ["inner_output_load1"]
        
        if loadPart1.component_count > 2:
            new_ports += ["inner_transistorstack2_load1"]
        
        if loadPart1.component_count > 3:
            new_ports += ["inner_transistorstack1_load1"]
        return new_ports


    
    def connectInstanceTerminalsOfLoadPart1WithoutGCC(load: Load, loadPart1: LoadPart):
        connectInstanceTerminal(load, loadPart1, "out1", "out1")
        connectInstanceTerminal(load, loadPart1, "out2", "out2")
        connectInstanceTerminal(load, loadPart1, "source_load1", "source")

        if loadPart1.ts1.instances[0].name.startswith("vb") and loadPart1.ts2.instances[0].name.startswith("vb"):
            if loadPart1.component_count > 2:
                connectInstanceTerminal(load, loadPart1, "outoutput1_load1", "outoutput1")
                connectInstanceTerminal(load, loadPart1, "outoutput2_load1", "outoutput2")
                connectInstanceTerminal(load, loadPart1, "outsource1_load1", "outsource1")
                connectInstanceTerminal(load, loadPart1, "outsource2_load1", "outsource2")
        else:
            if loadPart1.component_count ==2:
                connectInstanceTerminal(load, loadPart1, "inner_load1", "inner")
            
            if loadPart1.component_count >2:
                connectInstanceTerminal(load, loadPart1, "inner_source_load1", "inner_source")

                if loadPart1.ts1.instances[0].component_count == 1 and loadPart1.ts1.instances[
                    0
                ].name.startswith("dt"):
                    connectInstanceTerminal(load, loadPart1, "inner_output_load1", "inner_output")
            
            if loadPart1.component_count > 3:
                connectInstanceTerminal(load, loadPart1, "inner_output_load1", "inner_output")
        
        if loadPart1.component_count > 2:
            connectInstanceTerminal(
                load, loadPart1, "inner_transistorstack2_load1", "inner_transistorstack2"
            )
        if loadPart1.component_count > 3:
            connectInstanceTerminal(
                load, loadPart1, "inner_transistorstack1_load1", "inner_transistorstack1"
            )
        return load


    l.ports += addLoad1WithoutGCCNets(mixedLoadPart)
    l.ports += addLoad2Nets(currentBiasLoadPart)

    l = connectInstanceTerminalsOfLoadPart1WithoutGCC(l, mixedLoadPart)
    l = connectInstanceTerminalsOfLoadPart2(l, currentBiasLoadPart)
    return l


def createOneLoadPartLoads(loadParts) -> Iterator[Circuit]:
    for loadPart in loadParts:
        yield createOneLoadPartLoad(loadPart)

def createTwoLoadPartLoadsWithGCC(loadPartsGCC, secondLoadParts)-> Iterator[Circuit]:
    for loadPartWithGCC in loadPartsGCC:
        for secondLoadPart in secondLoadParts:
            yield createTwoLoadPartLoadWithGCC(loadPartWithGCC, secondLoadPart)

def createTwoLoadPartLoadsWithoutGCC(mixedLoadParts, currentBiasLoadParts)-> Iterator[Circuit]:
    for mixedLoadPart in mixedLoadParts:
        for currentBiasLoadPart in currentBiasLoadParts:
            yield createTwoLoadPartLoadWithoutGCC(mixedLoadPart, currentBiasLoadPart)


def createSymmetricalLoadFourTransistorMixedLoadParts(pmosLoadPart, nmosLoadPart):
    l = Load(id=1, techtype="p")
    l.ports = [
        "out1",
        "out2",
        # "source_load1",
    ]
    l.add_instance(pmosLoadPart)
    l.add_instance(nmosLoadPart)

    l.ports += addLoad1WithoutGCCNets(pmosLoadPart)
    l.ports += addLoad2Nets(nmosLoadPart)

    l = connectInstanceTerminalsOfLoadPart1WithoutGCC(l, pmosLoadPart)
    l = connectInstanceTerminalsOfLoadPart2(l, nmosLoadPart)
    return l



def createSymmetricalLoadsFourTransistorMixedLoadParts(pmosLoadParts,nmosLoadParts ) -> Iterator[Circuit]:
    for i in range(len(pmosLoadParts)):
        pmosLoadPart = pmosLoadParts[i]
        nmosLoadPart = nmosLoadParts[i]
        yield createSymmetricalLoadFourTransistorMixedLoadParts(pmosLoadPart, nmosLoadPart)

# case 1
def createSimpleMixedLoadPmos()->list[Circuit]:
    pmosLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    return createOneLoadPartLoads(pmosLoadParts)


# case 2
def createSimpleMixedLoadNmos():
    nmosLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    return createOneLoadPartLoads(nmosLoadParts)


# case 3
def createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos():
    pmosGCCLoadParts = (LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases())
    nmosSecondLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    return createTwoLoadPartLoadsWithGCC(pmosGCCLoadParts, nmosSecondLoadParts)

# case 4
def createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos():
    nmosGCCLoadParts = LoadPartManager().createLoadPartsNmosFourTransistorCurrentBiases()
    pmosSecondLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    return createTwoLoadPartLoadsWithGCC(nmosGCCLoadParts, pmosSecondLoadParts)

# case 5
def createLoadsTwoLoadPartsCascodeGCCMixedPmos():
    pmosGCCLoadParts = LoadPartManager().createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources()
    nmosSecondLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    return createTwoLoadPartLoadsWithGCC(pmosGCCLoadParts, nmosSecondLoadParts)

# case 6
def createLoadsTwoLoadPartsCascodeGCCMixedNmos():
    nmosGCCLoadParts = LoadPartManager().createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources()
    pmosSecondLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    return createTwoLoadPartLoadsWithGCC(nmosGCCLoadParts, pmosSecondLoadParts)

# case 7
def createLoadsTwoLoadPartsMixedCurrentBiasesPmos():
    nmosCurrentBiasLoadParts = LoadPartManager().createLoadPartsNmosCurrentBiases()
    pmosMixedLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    return createTwoLoadPartLoadsWithoutGCC(pmosMixedLoadParts, nmosCurrentBiasLoadParts)

# case 8
def createLoadsTwoLoadPartsMixedCurrentBiasesNmos():
    pmosCurrentBiasLoadParts = LoadPartManager().createLoadPartsPmosCurrentBiases()
    nmosMixedLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    return createTwoLoadPartLoadsWithoutGCC(nmosMixedLoadParts, pmosCurrentBiasLoadParts)

# case 9
def createLoadsPmosForFullyDifferentialNonInvertingStage():
    oneLoadPartLoadsCurrentBiasesPmos = createOneLoadPartLoads(LoadPartManager().createLoadPartsPmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesFoldedPmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases(),
                    LoadPartManager().createLoadPartsNmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesCascodeNmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources(),
            LoadPartManager().createLoadPartsPmosCurrentBiases())
    return chain(oneLoadPartLoadsCurrentBiasesPmos, twoLoadPartLoadsOnlyCurrentBiasesFoldedPmosGCC, twoLoadPartLoadsOnlyCurrentBiasesCascodeNmosGCC)

# case 10
def createLoadsNmosForFullyDifferentialNonInvertingStage():
    oneLoadPartLoadsCurrentBiasesNmos = createOneLoadPartLoads(LoadPartManager().createLoadPartsNmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesFoldedNmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsNmosFourTransistorCurrentBiases(),
            LoadPartManager().createLoadPartsPmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesCascodePmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources(),
            LoadPartManager().createLoadPartsNmosCurrentBiases())
    return chain(oneLoadPartLoadsCurrentBiasesNmos , twoLoadPartLoadsOnlyCurrentBiasesFoldedNmosGCC , twoLoadPartLoadsOnlyCurrentBiasesCascodePmosGCC)

# case 11
def createLoadsForComplementaryNonInvertingStage():
    pmosLoadParts = LoadPartManager().createLoadPartsPmosFourTransistorMixed()
    nmosLoadParts = LoadPartManager().createLoadPartsNmosFourTransistorMixed()
    loads = list(createSymmetricalLoadsFourTransistorMixedLoadParts(pmosLoadParts, nmosLoadParts))

    twoLoadPartLoadsMixedFoldedPmosGCC = list(createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases(),
    LoadPartManager().createLoadPartsNmosMixed()))
    twoLoadPartLoadsMixedFoldedNmosGCC = list(createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsNmosFourTransistorCurrentBiases(),
    LoadPartManager().createLoadPartsPmosMixed()))


    # TODO: filter out loads that have more than/less than 8 components
    for load in loads:
        yield load
    for load in twoLoadPartLoadsMixedFoldedPmosGCC + twoLoadPartLoadsMixedFoldedNmosGCC:
        if load.component_count == 8:
            yield load

# case 12
def createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage():
    pmosLoadParts = LoadPartManager().createTwoTransistorsLoadPartsLoadPartsPmosVoltageBiases()
    return createOneLoadPartLoads(pmosLoadParts)

# case 13
def createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage():
    pmosLoadParts = LoadPartManager().createFourTransistorsLoadPartsLoadPartsPmosVoltageBiases()
    return createOneLoadPartLoads(pmosLoadParts)


# case 14
def createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage():
    nmosLoadParts = LoadPartManager().createTwoTransistorsLoadPartsLoadPartsNmosVoltageBiases()
    return createOneLoadPartLoads(nmosLoadParts)

# case 15
def createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage():
    nmosLoadParts = LoadPartManager().createFourTransistorsLoadPartsLoadPartsNmosVoltageBiases()
    return createOneLoadPartLoads(nmosLoadParts)

# fmt: on
methods: list[list[Callable]] = [
    createSimpleMixedLoadPmos,
    createSimpleMixedLoadNmos,
    createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos,
    createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos,
    createLoadsTwoLoadPartsCascodeGCCMixedPmos,
    createLoadsTwoLoadPartsCascodeGCCMixedNmos,
    createLoadsTwoLoadPartsMixedCurrentBiasesPmos,
    createLoadsTwoLoadPartsMixedCurrentBiasesNmos,
    createLoadsPmosForFullyDifferentialNonInvertingStage,
    createLoadsNmosForFullyDifferentialNonInvertingStage,
    createLoadsForComplementaryNonInvertingStage,  # 11
    createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage,
    createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage,
    createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage,
    createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage,
]


class LoadManager:
    @staticmethod
    def createSimpleMixedLoadPmos():
        return createSimpleMixedLoadPmos()

    @staticmethod
    def createSimpleMixedLoadNmos():
        return createSimpleMixedLoadNmos()

    @staticmethod
    def createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos():
        return createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos()

    @staticmethod
    def createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos():
        return createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos()

    @staticmethod
    def createLoadsTwoLoadPartsCascodeGCCMixedPmos():
        return createLoadsTwoLoadPartsCascodeGCCMixedPmos()

    @staticmethod
    def createLoadsTwoLoadPartsCascodeGCCMixedNmos():
        return createLoadsTwoLoadPartsCascodeGCCMixedNmos()

    @staticmethod
    def createLoadsTwoLoadPartsMixedCurrentBiasesPmos():
        return createLoadsTwoLoadPartsMixedCurrentBiasesPmos()

    @staticmethod
    def createLoadsTwoLoadPartsMixedCurrentBiasesNmos():
        return createLoadsTwoLoadPartsMixedCurrentBiasesNmos()

    @staticmethod
    def createLoadsPmosForFullyDifferentialNonInvertingStage():
        return createLoadsPmosForFullyDifferentialNonInvertingStage()

    @staticmethod
    def createLoadsNmosForFullyDifferentialNonInvertingStage():
        return createLoadsNmosForFullyDifferentialNonInvertingStage()

    @staticmethod
    def createLoadsForComplementaryNonInvertingStage():
        return createLoadsForComplementaryNonInvertingStage()


if __name__ == "__main__":
    for case_id, create_method in enumerate(methods, start=1):
        circuits = list(create_method())
        print(f"case {case_id}: {create_method.__name__}, len = {len(circuits)}")
        for circuit_id, load in enumerate(circuits, start=1):
            save_graphviz_figure(
                load,
                GALLERY_DOT_DIR / f"l_{case_id}_{circuit_id}.dot",
            )
            convert_dot_to_png(
                GALLERY_DOT_DIR / f"l_{case_id}_{circuit_id}.dot",
                GALLERY_IMAGE_DIR / f"l_{case_id}_{circuit_id}.png",
            )
