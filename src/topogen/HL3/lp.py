import json
from pathlib import Path

from topogen.common.circuit import *
from topogen.common.circuit import (
    Circuit,
    LoadPart,
    TransistorStack,
    connect,
    convert_dot_to_png,
    createTransistorStack,
    save_graphviz_figure,
)
from topogen.HL2.cb import CurrentBiasManager
from topogen.HL2.vb import VoltageBiasManager
from utils.loguru_loader import setup_logger

# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "lp" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "lp" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

logger = setup_logger(log_level="DEBUG", log_file=None)


def connectInstanceTerminalsOfTwoTransistorLoadPart(out: LoadPart, ts1, ts2):
    """Wire two single-stack :class:`~topogen.common.circuit.TransistorStack`
    instances into a two-branch :class:`LoadPart` (``OUT1``/``OUT2``).

    Branches built from a current bias (``"cb"``-prefixed instance) connect
    their ``OUT``/``IN``/``SOURCE`` to ``OUT{1,2}``/``INNER``/``SOURCE``;
    branches built from anything else (voltage bias) connect their ``IN`` to
    ``OUT{1,2}``, with the ``OUT`` pin landing on ``OUT{1,2}`` too when *both*
    branches are voltage biases, or on the shared ``INNER`` node otherwise.
    """
    num = 1
    # fmt: off
    for transistorStack in [ts1, ts2]:
        if transistorStack.instances[0].name.startswith("cb"):
            if num == 1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))

            connect((out, LoadPart.INNER), (transistorStack, TransistorStack.IN))
            connect((out, LoadPart.SOURCE), (transistorStack, TransistorStack.SOURCE))

        else:
            if num == 1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.IN))
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.IN))

            if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith("vb"):
                if num == 1:
                    connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
                else:
                    connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))
            else:
                # Current-mirror load: the voltage-bias branch is the mirror
                # *reference* and must be diode-connected (gate = its own drain),
                # so the shared INNER mirror-gate node lands on the reference
                # drain (matching acst, where Load_1 is a diode transistor). The
                # extra OUT{1,2} connection ties this branch's gate to its drain;
                # without it the reference gate floats (issue #3, Fix 2a).
                connect((out, LoadPart.INNER), (transistorStack, TransistorStack.OUT))
                if num == 1:
                    connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
                else:
                    connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))

            connect((out, LoadPart.SOURCE), (transistorStack, TransistorStack.SOURCE))
        num += 1
    # fmt: on
    return out


def connectInstanceTerminalsOfFourTransistorLoadPart(out: LoadPart, ts1, ts2):
    """Wire two two-transistor :class:`~topogen.common.circuit.TransistorStack`
    instances into a four-transistor :class:`LoadPart`.

    Same branch-type split as :func:`connectInstanceTerminalsOfTwoTransistorLoadPart`,
    extended with each stack's inner cascode node
    (``INNERTRANSISTORSTACK{1,2}``) and, for the mixed/cb-mismatched case, the
    secondary inner port pair (``INNEROUTPUT``/``INNERSOURCE`` or, when both
    stacks are voltage biases, ``OUTOUTPUT{1,2}``/``OUTSOURCE{1,2}``).
    """
    num = 1
    # fmt: off
    for transistorStack in [ts1, ts2]:
        if transistorStack.instances[0].name.startswith("cb"):
            if num==1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
                connect((out, LoadPart.INNERTRANSISTORSTACK1), (transistorStack, TransistorStack.INNER))

            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))
                connect((out, LoadPart.INNERTRANSISTORSTACK2), (transistorStack, TransistorStack.INNER))

            connect((out, LoadPart.INNEROUTPUT), (transistorStack, TransistorStack.INOUTPUT))
            connect((out, LoadPart.INNERSOURCE), (transistorStack, TransistorStack.INSOURCE))
            connect((out, LoadPart.SOURCE), (transistorStack, TransistorStack.SOURCE))
        else:
            if num==1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.IN))
                connect((out, LoadPart.INNERTRANSISTORSTACK1), (transistorStack, TransistorStack.INNER))
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.IN))
                connect((out, LoadPart.INNERTRANSISTORSTACK2), (transistorStack, TransistorStack.INNER))

            if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith("vb"):
                if num==1:
                    connect((out, LoadPart.OUTOUTPUT1), (transistorStack, TransistorStack.OUTINPUT))
                    connect((out, LoadPart.OUTSOURCE1), (transistorStack, TransistorStack.OUTSOURCE))
                else:
                    connect((out, LoadPart.OUTOUTPUT2), (transistorStack, TransistorStack.OUTINPUT))
                    connect((out, LoadPart.OUTSOURCE2), (transistorStack, TransistorStack.OUTSOURCE))
            else:
                connect((out, LoadPart.INNEROUTPUT), (transistorStack, TransistorStack.OUTINPUT))
                connect((out, LoadPart.INNERSOURCE), (transistorStack, TransistorStack.OUTSOURCE))

            connect((out, LoadPart.SOURCE), (transistorStack, TransistorStack.SOURCE))
        
        num+=1
    return out
    # fmt: on


