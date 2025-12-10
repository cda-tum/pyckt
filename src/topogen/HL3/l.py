from src.topogen.HL3.lp import *
from src.topogen.HL2.vb import *
from src.topogen.common.circuit import *


from pathlib import Path
from typing import Callable

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
        if len(loadPart.ts1.instances[0].instances) + len(loadPart.ts2.instances[0].instances) > 2:
            connectInstanceTerminal(load, loadPart, "outoutput1_load1", "outoutput1")
            connectInstanceTerminal(load, loadPart, "outoutput2_load1", "outoutput2")
            connectInstanceTerminal(load, loadPart, "outsource1_load1", "outsource1")
            connectInstanceTerminal(load, loadPart, "outsource2_load1", "outsource2")
    else:
        if len(loadPart.ts1.instances[0].instances) + len(loadPart.ts2.instances[0].instances) == 2:
            connectInstanceTerminal(load, loadPart, "inner_load1", "inner")

        if len(loadPart.ts1.instances[0].instances) + len(loadPart.ts2.instances[0].instances) > 2:
            connectInstanceTerminal(load, loadPart, "innersource_load1", "inner_source")

            if len(loadPart.ts1.instances) == 1 and loadPart.ts1.instances[
                0
            ].name.startswith("dt"):
                connectInstanceTerminal(
                    load, loadPart, "inneroutput_load1", "inner_output"
                )

        if len(loadPart.ts1.instances[0].instances) + len(loadPart.ts2.instances[0].instances) > 3:
            connectInstanceTerminal(load, loadPart, "inneroutput_load1", "inner_output")
    if len(loadPart.ts1.instances[0].instances) + len(loadPart.ts2.instances[0].instances) > 2:
        connectInstanceTerminal(
            load, loadPart, "inner_transistorstack2_load1", "inner_transistorstack2"
        )
    if len(loadPart.ts1.instances[0].instances) + len(loadPart.ts2.instances[0].instances) > 3:
        connectInstanceTerminal(
            load, loadPart, "inner_transistorstack1_load1", "inner_transistorstack1"
        )
    return load

def addLoad1WithoutGCCNets(loadPart):
    new_ports = []
    # print (len(loadPart.instances[1].instances[0].instances))
    # print (loadPart.instances[1].instances[0].name)

    if loadPart.instances[0].instances[0].name.startswith("vb") and loadPart.instances[1].instances[0].name.startswith("vb"):
        if len(loadPart.instances[0].instances[0].instances)  + len(loadPart.instances[1].instances[0].instances) > 2:
            new_ports += ["outoutput1_load1", "outoutput2_load1", "outsource1_load1", "outsource2_load1"]
    else:
        if len(loadPart.instances[0].instances[0].instances)  + len(loadPart.instances[1].instances[0].instances) == 2:
            new_ports += ["inner_load1"]
        
        if len(loadPart.instances[0].instances[0].instances)  + len(loadPart.instances[1].instances[0].instances) > 2:
            new_ports += ["innersource_load1"]

            if len(loadPart.instances[0].instances[0].instances) ==  1 and loadPart.instances[0].instances[0].instances[0].name.startswith("dt"):
                new_ports += ["inneroutput_load1"]
        
        if len(loadPart.instances[0].instances[0].instances)  + len(loadPart.instances[1].instances[0].instances) > 3:
            new_ports += ["inneroutput_load1"]
    

    if len(loadPart.instances[0].instances[0].instances)  + len(loadPart.instances[1].instances[0].instances) == 2:
        new_ports += ["inner_transistorstack2_load1"]
    if len(loadPart.instances[0].instances[0].instances)  + len(loadPart.instances[1].instances[0].instances) == 2:
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

def addLoad2Nets(loadPart2):
    new_ports = []
    new_ports += ["source_load2"]

    if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) == 2:
        new_ports += ["inner_load2"]
    if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) > 2:
        new_ports += ["innersource_load2", "inner_transistorstack2_load2"]

        if len(loadPart2.ts1.instances[0].instances) == 1 and loadPart2.ts1.instances[
            0
        ].name.startswith("dt"):
            new_ports += ["inneroutput_load2"]
    
    if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) > 3:
        new_ports += ["inneroutput_load2", "innersource_load2", "inner_transistorstack1_load2"]
    return new_ports

