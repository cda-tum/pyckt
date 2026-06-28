from itertools import chain
from pathlib import Path
from typing import Callable, Iterator

from topogen.common.circuit import *
from topogen.HL2.vb import *
from topogen.HL3.lp import *

# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "sb" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "sb" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

def connectInstanceTerminalsOfOneTransistorStageBias(stageBias:Circuit, currentBias:Circuit) -> Circuit:
    """Wire a one-transistor :class:`~topogen.HL2.cb.CurrentBias`'s
    ``IN``/``OUT``/``SOURCE`` straight through to *stageBias*'s matching ports."""
    connect((stageBias, StageBias.IN), (currentBias, CurrentBias.IN))
    connect((stageBias, StageBias.OUT), (currentBias, CurrentBias.OUT))
    connect((stageBias, StageBias.SOURCE), (currentBias, CurrentBias.SOURCE))
    return stageBias

def connectInstanceTerminalsOfTwoTransistorStageBias(stageBias:Circuit, currentBias:Circuit) -> Circuit:
    """Wire a two-transistor :class:`~topogen.HL2.cb.CurrentBias`'s
    ``INOUTPUT``/``INSOURCE``/``INNER``/``OUT``/``SOURCE`` straight through to
    *stageBias*'s matching ports."""
    connect((stageBias, StageBias.INOUTPUT), (currentBias, CurrentBias.INOUTPUT))
    connect((stageBias, StageBias.INSOURCE), (currentBias, CurrentBias.INSOURCE ))
    connect((stageBias, StageBias.INNER), (currentBias, CurrentBias.INNER ))
    connect((stageBias, StageBias.OUT), (currentBias, CurrentBias.OUT))
    connect((stageBias, StageBias.SOURCE), (currentBias, CurrentBias.SOURCE))
    return stageBias

def createOneTransistorStageBias(currentBias) -> Circuit:
    """Wrap a one-transistor :class:`~topogen.HL2.cb.CurrentBias` in a :class:`StageBias`."""
    sb = StageBias(id=1, techtype="?")
    sb.ports = [
        StageBias.OUT,
        StageBias.IN,
        StageBias.SOURCE,
    ]
    sb.add_instance(currentBias)
    sb = connectInstanceTerminalsOfOneTransistorStageBias(sb, currentBias)
    return sb

def createTwoTransistorStageBias(currentBias) -> Circuit:
    """Wrap a two-transistor :class:`~topogen.HL2.cb.CurrentBias` in a :class:`StageBias`."""
    sb = StageBias(id=1, techtype="?")
    sb.ports = [
        StageBias.OUT,
        StageBias.INOUTPUT,
        StageBias.INSOURCE,
        StageBias.INNER,
        StageBias.SOURCE,
    ]
    sb.add_instance(currentBias)
    sb = connectInstanceTerminalsOfTwoTransistorStageBias(sb, currentBias)
    return sb

def createOneTransistorStageBiases(oneTransistorCurrentBiases: list[Circuit])->Iterator[Circuit]:
    """Wrap each one-transistor current bias in *oneTransistorCurrentBiases* as a :class:`StageBias`."""
    for currentBias in oneTransistorCurrentBiases:
        yield createOneTransistorStageBias(currentBias)

def createTwoTransistorStageBiases(twoTransistorCurrentBiases) ->Iterator[Circuit]:
    """Wrap each two-transistor current bias in *twoTransistorCurrentBiases* as a :class:`StageBias`."""
    for currentBias in twoTransistorCurrentBiases:
        yield createTwoTransistorStageBias(currentBias)

def initializeStageBiasesPmos():
    """Return a fresh chained iterator over every PMOS stage bias (one- and two-transistor)."""
    oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
    twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
    return chain(createOneTransistorStageBiases(oneTransistorCurrentBiases), createTwoTransistorStageBiases(twoTransistorCurrentBiases))

def initializeStageBiasesNmos():
    """Return a fresh chained iterator over every NMOS stage bias (one- and two-transistor)."""
    oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
    twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
    return chain(createOneTransistorStageBiases(oneTransistorCurrentBiases), createTwoTransistorStageBiases(twoTransistorCurrentBiases))