def connectInstanceTerminalsOfTwoTransistorLoadPartDifferentSources(
    out, ts1: TransistorStack, ts2: TransistorStack
):
    """Like :func:`connectInstanceTerminalsOfTwoTransistorLoadPart`, but each
    branch keeps its own independent source (``SOURCE1``/``SOURCE2``) instead
    of sharing one ``SOURCE`` node."""
    num = 1
    # fmt: off
    for transistorStack in [ts1, ts2]:
        if transistorStack.instances[0].name.startswith("cb"):
            if num == 1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
                connect((out, LoadPart.SOURCE1), (transistorStack, TransistorStack.SOURCE))
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))
                connect((out, LoadPart.SOURCE2), (transistorStack, TransistorStack.SOURCE))

            connect((out, LoadPart.INNER), (transistorStack, TransistorStack.IN))
        else:
            if num == 1:
                connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.IN))
                connect((out, LoadPart.SOURCE1), (transistorStack, TransistorStack.SOURCE))
            else:
                connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.IN))
                connect((out, LoadPart.SOURCE2), (transistorStack, TransistorStack.SOURCE))

            if ts1.instances[0].name == "vb" and ts2.instances[0].name == "vb":
                if num == 1:
                    connect((out, LoadPart.OUT1), (transistorStack, TransistorStack.OUT))
                else:
                    connect((out, LoadPart.OUT2), (transistorStack, TransistorStack.OUT))
            else:
                connect((out, LoadPart.INNER), (transistorStack, TransistorStack.OUT))
        num += 1
    return out
    # fmt: on


def createTwoTransistorLoadPart(ts1: TransistorStack, ts2: TransistorStack):
    """Build a two-branch :class:`LoadPart` (shared source) from two
    single-stack branches; see :func:`connectInstanceTerminalsOfTwoTransistorLoadPart`."""
    # if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith(
    #     "vb"
    # ):
    #     lp = LoadPart(id=1, techtype="p")
    # else:
    lp = LoadPart(id=1, techtype="p")
    lp.ports = [LoadPart.OUT1, LoadPart.OUT2, LoadPart.SOURCE]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") or ts2.instances[0].name.startswith("vb"):
        pass

    lp = connectInstanceTerminalsOfTwoTransistorLoadPart(lp, ts1, ts2)
    return lp


def createTwoTransistorLoadPartDifferentSources(
    ts1: TransistorStack, ts2: TransistorStack
):
    """Build a two-branch :class:`LoadPart` with independent sources
    (``SOURCE1``/``SOURCE2``) from two single-stack branches."""
    lp = LoadPart(id=1, techtype="p")
    lp.ports = [LoadPart.OUT1, LoadPart.OUT2, LoadPart.SOURCE1, LoadPart.SOURCE2]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") or ts2.instances[0].name.startswith("vb"):
        pass

    lp = connectInstanceTerminalsOfTwoTransistorLoadPartDifferentSources(lp, ts1, ts2)
    return lp