def connectInstanceTerminalsOfLoadPart2(load: Load, loadPart2: LoadPart):
    connectInstanceTerminal(load, loadPart2, "out1", "out1")
    connectInstanceTerminal(load, loadPart2, "out2", "out2")
    connectInstanceTerminal(load, loadPart2, "source_load2", "source")

    if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) == 2:
        connectInstanceTerminal(load, loadPart2, "inner_load2", "inner")
    if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) > 2:
        connectInstanceTerminal(load, loadPart2, "innersource_load2", "inner_source")
        connectInstanceTerminal(load, loadPart2, "inner_transistorstack2_load2", "inner_transistorstack2")

        if len(loadPart2.ts1.instances[0].instances) == 1 and loadPart2.ts1.instances[
            0
        ].name.startswith("dt"):
            connectInstanceTerminal(load, loadPart2, "inneroutput_load2", "inner_output")
    
    if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) > 3:
        connectInstanceTerminal(load, loadPart2, "inneroutput_load2", "inner_output")
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
    def addLoad1WithGCCNets(loadPart1):
        new_ports = []
        new_ports += ["source_gcc1", "source_gcc2", "inner_gcc"]
        if len(loadPart1.ts1.instances[0].instances) + len(loadPart1.ts2.instances[0].instances) > 2:
            new_ports += ["source_load1", "inner_bias_gcc"]
        return new_ports


    
    def connectInstanceTerminalsOfLoadPart1WithGCC(load: Load, loadPartWithGCC: LoadPart):
        connectInstanceTerminal(load, loadPartWithGCC, "out1", "out1")
        connectInstanceTerminal(load, loadPartWithGCC, "out2", "out2")

        if len(loadPartWithGCC.ts1.instances[0].instances) + len(loadPartWithGCC.ts2.instances[0].instances) == 2:
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
    def addLoad1WithoutGCCNets(loadPart1):
        new_ports = []
        new_ports += ["source_load1"]
        if loadPart1.ts1.instances[0].name.startswith("vb") and loadPart1.ts2.instances[0].name.startswith("vb"):
            if len(loadPart1.ts1.instances[0].instances)  + len(loadPart1.ts2.instances[0].instances) > 2:
                new_ports += ["outoutput1_load1", "outoutput2_load1", "outsource1_load1", "outsource2_load1"]
        else:
            if len(loadPart1.ts1.instances[0].instances)  + len(loadPart1.ts2.instances[0].instances) == 2:
                new_ports += ["inner_load1"]
            
            if len(loadPart1.ts1.instances[0].instances)  + len(loadPart1.ts2.instances[0].instances) > 2:
                new_ports += ["innersource_load1"]

                if len(loadPart1.ts1.instances[0].instances) ==  1 and loadPart1.ts1.instances[0].instances[0].name.startswith("dt"):
                    new_ports += ["inneroutput_load1"]
            
            if len(loadPart1.ts1.instances[0].instances)  + len(loadPart1.ts2.instances[0].instances) > 3:
                new_ports += ["inneroutput_load1"]
        
        if len(loadPart1.ts1.instances[0].instances)  + len(loadPart1.ts2.instances[0].instances) == 2:
            new_ports += ["inner_transistorstack2_load1"]
        
        if len(loadPart1.ts1.instances[0].instances)  + len(loadPart1.ts2.instances[0].instances) > 3:
            new_ports += ["inner_transistorstack1_load1"]
        return new_ports


    
    def connectInstanceTerminalsOfLoadPart1WithoutGCC(load: Load, loadPart1: LoadPart):
        connectInstanceTerminal(load, loadPart1, "out1", "out1")
        connectInstanceTerminal(load, loadPart1, "out2", "out2")
        connectInstanceTerminal(load, loadPart1, "source_load1", "source")

        if loadPart1.ts1.instances[0].name.startswith("vb") and loadPart1.ts2.instances[0].name.startswith("vb"):
            if len(loadPart1.ts1.instances[0].instances) + len(loadPart1.ts2.instances[0].instances) > 2:
                connectInstanceTerminal(load, loadPart1, "outoutput1_load1", "outoutput1")
                connectInstanceTerminal(load, loadPart1, "outoutput2_load1", "outoutput2")
                connectInstanceTerminal(load, loadPart1, "outsource1_load1", "outsource1")
                connectInstanceTerminal(load, loadPart1, "outsource2_load1", "outsource2")
        else:
            if len(loadPart1.ts1.instances[0].instances) + len(loadPart1.ts2.instances[0].instances) == 2:
                connectInstanceTerminal(load, loadPart1, "inner_load1", "inner")
            
            if len(loadPart1.ts1.instances[0].instances) + len(loadPart1.ts2.instances[0].instances) > 2:
                connectInstanceTerminal(load, loadPart1, "innersource_load1", "inner_source")

                if len(loadPart1.ts1.instances[0].instances) == 1 and loadPart1.ts1.instances[
                    0
                ].name.startswith("dt"):
                    connectInstanceTerminal(load, loadPart1, "inneroutput_load1", "inner_output")
            
            if len(loadPart1.ts1.instances[0].instances) + len(loadPart1.ts2.instances[0].instances) > 3:
                connectInstanceTerminal(load, loadPart1, "inneroutput_load1", "inner_output")
        
        if len(loadPart1.ts1.instances[0].instances) + len(loadPart1.ts2.instances[0].instances) > 2:
            connectInstanceTerminal(
                load, loadPart1, "inner_transistorstack2_load1", "inner_transistorstack2"
            )
        if len(loadPart1.ts1.instances[0].instances) + len(loadPart1.ts2.instances[0].instances) > 3:
            connectInstanceTerminal(
                load, loadPart1, "inner_transistorstack1_load1", "inner_transistorstack1"
            )
        return load


    l.ports += addLoad1WithoutGCCNets(mixedLoadPart)
    l.ports += addLoad2Nets(currentBiasLoadPart)

    l = connectInstanceTerminalsOfLoadPart1WithoutGCC(l, mixedLoadPart)
    l = connectInstanceTerminalsOfLoadPart2(l, currentBiasLoadPart)
    return l