class StageBiasManager:
    """Factory/cache for per-stage bias networks, built from HL2 current biases.

    .. note::
       This class defines methods named ``initializeStageBiasesPmos`` /
       ``initializeStageBiasesNmos`` that intentionally shadow the
       module-level functions of the same name — the methods *cache* the
       result on ``self`` (consumed by :meth:`getAllStageBiasesPmos` /
       :meth:`getAllStageBiasesNmos`), while
       :meth:`createStageBiasesPmos` / :meth:`createStageBiasesNmos` call the
       *module-level* functions directly to return a fresh, uncached iterator.
    """

    def __init__(self):
        """Build and cache every PMOS and NMOS stage bias."""
        self.initializeStageBiasesPmos()
        self.initializeStageBiasesNmos()
        pass
    def createStageBiasesPmos(self) ->Iterator[Circuit]:
        """Return a fresh (uncached) iterator over every PMOS stage bias."""
        return initializeStageBiasesPmos()
    def createStageBiasesNmos(self) ->Iterator[Circuit]:
        """Return a fresh (uncached) iterator over every NMOS stage bias."""
        return initializeStageBiasesNmos()

    def getOneTransistorStageBiasesNmos(self) ->Iterator[Circuit]:
        """Return a fresh iterator over the one-transistor NMOS stage biases."""
        oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        return createOneTransistorStageBiases(oneTransistorCurrentBiases)
    def getTwoTransistorStageBiasesNmos(self) ->Iterator[Circuit]:
        """Return a fresh iterator over the two-transistor NMOS stage biases."""
        twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()
        return createTwoTransistorStageBiases(twoTransistorCurrentBiases)


    def getOneTransistorStageBiasesPmos(self) ->Iterator[Circuit]:
        """Return a fresh iterator over the one-transistor PMOS stage biases."""
        oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        return createOneTransistorStageBiases(oneTransistorCurrentBiases)
    def getTwoTransistorStageBiasesPmos(self) ->Iterator[Circuit]:
        """Return a fresh iterator over the two-transistor PMOS stage biases."""
        twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()
        return createTwoTransistorStageBiases(twoTransistorCurrentBiases)

    def initializeStageBiasesNmos(self)-> None:
        """Build the one- and two-transistor NMOS stage biases and cache them on ``self``."""
        oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesNmos()
        twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesNmos()

        self.oneTransistorBiasesNmos_ = createOneTransistorStageBiases(oneTransistorCurrentBiases)
        self.twoTransistorBiasesNmos_ = createTwoTransistorStageBiases(twoTransistorCurrentBiases)

    def initializeStageBiasesPmos(self)-> None:
        """Build the one- and two-transistor PMOS stage biases and cache them on ``self``."""

        oneTransistorCurrentBiases = CurrentBiasManager().getOneTransistorCurrentBiasesPmos()
        twoTransistorCurrentBiases = CurrentBiasManager().getTwoTransistorCurrentBiasesPmos()

        self.oneTransistorBiasesPmos_ = createOneTransistorStageBiases(oneTransistorCurrentBiases)
        self.twoTransistorBiasesPmos_ = createTwoTransistorStageBiases(twoTransistorCurrentBiases)


    def getAllStageBiasesNmos(self):
        """Return every cached NMOS stage bias (one- and two-transistor) as a list."""
        assert self.oneTransistorBiasesNmos_ is not None
        assert self.twoTransistorBiasesNmos_ is not None
        return  list(self.oneTransistorBiasesNmos_) + list(self.twoTransistorBiasesNmos_)

    def getAllStageBiasesPmos(self):
        """Return every cached PMOS stage bias (one- and two-transistor) as a list."""
        assert self.oneTransistorBiasesPmos_ is not None
        assert self.twoTransistorBiasesPmos_ is not None
        return  list(self.oneTransistorBiasesPmos_) + list(self.twoTransistorBiasesPmos_)


if __name__ == "__main__":
    mng = StageBiasManager()
    methods: list[Callable[[], Iterator[Circuit]]] = [
        mng.createStageBiasesPmos,
        mng.createStageBiasesNmos,
    ]

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