def connectInstanceTerminalsOfThreeTransistorLoadPart(
    out, ts1: TransistorStack, ts2: TransistorStack
):
    """Wire a one-transistor stack (*ts1*) and a two-transistor stack (*ts2*)
    into an asymmetric three-transistor :class:`LoadPart`.

    *ts1*'s output feeds the shared ``INNERSOURCE`` node; *ts2*'s gate-input
    chains from either *ts1*'s ``INNEROUTPUT`` (when *ts1* is a single diode
    transistor) or directly from ``OUT1``.
    """

    connect((out, LoadPart.OUT1), (ts1, TransistorStack.IN))
    connect((out, LoadPart.INNERSOURCE), (ts1, TransistorStack.OUT))
    connect((out, LoadPart.SOURCE), (ts1, TransistorStack.SOURCE))

    connect((out, LoadPart.OUT2), (ts2, TransistorStack.OUT))

    if len(ts1.instances) == 1 and ts1.instances[0].name == "dt":
        connect((out, LoadPart.INNEROUTPUT), (ts2, TransistorStack.INOUTPUT))
    else:
        connect((out, LoadPart.OUT1), (ts2, TransistorStack.INOUTPUT))

    connect((out, LoadPart.INNERSOURCE), (ts2, TransistorStack.INSOURCE))
    connect((out, LoadPart.INNERTRANSISTORSTACK2), (ts2, TransistorStack.INNER))
    connect((out, LoadPart.SOURCE), (ts2, TransistorStack.SOURCE))
    return out


def createThreeTransistorLoadPart(ts1: TransistorStack, ts2: TransistorStack):
    """Build an asymmetric three-transistor :class:`LoadPart` from a
    one-transistor branch (*ts1*) and a two-transistor branch (*ts2*)."""
    lp = LoadPart(id=1, techtype="p")
    lp.ports = [ LoadPart.OUT1, LoadPart.OUT2, LoadPart.SOURCE, LoadPart.INNERTRANSISTORSTACK2, LoadPart.INNERSOURCE]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") or ts2.instances[0].name.startswith("vb"):
        pass

    lp = connectInstanceTerminalsOfThreeTransistorLoadPart(lp, ts1, ts2)
    return lp


def createTwoTransistorLoadPartsVoltageBiases(
    oneTransistorVoltageBiases: list[VoltageBias],
):
    """Build one two-branch :class:`LoadPart` per one-transistor voltage bias,
    pairing it with itself as both branches (skips multi-transistor biases)."""
    out: list[Circuit] = []
    for voltageBias in oneTransistorVoltageBiases:

        if len(voltageBias.instances) == 1:
            ts1 = createTransistorStack(1, voltageBias)
            ts2 = createTransistorStack(2, voltageBias)

            # fmt: on
            loadpart = createTwoTransistorLoadPart(ts1, ts2)
            out.append(loadpart)
            pass

    return out


def createTwoTransistorLoadPartsMixed(
    oneTransistorVoltageBiases: list[VoltageBias], oneTransistorCurrentBiases: list[CurrentBias]
) -> List[LoadPart]:
    """Build one two-branch :class:`LoadPart` per (voltage bias, current bias)
    pair across the full cross-product of the two input lists."""
    out = []
    for voltageBias in oneTransistorVoltageBiases:
        for currentBias in oneTransistorCurrentBiases:
            ts1 = createTransistorStack(1, voltageBias)
            ts2 = createTransistorStack(2, currentBias)

            # fmt: on

            loadpart = createTwoTransistorLoadPart(ts1, ts2)
            out.append(loadpart)
    return out