def createOneLoadPartLoads(loadParts):
    out = []
    for loadPart in loadParts:
        load = createOneLoadPartLoad(loadPart)
        out.append(load)
    return out

def createTwoLoadPartLoadsWithGCC(loadPartsGCC, secondLoadParts):
    out = []
    for loadPartWithGCC in loadPartsGCC:
        for secondLoadPart in secondLoadParts:
            load = createTwoLoadPartLoadWithGCC(loadPartWithGCC, secondLoadPart)
            out.append(load)
    return out

def createTwoLoadPartLoadsWithoutGCC(mixedLoadParts, currentBiasLoadParts):
    out = []
    for mixedLoadPart in mixedLoadParts:
        for currentBiasLoadPart in currentBiasLoadParts:
            load = createTwoLoadPartLoadWithoutGCC(mixedLoadPart, currentBiasLoadPart)
            out.append(load)
    return out


def createSymmetricalLoadFourTransistorMixedLoadParts(pmosLoadPart, nmosLoadPart):
    l = Load(id=1, techtype="p")
    l.ports = [
        "out1",
        "out2",
        # "source_load1",
    ]
    l.add_instance(pmosLoadPart)
    l.add_instance(nmosLoadPart)

    addLoad1WithoutGCCNets(pmosLoadPart)
    addLoad2Nets(nmosLoadPart)

    l = connectInstanceTerminalsOfLoadPart1WithoutGCC(l, pmosLoadPart)
    l = connectInstanceTerminalsOfLoadPart2(l, nmosLoadPart)
    return l



def createSymmetricalLoadsFourTransistorMixedLoadParts(pmosLoadParts,nmosLoadParts ):
    out = []
    for i in range(len(pmosLoadParts)):
        pmosLoadPart = pmosLoadParts[i]
        nmosLoadPart = nmosLoadParts[i]
        symmetricalLoadPart = createSymmetricalLoadFourTransistorMixedLoadParts(pmosLoadPart, nmosLoadPart)
        out.append(symmetricalLoadPart)
    return out

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

    i = 0
    for lp in pmosGCCLoadParts:
        i += 1
        lp.id = i
    
    for lp in nmosSecondLoadParts:
        i += 1
        lp.id = i
    return createTwoLoadPartLoadsWithGCC(pmosGCCLoadParts, nmosSecondLoadParts)

# case 4
def createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos():
    nmosGCCLoadParts = LoadPartManager().createLoadPartsNmosFourTransistorCurrentBiases()
    pmosSecondLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    i = 0
    for lp in nmosGCCLoadParts:
        i += 1
        lp.id = i
    for lp in pmosSecondLoadParts:
        i += 1
        lp.id = i
    return createTwoLoadPartLoadsWithGCC(nmosGCCLoadParts, pmosSecondLoadParts)

# case 5
def createLoadsTwoLoadPartsCascodeGCCMixedPmos():
    pmosGCCLoadParts = LoadPartManager().createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources()
    nmosSecondLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    i = 0
    for lp in pmosGCCLoadParts:
        i += 1
        lp.id = i
    i=20
    for lp in nmosSecondLoadParts:
        i += 1
        lp.id = i

    return createTwoLoadPartLoadsWithGCC(pmosGCCLoadParts, nmosSecondLoadParts)

