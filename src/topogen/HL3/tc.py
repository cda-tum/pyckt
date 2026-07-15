from copy import deepcopy
from pathlib import Path
from typing import Callable, Iterator

from topogen.common.circuit import *
from topogen.HL2.dp import *
from topogen.HL2.vb import *
from topogen.HL3.lp import *

# fmt: off

GALLERY_DOT_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "tc" / "dots"
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = Path(__file__).parent.parent.parent.parent / "gallery" / "HL3" / "tc" / "images"
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

tc = Transconductance
def connectInstanceTerminalsOfSimpleTransconductance(tc: Transconductance, dp: DiffPair) -> Transconductance:
    """Wire a single :class:`~topogen.HL2.dp.DiffPair` straight through to *tc*'s
    input/output/source ports (one-to-one, no feedback or complementary pairing)."""
    connect((tc, Transconductance.INPUT1), (dp, DiffPair.INPUT1))
    connect((tc, Transconductance.INPUT2), (dp, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1), (dp, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2), (dp, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE), (dp, DiffPair.SOURCE))
    return tc

def connectInstanceTerminalsOfFeedbackTransconductance(tc: Transconductance, dp1: DiffPair, dp2: DiffPair) -> Transconductance:
    """Wire two copies of the same :class:`DiffPair` into a feedback
    transconductance: each pair's ``INPUT2`` ties to the shared ``INNER``
    feedback node, and each pair gets an independent source
    (``SOURCE_1``/``SOURCE_2``)."""
    connect((tc, Transconductance.INPUT1), (dp1, DiffPair.INPUT1))
    connect((tc, Transconductance.INNER), (dp1, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1), (dp1, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2), (dp1, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE_1), (dp1, DiffPair.SOURCE))


    connect((tc, Transconductance.INPUT2), (dp2, DiffPair.INPUT1))
    connect((tc, Transconductance.INNER), (dp2, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1), (dp2, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2), (dp2, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE_2), (dp2, DiffPair.SOURCE))
    return tc

def connectInstanceTerminalsOfComplementaryTransconductance(tc: Transconductance, dp_nmos: DiffPair, dp_pmos: DiffPair) -> Transconductance:
    """Wire an NMOS and a PMOS :class:`DiffPair` sharing the same ``INPUT1``/
    ``INPUT2`` nodes but with independent sources and outputs
    (``OUT1NMOS``/``OUT2NMOS`` vs. ``OUT1PMOS``/``OUT2PMOS``)."""
    connect((tc, Transconductance.INPUT1), (dp_nmos, DiffPair.INPUT1))
    connect((tc, Transconductance.INPUT2), (dp_nmos, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1NMOS), (dp_nmos, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2NMOS), (dp_nmos, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE_NMOS), (dp_nmos, DiffPair.SOURCE))


    connect((tc, Transconductance.INPUT1), (dp_pmos, DiffPair.INPUT1))
    connect((tc, Transconductance.INPUT2), (dp_pmos, DiffPair.INPUT2))
    connect((tc, Transconductance.OUT1PMOS), (dp_pmos, DiffPair.OUTPUT1))
    connect((tc, Transconductance.OUT2PMOS), (dp_pmos, DiffPair.OUTPUT2))
    connect((tc, Transconductance.SOURCE_PMOS), (dp_pmos, DiffPair.SOURCE))
    return tc

def createSimpleTransconductance(differentialPair):
    """Build a :class:`Transconductance` directly from one differential pair."""
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        Transconductance.OUT1,
        Transconductance.OUT2,
        Transconductance.INPUT1,
        Transconductance.INPUT2,
        Transconductance.SOURCE,
    ]
    tc.add_instance(differentialPair)
    tc = connectInstanceTerminalsOfSimpleTransconductance(tc, differentialPair)
    return tc

def createFeedbackTransconductance(differentialPair)-> Circuit:
    """Build a feedback :class:`Transconductance` from two deep copies of
    *differentialPair*, cross-wired via the shared ``INNER`` node
    (see :func:`connectInstanceTerminalsOfFeedbackTransconductance`)."""
    differentialPair1 = deepcopy(differentialPair)
    differentialPair2 = deepcopy(differentialPair)
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        Transconductance.OUT1,
        Transconductance.OUT2,
        Transconductance.INPUT1,
        Transconductance.INPUT2,
        Transconductance.SOURCE_1,
        Transconductance.SOURCE_2,
    ]
    tc.add_instance(differentialPair1)
    tc.add_instance(differentialPair2)

    tc = connectInstanceTerminalsOfFeedbackTransconductance(tc, differentialPair1, differentialPair2)
    return tc