def createThreeTransistorLoadPartsMixed(
    oneTransistorVoltageBiases: list[VoltageBias], twoTransistorCurrentBiases: list[CurrentBias]
)-> list[LoadPart]:
    """Build one three-transistor :class:`LoadPart` per (one-transistor
    voltage bias, two-transistor current bias) pair across the full
    cross-product of the two input lists."""
    out = []
    for voltageBias in oneTransistorVoltageBiases:
        for currentBias in twoTransistorCurrentBiases:
            ts1 = createTransistorStack(1, voltageBias)
            ts2 = createTransistorStack(2, currentBias)

            # fmt: on

            loadpart = createThreeTransistorLoadPart(ts1, ts2)
            out.append(loadpart)
    return out


def createFourTransistorLoadPart(ts1, ts2)-> LoadPart:
    """Build a four-transistor :class:`LoadPart` from two two-transistor
    branches; see :func:`connectInstanceTerminalsOfFourTransistorLoadPart`
    for the port layout, which differs when both branches are voltage biases."""
    lp = LoadPart(id=1, techtype="p")
    lp.ports = [
        LoadPart.OUT1,
        LoadPart.OUT2,
        LoadPart.INNERTRANSISTORSTACK1,
        LoadPart.INNERTRANSISTORSTACK2,
        LoadPart.SOURCE
    ]
    lp.add_instance(ts1)
    lp.add_instance(ts2)

    if ts1.instances[0].name.startswith("vb") and ts2.instances[0].name.startswith(
        "vb"
    ):
        lp.ports  += [LoadPart.OUTOUTPUT1, LoadPart.OUTOUTPUT2, LoadPart.OUTSOURCE1, LoadPart.OUTSOURCE2]
    else:
        lp.ports += [LoadPart.INNEROUTPUT, LoadPart.INNERSOURCE]

    lp = connectInstanceTerminalsOfFourTransistorLoadPart(lp, ts1, ts2)
    return lp


def createFourTransistorLoadPartsMixed(
    twoTransistorVoltageBiases, twoTransistorCurrentBiases
):
    """Build one four-transistor :class:`LoadPart` per (two-transistor
    voltage bias, two-transistor current bias) pair across the full
    cross-product of the two input lists."""
    out = []
    for voltageBias in twoTransistorVoltageBiases:
        for currentBias in twoTransistorCurrentBiases:
            # fmt: on
            ts1 = createTransistorStack(1, voltageBias)
            ts2 = createTransistorStack(2, currentBias)
            loadpart = createFourTransistorLoadPart(ts1, ts2)
            out.append(loadpart)
    return out


def createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases):
    """Build one four-transistor :class:`LoadPart` per two-transistor voltage
    bias, pairing it with itself as both branches."""
    out = []
    for voltageBias in twoTransistorVoltageBiases:
        ts1 = createTransistorStack(1, voltageBias)
        ts2 = createTransistorStack(2, voltageBias)
        loadpart = createFourTransistorLoadPart(ts1, ts2)
        out.append(loadpart)
    return out


def createTwoTransistorLoadPartsCurrentBiasesDifferentSources(
    oneTransistorCurrentBiases,
):
    """Build one independent-source, two-branch :class:`LoadPart` per
    one-transistor current bias, pairing it with itself as both branches."""
    out = []
    for currentBias in oneTransistorCurrentBiases:
        ts1 = createTransistorStack(1, currentBias)
        ts2 = createTransistorStack(2, currentBias)
        loadpart = createTwoTransistorLoadPartDifferentSources(ts1, ts2)
        out.append(loadpart)
    return out


def createFourTransistorLoadPartsCurrentBiases(twoTransistorCurrentBiases):
    """Build one four-transistor :class:`LoadPart` per two-transistor current
    bias, pairing it with itself as both branches."""
    out = []
    for currentBias in twoTransistorCurrentBiases:
        ts1 = createTransistorStack(1, currentBias)
        ts2 = createTransistorStack(2, currentBias)

        loadpart = createFourTransistorLoadPart(ts1, ts2)
        out.append(loadpart)
    return out


