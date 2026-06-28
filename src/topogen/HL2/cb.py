from copy import deepcopy
from itertools import chain
from typing import Iterator

from topogen.common.circuit import *

GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "cb" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "cb" / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


class CurrentBiasManager:
    """Factory for the one- and two-transistor current-bias stacks at HL2.

    A *current bias* is a stack-style network (distinct from the
    common-source/common-gate :class:`~topogen.HL2.cm.CurrentMirror`): the
    one-transistor form is a single diode/normal transistor, and the
    two-transistor form cascodes a source transistor under an output
    transistor, with the inner node exposed as ``CurrentBias.INNER``.
    """

    def __init__(self):
        """Build and cache every one-/two-transistor NMOS and PMOS bias."""
        self.initializeOneTransistorCurrentBiasesNmos()
        self.initializeOneTransistorCurrentBiasesPmos()
        self.initializeTwoTransistorCurrentBiasesNmos()
        self.initializeTwoTransistorCurrentBiasesPmos()

    def getAllCurrentBiasesPmos(self) -> list[CurrentBias]:
        """Return every cached PMOS bias (one-transistor + both two-transistor variants)."""
        return [self.oneTransistorCurrentBiasesPmos_] + list(
            self.twoTransistorCurrentBiasesPmos_
        )

    def getAllCurrentBiasesNmos(self) -> list[CurrentBias]:
        """Return every cached NMOS bias (one-transistor + both two-transistor variants)."""
        return [self.oneTransistorCurrentBiasesNmos_] + list(
            self.twoTransistorCurrentBiasesNmos_
        )

    def getOneTransistorCurrentBiasesPmos(self) -> list[CurrentBias]:
        """Return the single one-transistor PMOS bias, wrapped in a list."""
        return [self.oneTransistorCurrentBiasesPmos_]

    def getTwoTransistorCurrentBiasesPmos(self) -> list[CurrentBias]:
        """Return both two-transistor PMOS bias variants (normal+normal, diode+normal)."""
        return list(self.twoTransistorCurrentBiasesPmos_)

    def getOneTransistorCurrentBiasesNmos(self) -> list[CurrentBias]:
        """Return the single one-transistor NMOS bias, wrapped in a list."""
        return [self.oneTransistorCurrentBiasesNmos_]

    def getTwoTransistorCurrentBiasesNmos(self) -> list[CurrentBias]:
        """Return both two-transistor NMOS bias variants (normal+normal, diode+normal)."""
        return list(self.twoTransistorCurrentBiasesNmos_)

    def getNormalTransistorCurrentBias(self, techtype: str):
        """Return the one-transistor bias of *techtype* built from a plain
        (non-diode) transistor, or ``None`` if not found.

        Parameters
        ----------
        techtype:
            ``"n"`` for NMOS, anything else is treated as PMOS.
        """
        if techtype == "n":
            for cb in self.oneTransistorCurrentBiasesNmos_:
                if len(cb.instances) == 1 and cb.instances[0].name == "nt":
                    return cb
        else:
            for cb in self.oneTransistorCurrentBiasesPmos_:
                if len(cb.instances) == 1 and cb.instances[0].name == "nt":
                    return cb

    def initializeOneTransistorCurrentBiasesPmos(self):
        """Build the one-transistor PMOS bias and cache it on ``self``."""
        normalTransistor = NormalTransistor(techtype="p")
        self.oneTransistorCurrentBiasesPmos_ = self.createOneTransistorCurrentBias(
            normalTransistor
        )

    def initializeTwoTransistorCurrentBiasesPmos(self):
        """Build both two-transistor PMOS bias variants and cache them on ``self``."""
        normalTransistorPmos = NormalTransistor(techtype="p")
        diodeTransistorPmos = DiodeTransistor(techtype="p")
        self.twoTransistorCurrentBiasesPmos_ = self.createTwoTransistorCurrentBias(
            normalTransistorPmos, diodeTransistorPmos
        )

    def initializeOneTransistorCurrentBiasesNmos(self):
        """Build the one-transistor NMOS bias and cache it on ``self``."""
        normalTransistor = NormalTransistor(techtype="n")
        self.oneTransistorCurrentBiasesNmos_ = self.createOneTransistorCurrentBias(
            normalTransistor
        )

    def initializeTwoTransistorCurrentBiasesNmos(self):
        """Build both two-transistor NMOS bias variants and cache them on ``self``."""
        normalTransistorNmos = NormalTransistor(techtype="n")
        diodeTransistorNmos = DiodeTransistor(techtype="n")
        self.twoTransistorCurrentBiasesNmos_ = self.createTwoTransistorCurrentBias(
            normalTransistorNmos, diodeTransistorNmos
        )

    def createTwoTransistorCurrentBias(
        self, normalTransistor: Circuit, diodeTransistor: Circuit
    ) -> Iterator[CurrentBias]:
        """Build the two two-transistor bias variants for one tech type.

        Returns an iterator of two :class:`CurrentBias` circuits: a
        normal+normal stack (two independent copies of *normalTransistor*)
        and a diode+normal stack (*diodeTransistor* as the source transistor,
        *normalTransistor* as the output transistor).
        """
        nt1 = deepcopy(normalTransistor)
        nt2 = deepcopy(normalTransistor)
        nt2.id = 2
        firstTwoTransistorCurrentBias = self.createTwoTransistorCircuit(nt1, nt2)
        secondTwoTransistorCurrentBias = self.createTwoTransistorCircuit(
            diodeTransistor, normalTransistor
        )
        return chain([firstTwoTransistorCurrentBias, secondTwoTransistorCurrentBias])

    def createOneTransistorCurrentBias(self, normalTransistor: Circuit) -> CurrentBias:
        """Wrap a single transistor in a one-transistor :class:`CurrentBias`
        (``IN``/``OUT``/``SOURCE`` ports tied to gate/drain/source)."""
        cb = CurrentBias(id=1, techtype=normalTransistor.tech)
        cb.ports = [CurrentBias.IN, CurrentBias.OUT, CurrentBias.SOURCE]
        cb.add_instance(normalTransistor)
        cb = self.connectInstanceTerminalsOneTransistorCurrentBias(cb, normalTransistor)
        return cb

    def createTwoTransistorCircuit(
        self, sourceTransistor: Circuit, outputTransistor: Circuit
    ) -> CurrentBias:
        """Stack *sourceTransistor* under *outputTransistor* into a
        two-transistor :class:`CurrentBias`.

        *sourceTransistor*'s drain becomes the shared inner node
        (``CurrentBias.INNER``), which is *outputTransistor*'s source.
        """
        cb = CurrentBias(id=1, techtype=sourceTransistor.tech)
        cb.ports = [
            CurrentBias.INSOURCE,
            CurrentBias.INOUTPUT,
            CurrentBias.INNER,
            CurrentBias.OUT,
            CurrentBias.SOURCE,
        ]
        cb.add_instance(sourceTransistor)
        cb.add_instance(outputTransistor)
        cb = self.connectInstanceTerminalsTwoTransistorCurrentBias(
            cb, sourceTransistor, outputTransistor
        )
        return cb

    def connectInstanceTerminalsOneTransistorCurrentBias(
        self, cb: CurrentBias, transistor: Circuit
    ) -> CurrentBias:
        """Wire *transistor*'s gate/drain/source to *cb*'s ``IN``/``OUT``/``SOURCE``."""
        connect((cb, CurrentBias.IN), (transistor, "gate"))
        connect((cb, CurrentBias.OUT), (transistor, "drain"))
        connect((cb, CurrentBias.SOURCE), (transistor, "source"))
        return cb

    def connectInstanceTerminalsTwoTransistorCurrentBias(
        self, cb: CurrentBias, sourceTransistor: Circuit, outputTransistor: Circuit
    ) -> CurrentBias:
        """Wire both stacked transistors' pins to *cb*'s ports.

        *sourceTransistor*'s gate/drain/source map to ``INSOURCE``/``INNER``/
        ``SOURCE``; *outputTransistor*'s gate/drain/source map to
        ``INOUTPUT``/``OUT``/``INNER`` (its source sits on the inner node).
        """
        connect((cb, CurrentBias.INSOURCE), (sourceTransistor, "gate"))
        connect((cb, CurrentBias.INNER), (sourceTransistor, "drain"))
        connect((cb, CurrentBias.SOURCE), (sourceTransistor, "source"))

        connect((cb, CurrentBias.INOUTPUT), (outputTransistor, "gate"))
        connect((cb, CurrentBias.OUT), (outputTransistor, "drain"))
        connect((cb, CurrentBias.INNER), (outputTransistor, "source"))
        return cb


if __name__ == "__main__":

    cb_mng = CurrentBiasManager()

    all_cb = list(cb_mng.getAllCurrentBiasesNmos()) + list(
        cb_mng.getAllCurrentBiasesPmos()
    )
    case_id = 0
    for circuit_id, circuit in enumerate(all_cb):
        print(circuit)
        save_graphviz_figure(
            circuit, filename=GALLERY_DOT_DIR / f"cb_{case_id}_{circuit_id}.dot"
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR / f"cb_{case_id}_{circuit_id}.dot",
            GALLERY_IMAGE_DIR / f"cb_{case_id}_{circuit_id}.png",
        )