# case 6
def createLoadsTwoLoadPartsCascodeGCCMixedNmos():
    nmosGCCLoadParts = LoadPartManager().createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources()
    pmosSecondLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    i = 0
    for lp in nmosGCCLoadParts:
        i += 1
        lp.id = i
    i=20
    for lp in pmosSecondLoadParts:
        i += 1
        lp.id = i

    return createTwoLoadPartLoadsWithGCC(nmosGCCLoadParts, pmosSecondLoadParts)

# case 7
def createLoadsTwoLoadPartsMixedCurrentBiasesPmos():
    nmosCurrentBiasLoadParts = LoadPartManager().createLoadPartsNmosCurrentBiases()
    pmosMixedLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    i = 0
    for lp in nmosCurrentBiasLoadParts:
        i += 1
        lp.id = i
    i=20
    for lp in pmosMixedLoadParts:
        i += 1
        lp.id = i


    return createTwoLoadPartLoadsWithoutGCC(pmosMixedLoadParts, nmosCurrentBiasLoadParts)

# case 8
def createLoadsTwoLoadPartsMixedCurrentBiasesNmos():
    pmosCurrentBiasLoadParts = LoadPartManager().createLoadPartsPmosCurrentBiases()
    nmosMixedLoadParts = LoadPartManager().createLoadPartsNmosMixed()

    assignInstanceIds(pmosCurrentBiasLoadParts, start_idx=10)
    assignInstanceIds(nmosMixedLoadParts, start_idx=20)

    return createTwoLoadPartLoadsWithoutGCC(nmosMixedLoadParts, pmosCurrentBiasLoadParts)

# case 9
def createLoadsPmosForFullyDifferentialNonInvertingStage():
    oneLoadPartLoadsCurrentBiasesPmos = createOneLoadPartLoads(LoadPartManager().createLoadPartsPmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesFoldedPmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases(),
                    LoadPartManager().createLoadPartsNmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesCascodeNmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources(),
            LoadPartManager().createLoadPartsPmosCurrentBiases())
    return oneLoadPartLoadsCurrentBiasesPmos + twoLoadPartLoadsOnlyCurrentBiasesFoldedPmosGCC + twoLoadPartLoadsOnlyCurrentBiasesCascodeNmosGCC

# case 10
def createLoadsNmosForFullyDifferentialNonInvertingStage():
    oneLoadPartLoadsCurrentBiasesNmos = createOneLoadPartLoads(LoadPartManager().createLoadPartsNmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesFoldedNmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsNmosFourTransistorCurrentBiases(),
            LoadPartManager().createLoadPartsPmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesCascodePmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources(),
            LoadPartManager().createLoadPartsNmosCurrentBiases())
    return oneLoadPartLoadsCurrentBiasesNmos + twoLoadPartLoadsOnlyCurrentBiasesFoldedNmosGCC + twoLoadPartLoadsOnlyCurrentBiasesCascodePmosGCC

# case 11
def createLoadsForComplementaryNonInvertingStage():
    pmosLoadParts = LoadPartManager().createLoadPartsPmosFourTransistorMixed()
    nmosLoadParts = LoadPartManager().createLoadPartsNmosFourTransistorMixed()
    loads = createSymmetricalLoadsFourTransistorMixedLoadParts(pmosLoadParts, nmosLoadParts)

    twoLoadPartLoadsMixedFoldedPmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases(),
    LoadPartManager().createLoadPartsNmosMixed())
    twoLoadPartLoadsMixedFoldedNmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsNmosFourTransistorCurrentBiases(),
    LoadPartManager().createLoadPartsPmosMixed())

    # TODO: filter out loads that have more than/less than 8 components
    return loads + twoLoadPartLoadsMixedFoldedPmosGCC + twoLoadPartLoadsMixedFoldedNmosGCC

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
if __name__ == "__main__":
    for idx1, method in enumerate(methods):
        print(f"Method {idx1}: {method.__name__}, len = {len(method())}")
        for idx2, load in enumerate(method()):
            # print(load)
            if load == None:
                continue
            save_graphviz_figure(
                load,
                GALLERY_DOT_DIR / f"l_{idx1}_{idx2}.dot",
            )
            convert_dot_to_png(
                GALLERY_DOT_DIR / f"l_{idx1}_{idx2}.dot",
                GALLERY_IMAGE_DIR / f"l_{idx1}_{idx2}.png",
            )