def createTwoTransistorLoadPartsCurrentBiases(oneTransistorCurrentBiases):
    """Build one shared-source, two-branch :class:`LoadPart` per one-transistor
    current bias, pairing it with itself as both branches."""
    out = []
    for currentBias in oneTransistorCurrentBiases:
        ts1 = createTransistorStack(1, currentBias)
        ts2 = createTransistorStack(2, currentBias)

        loadpart = createTwoTransistorLoadPart(ts1, ts2)
        out.append(loadpart)
    return out


class LoadPartManager:
    """Factory/cache for HL3 ``LoadPart`` branches, combining HL2 voltage and
    current biases into two-, three-, and four-transistor branches.

    Most ``create*`` methods are thin convenience wrappers fetching the
    relevant :class:`~topogen.HL2.vb.VoltageBiasManager`/
    :class:`~topogen.HL2.cb.CurrentBiasManager` lists and delegating to the
    matching module-level ``create*LoadParts*`` function. ``case N`` comments
    mark the enumeration cases used by the ``if __name__ == "__main__"``
    gallery-generation block at the bottom of this file.
    """

    def __init__(self):
        """Build and cache the PMOS and NMOS voltage-bias load parts."""
        self.initializeLoadPartsPmos()
        self.initializeLoadPartsNmos()

    # case 1
    def createTwoTransistorsLoadPartsLoadPartsPmosVoltageBiases(self):
        """Return two-branch PMOS load parts built from one-transistor voltage biases."""
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        )
        loadParts = createTwoTransistorLoadPartsVoltageBiases(
            oneTransistorVoltageBiases
        )
        return loadParts

    # case 2
    def createFourTransistorsLoadPartsLoadPartsPmosVoltageBiases(self):
        """Return four-transistor PMOS load parts built from two-transistor voltage biases."""
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        )

        return createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    # case 3
    def createFourTransistorsLoadPartsLoadPartsNmosVoltageBiases(self):
        """Return four-transistor NMOS load parts built from two-transistor voltage biases."""
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        )

        return createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    # case 4
    def createTwoTransistorsLoadPartsLoadPartsNmosVoltageBiases(self):
        """Return two-branch NMOS load parts built from one-transistor voltage biases."""
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
        )
        loadParts = createTwoTransistorLoadPartsVoltageBiases(
            oneTransistorVoltageBiases
        )
        return loadParts

    # case 5
    def createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources(self):
        """Return independent-source, two-branch PMOS load parts built from
        one-transistor current biases."""
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        )
        loadParts = createTwoTransistorLoadPartsCurrentBiasesDifferentSources(
            oneTransistorCurrentBiases
        )
        return loadParts

    # case 6
    def createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources(self):
        """Return independent-source, two-branch NMOS load parts built from
        one-transistor current biases."""
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        )
        loadParts = createTwoTransistorLoadPartsCurrentBiasesDifferentSources(
            oneTransistorCurrentBiases
        )
        return loadParts

    # case 7
    def createLoadPartsPmosFourTransistorCurrentBiases(self):
        """Return four-transistor PMOS load parts built from two-transistor current biases."""
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        )
        loadParts = createFourTransistorLoadPartsCurrentBiases(
            twoTransistorCurrentBiases
        )
        return loadParts

    # case 8
    def createLoadPartsNmosFourTransistorCurrentBiases(self):
        """Return four-transistor NMOS load parts built from two-transistor current biases."""
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        )
        loadParts = createFourTransistorLoadPartsCurrentBiases(
            twoTransistorCurrentBiases
        )
        return loadParts

    # case 9
    def createLoadPartsPmosCurrentBiases(self):
        """Return all PMOS current-bias load parts: two-branch (one-transistor
        biases) plus four-transistor (two-transistor biases)."""
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        )
        return createTwoTransistorLoadPartsCurrentBiases(
            oneTransistorCurrentBiases
        ) + createFourTransistorLoadPartsCurrentBiases(twoTransistorCurrentBiases)

    # case 10
    def createLoadPartsNmosCurrentBiases(self):
        """Return all NMOS current-bias load parts: two-branch (one-transistor
        biases) plus four-transistor (two-transistor biases)."""
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        )
        return createTwoTransistorLoadPartsCurrentBiases(
            oneTransistorCurrentBiases
        ) + createFourTransistorLoadPartsCurrentBiases(twoTransistorCurrentBiases)

    def createLoadPartsPmosVoltageBiases(self):
        """Return all PMOS voltage-bias load parts: two-branch (one-transistor
        biases) plus four-transistor (two-transistor biases)."""
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        )
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        )
        return createTwoTransistorLoadPartsVoltageBiases(
            oneTransistorVoltageBiases
        ) + createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    def createLoadPartsNmosVoltageBiases(self):
        """Return all NMOS voltage-bias load parts: two-branch (one-transistor
        biases) plus four-transistor (two-transistor biases)."""
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
        )
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        )
        return createTwoTransistorLoadPartsVoltageBiases(
            oneTransistorVoltageBiases
        ) + createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    def createLoadPartsPmosMixed(self):
        """Return all mixed PMOS voltage+current-bias load parts: two-, three-,
        and four-transistor variants combined."""
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        )
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        )
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        )
        return (
            createTwoTransistorLoadPartsMixed(
                oneTransistorVoltageBiases, oneTransistorCurrentBiases
            )
            + createThreeTransistorLoadPartsMixed(
                oneTransistorVoltageBiases, twoTransistorCurrentBiases
            )
            + createFourTransistorLoadPartsMixed(
                twoTransistorVoltageBiases, twoTransistorCurrentBiases
            )
        )

    def createLoadPartsNmosMixed(self):
        """Return all mixed NMOS voltage+current-bias load parts: two-, three-,
        and four-transistor variants combined."""
        oneTransistorVoltageBiases = (
            VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
        )
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        )
        oneTransistorCurrentBiases = (
            CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        )

        return (
            createTwoTransistorLoadPartsMixed(
                oneTransistorVoltageBiases, oneTransistorCurrentBiases
            )
            + createThreeTransistorLoadPartsMixed(
                oneTransistorVoltageBiases, twoTransistorCurrentBiases
            )
            + createFourTransistorLoadPartsMixed(
                twoTransistorVoltageBiases, twoTransistorCurrentBiases
            )
        )

    def createLoadPartsPmosFourTransistorMixed(self):
        """Return four-transistor PMOS load parts mixing two-transistor
        voltage and current biases."""
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        )
        return createFourTransistorLoadPartsMixed(
            twoTransistorVoltageBiases, twoTransistorCurrentBiases
        )

    def createLoadPartsNmosFourTransistorMixed(self):
        """Return four-transistor NMOS load parts mixing two-transistor
        voltage and current biases."""
        twoTransistorVoltageBiases = (
            VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        )
        twoTransistorCurrentBiases = (
            CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        )
        return createFourTransistorLoadPartsMixed(
            twoTransistorVoltageBiases, twoTransistorCurrentBiases
        )

    def initializeLoadPartsPmos(self):
        """Build the two- and four-transistor PMOS voltage-bias load parts and cache them on ``self``."""
        oneTransistorVoltageBiases = VoltageBiasManager().getOneTransistorVoltageBiasesPmos()
        twoTransistorVoltageBiases = VoltageBiasManager().getTwoTransistorVoltageBiasesPmos()
        # oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        # twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()

        self.twoTransistorsLoadPartsPmosVoltageBiases_ = createTwoTransistorLoadPartsVoltageBiases(oneTransistorVoltageBiases)
        self.fourTransistorsLoadPartsPmosVoltageBiases_ = createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    def initializeLoadPartsNmos(self):
        """Build the two- and four-transistor NMOS voltage-bias load parts and cache them on ``self``."""
        oneTransistorVoltageBiases = VoltageBiasManager().getOneTransistorVoltageBiasesNmos()
        twoTransistorVoltageBiases = VoltageBiasManager().getTwoTransistorVoltageBiasesNmos()
        # oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesNmos();
        # twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesNmos();

        self.twoTransistorsLoadPartsNmosVoltageBiases_ = createTwoTransistorLoadPartsVoltageBiases(oneTransistorVoltageBiases)
        self.fourTransistorsLoadPartsNmosVoltageBiases_ = createFourTransistorLoadPartsVoltageBiases(twoTransistorVoltageBiases)

    def getLoadPartsPmosVoltageBiases(self):
        """Return the cached PMOS voltage-bias load parts (two- + four-transistor)."""
        assert self.twoTransistorsLoadPartsPmosVoltageBiases_ != None
        assert self.fourTransistorsLoadPartsPmosVoltageBiases_ != None

        return self.twoTransistorsLoadPartsPmosVoltageBiases_ + self.fourTransistorsLoadPartsPmosVoltageBiases_


    def getLoadPartsNmosVoltageBiases(self):
        """Return the cached NMOS voltage-bias load parts (two- + four-transistor)."""
        assert self.twoTransistorsLoadPartsNmosVoltageBiases_ is not None
        assert self.fourTransistorsLoadPartsNmosVoltageBiases_ is not None
        return self.twoTransistorsLoadPartsNmosVoltageBiases_  + self.fourTransistorsLoadPartsNmosVoltageBiases_