def createComplementaryTransconductance(differentialPairPmos, differentialPairNmos) -> Circuit:
    """Build a complementary :class:`Transconductance` from one PMOS and one
    NMOS differential pair sharing the same input nodes."""
    tc = Transconductance(id=1, techtype="?")
    tc.ports = [
        Transconductance.OUT1NMOS,
        Transconductance.OUT2NMOS,
        Transconductance.OUT1PMOS,
        Transconductance.OUT2PMOS,
        Transconductance.INPUT1,
        Transconductance.INPUT2,
        Transconductance.SOURCE_PMOS,
        Transconductance.SOURCE_NMOS,
    ]
    tc.add_instance(differentialPairPmos)
    tc.add_instance(differentialPairNmos)
    tc = connectInstanceTerminalsOfComplementaryTransconductance(tc, differentialPairNmos, differentialPairPmos)
    return tc

class TransconductanceManager:
    """Factory for every HL3 transconductance variant, built from HL2 differential pairs.

    Wraps the module-level ``create*Transconductance`` functions, supplying
    them with the PMOS/NMOS pairs from
    :class:`~topogen.HL2.dp.DiffPairManager` so callers don't need to wire
    differential pairs themselves.
    """

    def __init__(self):
        """Build and cache every transconductance variant."""
        self.initializeTransconductances()

    def createSimpleTransconductance(self) -> Iterator[Circuit]:
        """Return ``[pmos_simple, nmos_simple]`` transconductances, freshly built."""
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()
        return iter([createSimpleTransconductance(differentialPairPmos), createSimpleTransconductance(differentialPairNmos)])

    def createFeedbackTransconductance(self) -> Iterator[Circuit]:
        """Return ``[pmos_feedback, nmos_feedback]`` transconductances, freshly built."""
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()
        return iter([createFeedbackTransconductance(differentialPairPmos), createFeedbackTransconductance(differentialPairNmos)])

    def createComplementaryTransconductance(self) -> Iterator[Circuit]:
        """Return the single complementary (NMOS+PMOS) transconductance, freshly built."""
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()
        return iter([createComplementaryTransconductance(differentialPairPmos, differentialPairNmos)])

    def getComplementaryTransconductance(self) -> Iterator[Circuit]:
        """Alias for :meth:`createComplementaryTransconductance`."""
        return self.createComplementaryTransconductance()

    def getSimpleTransconductancePmos(self) -> Iterator[Transconductance]:
        """Return a freshly-built simple PMOS transconductance."""
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        return createSimpleTransconductance(differentialPairPmos)

    def getSimpleTransconductanceNmos(self) -> Iterator[Transconductance]:
        """Return a freshly-built simple NMOS transconductance."""
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()
        return createSimpleTransconductance(differentialPairNmos)

    def initializeTransconductances(self):
        """Build the simple, feedback, and complementary variants and cache them on ``self``."""
        differentialPairPmos = DiffPairManager().getDifferentialPairPmos()
        differentialPairNmos = DiffPairManager().getDifferentialPairNmos()

        # initial all
        self.simpleTransconductancePmos_ = createSimpleTransconductance(differentialPairPmos)
        self.simpleTransconductanceNmos_ = createSimpleTransconductance(differentialPairNmos)

        self.feedbackTransconductancePmos_ = createFeedbackTransconductance(differentialPairPmos)
        self.feedbackTransconductanceNmos_ = createFeedbackTransconductance(differentialPairNmos)

        self.complementaryTransconductance_ = createComplementaryTransconductance(differentialPairPmos, differentialPairNmos)
        

    def getFeedbackTransconductanceNmos(self) -> Iterator[Transconductance]:
        """Return the cached feedback NMOS transconductance."""
        return self.feedbackTransconductanceNmos_

    def getFeedbackTransconductancePmos(self) -> Iterator[Transconductance]:
        """Return the cached feedback PMOS transconductance."""
        return self.feedbackTransconductancePmos_



if __name__ == "__main__":
    mng = TransconductanceManager()
    methods: list[Callable[[], Iterator[Circuit]]] = [
        mng.createSimpleTransconductance,
        mng.createFeedbackTransconductance,
        mng.createComplementaryTransconductance,
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
