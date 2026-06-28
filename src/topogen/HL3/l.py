from itertools import chain
from pathlib import Path
from typing import Callable, Iterator

from topogen.common.circuit import *
from topogen.HL2.vb import *
from topogen.HL3.lp import *

# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "l" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "l" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

def connectInstanceTerminalsOfLoadPart1WithoutGCC(load: Load, loadPart: LoadPart):
    """Wire a non-GCC :class:`~topogen.HL3.lp.LoadPart` (acting as "load 1")
    into a :class:`Load`'s ``OUT1``/``OUT2``/``SOURCELOAD1`` plus whichever
    inner/cascode ports :func:`addLoad1WithoutGCCNets` added, based on
    *loadPart*'s branch types and ``component_count``.
    """
    # Connect the loadPart instances to the load terminals
    # Assuming loadPart has two instances representing two transistor stacks

    # fmt: off
    connect((load, Load.OUT1), (loadPart, LoadPart.OUT1))
    connect((load, Load.OUT2), (loadPart, LoadPart.OUT2))
    connect((load, Load.SOURCELOAD1), (loadPart, LoadPart.SOURCE))

    if loadPart.ts1.instances[0].name.startswith("vb") and loadPart.ts2.instances[
        0
    ].name.startswith("vb"):
        if loadPart.component_count > 2:
            connect((load, Load.OUTOUTPUT1LOAD1), (loadPart, LoadPart.OUTOUTPUT1))
            connect((load, Load.OUTOUTPUT2LOAD1), (loadPart, LoadPart.OUTOUTPUT2))
            connect((load, Load.OUTSOURCE1LOAD1), (loadPart, LoadPart.OUTSOURCE1))
            connect((load, Load.OUTSOURCE2LOAD1), (loadPart, LoadPart.OUTSOURCE2))
    else:
        if loadPart.component_count == 2:
            connect((load, Load.INNERLOAD1), (loadPart, LoadPart.INNER))

        if loadPart.component_count > 2:
            connect((load, Load.INNERSOURCELOAD1), (loadPart, LoadPart.INNERSOURCE))

            if len(loadPart.ts1.instances) == 1 and loadPart.ts1.instances[
                0
            ].name.startswith("dt"):
                connect((load, Load.INNEROUTPUTLOAD1), (loadPart, LoadPart.INNEROUTPUT))


        if loadPart.component_count > 3:
            connect((load, Load.INNEROUTPUTLOAD1), (loadPart, LoadPart.INNEROUTPUT))
    if loadPart.component_count > 2:
        connect((load, Load.INNERTRANSISTORSTACK2LOAD1), (loadPart, LoadPart.INNERTRANSISTORSTACK2))
    if loadPart.component_count > 3:
        connect((load, Load.INNERTRANSISTORSTACK1LOAD1), (loadPart, LoadPart.INNERTRANSISTORSTACK1))

    return load

def addLoad1WithoutGCCNets(loadPart: LoadPart):
    """Return the extra port list a non-GCC "load 1" :class:`~topogen.HL3.lp.LoadPart`
    needs on the enclosing :class:`Load`, based on its branch types and
    ``component_count`` (mirrors the cases handled by
    :func:`connectInstanceTerminalsOfLoadPart1WithoutGCC`)."""
    # num_reviews: 1

    new_ports = [ Load.SOURCELOAD1]
    if loadPart.instances[0].instances[0].name.startswith("vb") and loadPart.instances[1].instances[0].name.startswith("vb"):
        if loadPart.component_count > 2:
            new_ports += [
                          Load.OUTOUTPUT1LOAD1,
                          Load.OUTOUTPUT2LOAD1,
                          Load.OUTSOURCE1LOAD1,
                          Load.OUTSOURCE2LOAD1,
            ]
    else:
        if loadPart.component_count ==2:
            new_ports += [Load.INNERLOAD1]
        
        if loadPart.component_count > 2:
            new_ports += [Load.INNERSOURCELOAD1]

            if loadPart.ts1.instances[0].component_count ==  1 and loadPart.ts1.instances[0].name.startswith("dt"):
                new_ports += [Load.INNEROUTPUTLOAD1]
        
        if loadPart.component_count > 3:
            new_ports += [Load.INNEROUTPUTLOAD1]

    if loadPart.component_count > 2:
        new_ports += [Load.INNERTRANSISTORSTACK2LOAD1]
    if loadPart.component_count > 3:
        new_ports += [Load.INNERTRANSISTORSTACK1LOAD1]
    return new_ports