def print_json(data):
    """Debug helper: pretty-print *data* as JSON plus its length."""
    print(json.dumps(data, indent=4))
    print("length: ", len(data))


def print_json_v2(data: list, print_graphviz=False):
    """Debug helper: optionally print each circuit's graphviz source, then its count."""
    for d in data:
        if print_graphviz:
            print(d.graphviz())
    print(f"# numbers: {len(data)}")


create_methods = [
    "createTwoTransistorsLoadPartsLoadPartsPmosVoltageBiases",
    "createFourTransistorsLoadPartsLoadPartsPmosVoltageBiases",
    "createTwoTransistorsLoadPartsLoadPartsNmosVoltageBiases",
    "createFourTransistorsLoadPartsLoadPartsNmosVoltageBiases",
    "createLoadPartsPmosTwoTransistorCurrentBiasesDifferentSources",
    "createLoadPartsNmosTwoTransistorCurrentBiasesDifferentSources",
    "createLoadPartsPmosFourTransistorCurrentBiases",
    "createLoadPartsNmosFourTransistorCurrentBiases",
    "createLoadPartsPmosCurrentBiases",
    "createLoadPartsNmosCurrentBiases",
    "createLoadPartsPmosVoltageBiases",
    "createLoadPartsNmosVoltageBiases",
    "createLoadPartsPmosMixed",
    "createLoadPartsNmosMixed",
    "createLoadPartsPmosFourTransistorMixed",
    "createLoadPartsNmosFourTransistorMixed",
]

if __name__ == "__main__":

    lp_mng = LoadPartManager()
    for case_id, method in enumerate(create_methods):
        for circuit_id, circuit in enumerate(getattr(lp_mng, method)()):
            if circuit != None:
                save_graphviz_figure(
                    circuit, filename=GALLERY_DOT_DIR/ f"lp_{case_id}_{circuit_id}.dot"
                )
                convert_dot_to_png(
                    GALLERY_DOT_DIR/ f"lp_{case_id}_{circuit_id}.dot", GALLERY_IMAGE_DIR/ f"lp_{case_id}_{circuit_id}.png"
                )
            else:
                logger.warning(f"circuit is None for {method} - {case_id}-{circuit_id}")
                exit(1)