def createOneLoadPartLoad(loadPart):
    """Wrap a single :class:`~topogen.HL3.lp.LoadPart` ("load 1" only, no
    second branch and no GCC) in a :class:`Load`."""
    l = Load(id=1, techtype="p")
    l.ports = [
        Load.OUT1,
        Load.OUT2,
        Load.SOURCELOAD1
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
    """Return the extra port list a "load 2" :class:`~topogen.HL3.lp.LoadPart`
    needs on the enclosing :class:`Load`, based on its ``component_count``
    (mirrors the cases handled by :func:`connectInstanceTerminalsOfLoadPart2`)."""
    new_ports = []
    new_ports += [Load.SOURCELOAD2]

    # if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) == 2:
    if loadPart2.component_count == 2:
        new_ports += [Load.INNERLOAD2]
    # if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) > 2:
    if loadPart2.component_count > 2:
        new_ports += [Load.INNERSOURCELOAD2, Load.INNERTRANSISTORSTACK2LOAD2]

        if loadPart2.ts1.instances[0].component_count == 1 and loadPart2.ts1.instances[
            0
        ].name.startswith("dt"):
            new_ports += [Load.INNEROUTPUTLOAD2]
        
    # if len(loadPart2.ts1.instances[0].instances) + len(loadPart2.ts2.instances[0].instances) > 3:
    if loadPart2.component_count > 3:
        new_ports += [Load.INNEROUTPUTLOAD2, Load.INNERSOURCELOAD2, Load.INNERTRANSISTORSTACK1LOAD2]
    return new_ports

def connectInstanceTerminalsOfLoadPart2(load: Load, loadPart2: LoadPart):
    """Wire a :class:`~topogen.HL3.lp.LoadPart` (acting as "load 2") into a
    :class:`Load`'s ``OUT1``/``OUT2``/``SOURCELOAD2`` plus whichever
    inner/cascode ports :func:`addLoad2Nets` added."""
    connect((load, Load.OUT1), (loadPart2, LoadPart.OUT1))
    connect((load, Load.OUT2), (loadPart2, LoadPart.OUT2))
    connect((load, Load.SOURCELOAD2), (loadPart2, LoadPart.SOURCE))


    if loadPart2.component_count == 2:
        connect((load, Load.INNERLOAD2), (loadPart2, LoadPart.INNER))
    if loadPart2.component_count > 2:
        connect((load, Load.INNERSOURCELOAD2), (loadPart2, LoadPart.INNERSOURCE))
        connect((load, Load.INNERTRANSISTORSTACK2LOAD2), (loadPart2, LoadPart.INNERTRANSISTORSTACK2))

        if loadPart2.ts1.instances[0].component_count == 1 and loadPart2.ts1.instances[
            0
        ].name.startswith("dt"):
            connect((load, Load.INNEROUTPUTLOAD2), (loadPart2, LoadPart.INNEROUTPUT))
    
    if loadPart2.component_count > 3:
        connect((load, Load.INNEROUTPUTLOAD2), (loadPart2, LoadPart.INNEROUTPUT))
        connect((load, Load.INNERTRANSISTORSTACK1LOAD2), (loadPart2, LoadPart.INNERTRANSISTORSTACK1))

    return load
def createTwoLoadPartLoadWithGCC(loadPartWithGCC, secondLoadPart):
    """Combine a GCC (gain/cross-coupled) "load 1" :class:`~topogen.HL3.lp.LoadPart`
    with a plain "load 2" branch into a two-branch :class:`Load`."""
    l = Load(id=1, techtype="p")
    l.ports = [
        Load.OUT1,
        Load.OUT2
    ]
    l.add_instance(loadPartWithGCC)
    l.add_instance(secondLoadPart)


    # fmt: off
    def addLoad1WithGCCNets(loadPart1: LoadPart):
        """Return the extra port list a GCC "load 1" needs, based on ``component_count``."""
        new_ports = []
        new_ports += [Load.SOURCEGCC1, Load.SOURCEGCC2, Load.INNERGCC]
        if loadPart1.component_count > 2:
            new_ports += [Load.SOURCELOAD1, Load.INNERBIASGCC]
        return new_ports


    
    def connectInstanceTerminalsOfLoadPart1WithGCC(load: Load, loadPartWithGCC: LoadPart):
        """Wire the GCC "load 1" branch into *load*'s GCC-specific ports
        (``SOURCEGCC{1,2}``/``INNERGCC``, plus ``SOURCELOAD1``/``INNERBIASGCC``
        when the branch has more than 2 components)."""
        connect((load, Load.OUT1), (loadPartWithGCC, LoadPart.OUT1))
        connect((load, Load.OUT2), (loadPartWithGCC, LoadPart.OUT2))

        if loadPartWithGCC.component_count == 2:
            connect((load, Load.SOURCEGCC1), (loadPartWithGCC, LoadPart.SOURCE1))
            connect((load, Load.SOURCEGCC2), (loadPartWithGCC, LoadPart.SOURCE2))
            connect((load, Load.INNERGCC), (loadPartWithGCC, LoadPart.INNER))


        else:
            connect((load, Load.SOURCEGCC1), (loadPartWithGCC, LoadPart.INNERTRANSISTORSTACK1))
            connect((load, Load.SOURCEGCC2), (loadPartWithGCC, LoadPart.INNERTRANSISTORSTACK2))
            connect((load, Load.INNERGCC), (loadPartWithGCC, LoadPart.INNEROUTPUT))
            connect((load, Load.SOURCELOAD1), (loadPartWithGCC, LoadPart.SOURCE))
            connect((load, Load.INNERBIASGCC), (loadPartWithGCC, LoadPart.INNERSOURCE))

        return load



    l.ports += addLoad1WithGCCNets(loadPartWithGCC)
    l.ports += addLoad2Nets(secondLoadPart)

    l = connectInstanceTerminalsOfLoadPart1WithGCC(l, loadPartWithGCC)
    l = connectInstanceTerminalsOfLoadPart2(l, secondLoadPart)
    return l

def createTwoLoadPartLoadWithoutGCC(mixedLoadPart, currentBiasLoadPart):
    """Combine a non-GCC "load 1" :class:`~topogen.HL3.lp.LoadPart` (typically
    mixed voltage+current bias) with a "load 2" current-bias branch into a
    two-branch :class:`Load`."""
    l = Load(id=1, techtype="p")
    l.ports = [
        Load.OUT1,
        Load.OUT2
    ]
    l.add_instance(mixedLoadPart)
    l.add_instance(currentBiasLoadPart)


    # fmt: off
    def addLoad1WithoutGCCNets(loadPart1: LoadPart):
        """Return the extra port list this non-GCC "load 1" branch needs,
        based on its branch types and ``component_count`` (local variant of
        the module-level :func:`addLoad1WithoutGCCNets`, used here because the
        branch nesting is one level deeper: ``loadPart1.ts1.instances[0].instances[0]``)."""
        new_ports = []
        new_ports += [Load.SOURCELOAD1]
        if loadPart1.ts1.instances[0].name.startswith("vb") and loadPart1.ts2.instances[0].name.startswith("vb"):
            if loadPart1.component_count > 2:
                new_ports += [
                              Load.OUTOUTPUT1LOAD1,
                              Load.OUTOUTPUT2LOAD1,
                              Load.OUTSOURCE1LOAD1,
                              Load.OUTSOURCE2LOAD1,
                              ]
        else:
            if loadPart1.component_count ==2 :
                new_ports += [Load.INNERLOAD1]
            
            if loadPart1.component_count > 2:
                new_ports += [Load.INNERSOURCELOAD1]

                if loadPart1.ts1.instances[0].component_count ==  1 and loadPart1.ts1.instances[0].instances[0].name.startswith("dt"):
                    new_ports += [Load.INNEROUTPUTLOAD1]
            
            if loadPart1.component_count > 3:
                new_ports += [Load.INNEROUTPUTLOAD1]
        
        if loadPart1.component_count > 2:
            new_ports += [Load.INNERTRANSISTORSTACK2LOAD1]
        
        if loadPart1.component_count > 3:
            new_ports += [Load.INNERTRANSISTORSTACK1LOAD1]
        return new_ports


    
    def connectInstanceTerminalsOfLoadPart1WithoutGCC(load: Load, loadPart1: LoadPart):
        """Wire this non-GCC "load 1" branch into *load* (local variant of the
        module-level :func:`connectInstanceTerminalsOfLoadPart1WithoutGCC`)."""
        connect((load, Load.OUT1), (loadPart1, LoadPart.OUT1))
        connect((load, Load.OUT2), (loadPart1, LoadPart.OUT2))
        connect((load, Load.SOURCELOAD1), (loadPart1,  LoadPart.SOURCE))

        if loadPart1.ts1.instances[0].name.startswith("vb") and loadPart1.ts2.instances[0].name.startswith("vb"):
            if loadPart1.component_count > 2:
                connect((load, Load.OUTOUTPUT1LOAD1), (loadPart1, LoadPart.OUTOUTPUT1))
                connect((load, Load.OUTOUTPUT2LOAD1), (loadPart1, LoadPart.OUTOUTPUT2))
                connect((load, Load.OUTSOURCE1LOAD1), (loadPart1, LoadPart.OUTSOURCE1))
                connect((load, Load.OUTSOURCE2LOAD1), (loadPart1, LoadPart.OUTSOURCE2))

        else:
            if loadPart1.component_count ==2:
                connect((load, Load.INNERLOAD1), (loadPart1, LoadPart.INNER))
            
            if loadPart1.component_count >2:
                connect((load, Load.INNERSOURCELOAD1), (loadPart1,  LoadPart.INNERSOURCE))

                if loadPart1.ts1.instances[0].component_count == 1 and loadPart1.ts1.instances[
                    0
                ].name.startswith("dt"):
                    connect((load, Load.INNEROUTPUTLOAD1), (loadPart1, LoadPart.INNEROUTPUT))
            
            if loadPart1.component_count > 3:
                connect((load, Load.INNEROUTPUTLOAD1), (loadPart1,  LoadPart.INNEROUTPUT))
        
        if loadPart1.component_count > 2:
            connect((load, Load.INNERTRANSISTORSTACK2LOAD1), (loadPart1, LoadPart.INNERTRANSISTORSTACK2))
        if loadPart1.component_count > 3:
            connect((load, Load.INNERTRANSISTORSTACK1LOAD1), (loadPart1,  LoadPart.INNERTRANSISTORSTACK1))

        return load


    l.ports += addLoad1WithoutGCCNets(mixedLoadPart)
    l.ports += addLoad2Nets(currentBiasLoadPart)

    l = connectInstanceTerminalsOfLoadPart1WithoutGCC(l, mixedLoadPart)
    l = connectInstanceTerminalsOfLoadPart2(l, currentBiasLoadPart)
    return l


def createOneLoadPartLoads(loadParts) -> Iterator[Circuit]:
    """Wrap each load part in *loadParts* as a single-branch :class:`Load`."""
    for loadPart in loadParts:
        yield createOneLoadPartLoad(loadPart)

def createTwoLoadPartLoadsWithGCC(loadPartsGCC, secondLoadParts)-> Iterator[Circuit]:
    """Yield one GCC :class:`Load` per (GCC load part, second load part) pair
    across the full cross-product of the two input lists."""
    for loadPartWithGCC in loadPartsGCC:
        for secondLoadPart in secondLoadParts:
            yield createTwoLoadPartLoadWithGCC(loadPartWithGCC, secondLoadPart)

def createTwoLoadPartLoadsWithoutGCC(mixedLoadParts, currentBiasLoadParts)-> Iterator[Circuit]:
    """Yield one non-GCC two-branch :class:`Load` per (mixed load part,
    current-bias load part) pair across the full cross-product of the two
    input lists."""
    for mixedLoadPart in mixedLoadParts:
        for currentBiasLoadPart in currentBiasLoadParts:
            yield createTwoLoadPartLoadWithoutGCC(mixedLoadPart, currentBiasLoadPart)


def createSymmetricalLoadFourTransistorMixedLoadParts(pmosLoadPart, nmosLoadPart):
    """Combine a PMOS and an NMOS four-transistor mixed load part into one
    symmetrical two-branch :class:`Load`."""
    l = Load(id=1, techtype="p")
    l.ports = [
        Load.OUT1,
        Load.OUT2,
    ]
    l.add_instance(pmosLoadPart)
    l.add_instance(nmosLoadPart)

    l.ports += addLoad1WithoutGCCNets(pmosLoadPart)
    l.ports += addLoad2Nets(nmosLoadPart)

    l = connectInstanceTerminalsOfLoadPart1WithoutGCC(l, pmosLoadPart)
    l = connectInstanceTerminalsOfLoadPart2(l, nmosLoadPart)
    return l



def createSymmetricalLoadsFourTransistorMixedLoadParts(pmosLoadParts,nmosLoadParts ) -> Iterator[Circuit]:
    """Yield one symmetrical :class:`Load` per index-aligned (PMOS, NMOS)
    four-transistor mixed load part pair (zipped by position, not cross-product)."""
    for i in range(len(pmosLoadParts)):
        pmosLoadPart = pmosLoadParts[i]
        nmosLoadPart = nmosLoadParts[i]
        yield createSymmetricalLoadFourTransistorMixedLoadParts(pmosLoadPart, nmosLoadPart)

# case 1
def createSimpleMixedLoadPmos()->list[Circuit]:
    """Case 1: single-branch PMOS loads built from mixed voltage+current-bias load parts."""
    pmosLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    return createOneLoadPartLoads(pmosLoadParts)


# case 2
def createSimpleMixedLoadNmos():
    """Case 2: single-branch NMOS loads built from mixed voltage+current-bias load parts."""
    nmosLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    return createOneLoadPartLoads(nmosLoadParts)


# case 3
def createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos():
    """Case 3: two-branch loads pairing a folded-GCC PMOS four-transistor
    current-bias load part with an NMOS mixed load part."""
    pmosGCCLoadParts = (LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases())
    nmosSecondLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    return createTwoLoadPartLoadsWithGCC(pmosGCCLoadParts, nmosSecondLoadParts)

# case 4
def createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos():
    """Case 4: NMOS/PMOS mirror of :func:`createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos`."""
    nmosGCCLoadParts = LoadPartManager().createLoadPartsNmosFourTransistorCurrentBiases()
    pmosSecondLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    return createTwoLoadPartLoadsWithGCC(nmosGCCLoadParts, pmosSecondLoadParts)

# case 5
def createLoadsTwoLoadPartsCascodeGCCMixedPmos():
    """Case 5: two-branch loads pairing a cascode-GCC PMOS current-bias load
    part (independent sources) with an NMOS mixed load part."""
    pmosGCCLoadParts = LoadPartManager().createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources()
    nmosSecondLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    return createTwoLoadPartLoadsWithGCC(pmosGCCLoadParts, nmosSecondLoadParts)

# case 6
def createLoadsTwoLoadPartsCascodeGCCMixedNmos():
    """Case 6: NMOS/PMOS mirror of :func:`createLoadsTwoLoadPartsCascodeGCCMixedPmos`."""
    nmosGCCLoadParts = LoadPartManager().createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources()
    pmosSecondLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    return createTwoLoadPartLoadsWithGCC(nmosGCCLoadParts, pmosSecondLoadParts)

# case 7
def createLoadsTwoLoadPartsMixedCurrentBiasesPmos():
    """Case 7: two-branch, non-GCC loads pairing a PMOS mixed load part with
    an NMOS current-bias load part."""
    nmosCurrentBiasLoadParts = LoadPartManager().createLoadPartsNmosCurrentBiases()
    pmosMixedLoadParts = LoadPartManager().createLoadPartsPmosMixed()
    return createTwoLoadPartLoadsWithoutGCC(pmosMixedLoadParts, nmosCurrentBiasLoadParts)

# case 8
def createLoadsTwoLoadPartsMixedCurrentBiasesNmos():
    """Case 8: NMOS/PMOS mirror of :func:`createLoadsTwoLoadPartsMixedCurrentBiasesPmos`."""
    pmosCurrentBiasLoadParts = LoadPartManager().createLoadPartsPmosCurrentBiases()
    nmosMixedLoadParts = LoadPartManager().createLoadPartsNmosMixed()
    return createTwoLoadPartLoadsWithoutGCC(nmosMixedLoadParts, pmosCurrentBiasLoadParts)

# case 9
def createLoadsPmosForFullyDifferentialNonInvertingStage():
    """Case 9: every PMOS load suitable for a fully-differential non-inverting
    stage — single-branch current-bias loads, folded-GCC, and cascode-GCC variants, chained."""
    oneLoadPartLoadsCurrentBiasesPmos = createOneLoadPartLoads(LoadPartManager().createLoadPartsPmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesFoldedPmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsPmosFourTransistorCurrentBiases(),
                    LoadPartManager().createLoadPartsNmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesCascodeNmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources(),
            LoadPartManager().createLoadPartsPmosCurrentBiases())
    return chain(oneLoadPartLoadsCurrentBiasesPmos, twoLoadPartLoadsOnlyCurrentBiasesFoldedPmosGCC, twoLoadPartLoadsOnlyCurrentBiasesCascodeNmosGCC)

# case 10
def createLoadsNmosForFullyDifferentialNonInvertingStage():
    """Case 10: NMOS/PMOS mirror of :func:`createLoadsPmosForFullyDifferentialNonInvertingStage`."""
    oneLoadPartLoadsCurrentBiasesNmos = createOneLoadPartLoads(LoadPartManager().createLoadPartsNmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesFoldedNmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsNmosFourTransistorCurrentBiases(),
            LoadPartManager().createLoadPartsPmosCurrentBiases())
    twoLoadPartLoadsOnlyCurrentBiasesCascodePmosGCC = createTwoLoadPartLoadsWithGCC(LoadPartManager().createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources(),
            LoadPartManager().createLoadPartsNmosCurrentBiases())
    return chain(oneLoadPartLoadsCurrentBiasesNmos , twoLoadPartLoadsOnlyCurrentBiasesFoldedNmosGCC , twoLoadPartLoadsOnlyCurrentBiasesCascodePmosGCC)

# case 11
def createLoadsForComplementaryNonInvertingStage():
    """Case 11: every load suitable for a complementary non-inverting stage —
    symmetrical PMOS/NMOS four-transistor mixed loads, plus folded-GCC
    variants filtered to exactly 8 components."""
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
    """Case 12: single-branch PMOS loads built from two-transistor voltage-bias load parts."""
    pmosLoadParts = LoadPartManager().createTwoTransistorsLoadPartsLoadPartsPmosVoltageBiases()
    return createOneLoadPartLoads(pmosLoadParts)

# case 13
def createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage():
    """Case 13: single-branch PMOS loads built from four-transistor voltage-bias load parts."""
    pmosLoadParts = LoadPartManager().createFourTransistorsLoadPartsLoadPartsPmosVoltageBiases()
    return createOneLoadPartLoads(pmosLoadParts)


# case 14
def createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage():
    """Case 14: NMOS/PMOS mirror of :func:`createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage`."""
    nmosLoadParts = LoadPartManager().createTwoTransistorsLoadPartsLoadPartsNmosVoltageBiases()
    return createOneLoadPartLoads(nmosLoadParts)

# case 15
def createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage():
    """Case 15: NMOS/PMOS mirror of :func:`createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage`."""
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
    """Object-oriented facade over the module-level ``create*`` / ``case N``
    functions in this file — each method is a thin static forwarder to its
    same-named module-level function, except :meth:`getLoadsPmosForFeedbackNonInvertingStage`
    / :meth:`getLoadsNmosForFeedbackNonInvertingStage`, which read from the
    voltage-bias load parts cached by :meth:`initializeLoadsVoltageBiasesLoadPart`.
    """

    def __init__(self):
        """Build and cache the voltage-bias single-branch loads (see :meth:`initializeLoadsVoltageBiasesLoadPart`)."""
        self.initializeLoadsVoltageBiasesLoadPart()

    @staticmethod
    def createSimpleMixedLoadPmos():
        """Forwards to module-level :func:`createSimpleMixedLoadPmos` (case 1)."""
        return createSimpleMixedLoadPmos()

    @staticmethod
    def createSimpleMixedLoadNmos():
        """Forwards to module-level :func:`createSimpleMixedLoadNmos` (case 2)."""
        return createSimpleMixedLoadNmos()

    @staticmethod
    def createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos():
        """Forwards to module-level :func:`createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos` (case 3)."""
        return createSimpleTwoLoadPartsFoldedGCCMixedLoadPmos()

    @staticmethod
    def createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos():
        """Forwards to module-level :func:`createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos` (case 4)."""
        return createSimpleTwoLoadPartsFoldedGCCMixedLoadNmos()

    @staticmethod
    def createLoadsTwoLoadPartsCascodeGCCMixedPmos():
        """Forwards to module-level :func:`createLoadsTwoLoadPartsCascodeGCCMixedPmos` (case 5)."""
        return createLoadsTwoLoadPartsCascodeGCCMixedPmos()

    @staticmethod
    def createLoadsTwoLoadPartsCascodeGCCMixedNmos():
        """Forwards to module-level :func:`createLoadsTwoLoadPartsCascodeGCCMixedNmos` (case 6)."""
        return createLoadsTwoLoadPartsCascodeGCCMixedNmos()

    @staticmethod
    def createLoadsTwoLoadPartsMixedCurrentBiasesPmos():
        """Forwards to module-level :func:`createLoadsTwoLoadPartsMixedCurrentBiasesPmos` (case 7)."""
        return createLoadsTwoLoadPartsMixedCurrentBiasesPmos()

    @staticmethod
    def createLoadsTwoLoadPartsMixedCurrentBiasesNmos():
        """Forwards to module-level :func:`createLoadsTwoLoadPartsMixedCurrentBiasesNmos` (case 8)."""
        return createLoadsTwoLoadPartsMixedCurrentBiasesNmos()

    @staticmethod
    def createLoadsPmosForFullyDifferentialNonInvertingStage():
        """Forwards to module-level :func:`createLoadsPmosForFullyDifferentialNonInvertingStage` (case 9)."""
        return createLoadsPmosForFullyDifferentialNonInvertingStage()

    @staticmethod
    def createLoadsNmosForFullyDifferentialNonInvertingStage():
        """Forwards to module-level :func:`createLoadsNmosForFullyDifferentialNonInvertingStage` (case 10)."""
        return createLoadsNmosForFullyDifferentialNonInvertingStage()

    @staticmethod
    def createLoadsForComplementaryNonInvertingStage():
        """Forwards to module-level :func:`createLoadsForComplementaryNonInvertingStage` (case 11)."""
        return createLoadsForComplementaryNonInvertingStage()

    @staticmethod
    def createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage():
        """Forwards to module-level :func:`createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage` (case 14)."""
        return createLoadsNmosTwoForSymmetricalOpAmpNonInvertingStage()

    @staticmethod
    def createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage():
        """Forwards to module-level :func:`createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage` (case 15)."""
        return createLoadsNmosFourForSymmetricalOpAmpNonInvertingStage()

    @staticmethod
    def createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage():
        """Forwards to module-level :func:`createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage` (case 12)."""
        return createLoadsPmosTwoForSymmetricalOpAmpNonInvertingStage()

    @staticmethod
    def createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage():
        """Forwards to module-level :func:`createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage` (case 13)."""
        return createLoadsPmosFourForSymmetricalOpAmpNonInvertingStage()

    def initializeLoadsVoltageBiasesLoadPart(self):
        """Build the single-branch PMOS/NMOS voltage-bias loads and cache them on ``self``."""
        pmosLoadParts = LoadPartManager().getLoadPartsPmosVoltageBiases()
        nmosLoadParts = LoadPartManager().getLoadPartsNmosVoltageBiases()

        self.oneLoadPartLoadsVoltageBiasesNmos_ = createOneLoadPartLoads(nmosLoadParts)
        self.oneLoadPartLoadsVoltageBiasesPmos_ = createOneLoadPartLoads(pmosLoadParts)

    # @staticmethod
    def getLoadsPmosForFeedbackNonInvertingStage(self) -> Iterator[NonInvertingStage]:
        """Yield the cached PMOS voltage-bias loads with exactly 2 components
        (the variant suitable for a feedback non-inverting stage)."""
        out = []
        for voltageBiasLoad in self.oneLoadPartLoadsVoltageBiasesPmos_:
            if voltageBiasLoad.component_count == 2:
                out.append(voltageBiasLoad)
                yield voltageBiasLoad

        # TODO: uncomment the following line
        # assert len(out) == 1
        # yield out[

    def getLoadsNmosForFeedbackNonInvertingStage(self) -> Iterator[NonInvertingStage]:
        """Yield the cached NMOS voltage-bias loads with exactly 2 components
        (the variant suitable for a feedback non-inverting stage)."""
        out = []
        for voltageBiasLoad in self.oneLoadPartLoadsVoltageBiasesNmos_:
            if voltageBiasLoad.component_count == 2:
                out.append(voltageBiasLoad)
                yield voltageBiasLoad

        # TODO: uncomment the following lines
        # print(f"total out: ", len(out))
        # assert len(out) == 1, print(len(out))
        # yield out[1]


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
