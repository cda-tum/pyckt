from copy import deepcopy
from itertools import chain
from typing import Iterator, Union

from topogen.common.circuit import *

GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "vb" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "vb" / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


class VoltageBiasManager:
    """For voltage bias subcircuit, all transistors in the VB has the same type (NMOS, PMOS)"""

    def __init__(self):
        """Build and cache every one-/two-transistor NMOS and PMOS voltage bias."""
        self.initializeOneTransistorVoltageBiasesNmos()
        self.initializeOneTransistorVoltageBiasesPmos()
        self.initializeTwoTransistorVoltageBiasesNmos()
        self.initializeTwoTransistorVoltageBiasesPmos()

    def getAllVoltageBiasesPmos(self) -> Iterator[VoltageBias]:
        """Return every cached PMOS voltage bias (one- and two-transistor variants)."""
        return chain(
            self.oneTransistorVoltageBiasesPmos_, self.twoTransistorVoltageBiasesPmos_
        )

    def getAllVoltageBiasesNmos(self) -> Iterator[VoltageBias]:
        """Return every cached NMOS voltage bias (one- and two-transistor variants)."""
        return chain(
            self.oneTransistorVoltageBiasesNmos_, self.twoTransistorVoltageBiasesNmos_
        )

    def getDiodeTransistorVoltageBiasNmos(self) -> VoltageBias:
        """Return the one-transistor NMOS bias built from a diode transistor, if any."""
        for vb in self.oneTransistorVoltageBiasesNmos_:
            if vb.isSingleDiodeTransistor:
                return vb

    def getDiodeTransistorVoltageBiasPmos(self) -> VoltageBias:
        """Return the one-transistor PMOS bias built from a diode transistor, if any."""
        for vb in self.oneTransistorVoltageBiasesPmos_:
            if vb.isSingleDiodeTransistor:
                return vb

    def getTwoDiodeTransistorVoltageBiasNmos(self) -> VoltageBias:
        """Return the two-transistor NMOS bias built from two diode transistors, if any."""
        for vb in self.getTwoTransistorVoltageBiasesNmos():
            if vb.instances[0].name == "dt" and vb.instances[1].name == "dt":
                return vb

    def getTwoDiodeTransistorVoltageBiasPmos(self) -> VoltageBias:
        """Return the two-transistor PMOS bias built from two diode transistors, if any."""
        for vb in self.getTwoTransistorVoltageBiasesPmos():
            if vb.instances[0].name == "dt" and vb.instances[1].name == "dt":
                return vb

    def getOneTransistorVoltageBiasesPmos(self):
        """Return the cached one-transistor PMOS bias variants (normal, diode)."""
        return self.oneTransistorVoltageBiasesPmos_

    def getTwoTransistorVoltageBiasesPmos(self):
        """Return the cached two-transistor PMOS bias variants (diode+diode, normal+normal, mixed)."""
        return self.twoTransistorVoltageBiasesPmos_

    def getOneTransistorVoltageBiasesNmos(self):
        """Return the cached one-transistor NMOS bias variants (normal, diode)."""
        return self.oneTransistorVoltageBiasesNmos_

    def getTwoTransistorVoltageBiasesNmos(self):
        """Return the cached two-transistor NMOS bias variants (diode+diode, normal+normal, mixed)."""
        return self.twoTransistorVoltageBiasesNmos_

    def initializeOneTransistorVoltageBiasesPmos(self) -> None:
        """Build the one-transistor PMOS bias variants and cache them on ``self``."""
        normalTransistorPmos = NormalTransistor(techtype="p")
        diodeTransistorPmos = DiodeTransistor(techtype="p")
        # materialise to a list — the ``chain`` iterator is otherwise exhausted
        # after the first consumer, leaving every later caller with 0 PMOS
        # voltage biases (the NMOS path already wraps in list()); this asymmetry
        # corrupted every load factory that mirrors a PMOS voltage bias (issue #3).
        self.oneTransistorVoltageBiasesPmos_ = list(
            self.createOneTransistorVoltageBiases(
                normalTransistorPmos, diodeTransistorPmos
            )
        )

    def initializeTwoTransistorVoltageBiasesPmos(self) -> None:
        """Build the two-transistor PMOS bias variants and cache them on ``self``."""
        normalTransistorPmos = NormalTransistor(techtype="p")
        diodeTransistorPmos = DiodeTransistor(techtype="p")
        self.twoTransistorVoltageBiasesPmos_ = list(
            self.createTwoTransistorVoltageBiases(
                normalTransistorPmos, diodeTransistorPmos
            )
        )

    def initializeOneTransistorVoltageBiasesNmos(self) -> None:
        """Build the one-transistor NMOS bias variants and cache them on ``self``."""
        normalTransistorNmos = NormalTransistor(techtype="n")
        diodeTransistorNmos = DiodeTransistor(techtype="n")
        self.oneTransistorVoltageBiasesNmos_ = list(
            self.createOneTransistorVoltageBiases(
                normalTransistorNmos, diodeTransistorNmos
            )
        )

    def initializeTwoTransistorVoltageBiasesNmos(self) -> None:
        """Build the two-transistor NMOS bias variants and cache them on ``self``."""
        normalTransistorNmos = NormalTransistor(techtype="n")
        diodeTransistorNmos = DiodeTransistor(techtype="n")
        self.twoTransistorVoltageBiasesNmos_ = list(
            self.createTwoTransistorVoltageBiases(
                normalTransistorNmos, diodeTransistorNmos
            )
        )

    def createOneTransistorVoltageBiases(
        self, normalTransistor: NormalTransistor, diodeTransistor: DiodeTransistor
    ) -> Iterator[VoltageBias]:
        """Return the normal-transistor and diode-transistor one-transistor bias circuits."""
        firstOneTransistorVoltageBias = self.createOneTransistorCircuit(
            normalTransistor
        )
        secondOneTransistorVoltageBias = self.createOneTransistorCircuit(
            diodeTransistor
        )
        return chain([firstOneTransistorVoltageBias, secondOneTransistorVoltageBias])

    def createTwoTransistorVoltageBiases(
        self, normalTransistor: NormalTransistor, diodeTransistor: DiodeTransistor
    ) -> Iterator[VoltageBias]:
        """Build the three two-transistor bias stacks: diode+diode, normal+normal,
        and mixed normal+diode."""
        diodeTransistor1 = deepcopy(diodeTransistor)
        diodeTransistor2 = deepcopy(diodeTransistor)

        diodeTransistor1.id = 1
        diodeTransistor2.id = 1

        normalTransistor1 = deepcopy(normalTransistor)
        normalTransistor2 = deepcopy(normalTransistor)
        normalTransistor1.id = 1
        normalTransistor2.id = 2
        twoDiodeTransistorCircuit = self.createTwoTransistorCircuit(
            diodeTransistor1, diodeTransistor2
        )
        twoNormalTransistorCircuit = self.createTwoTransistorCircuit(
            normalTransistor1, normalTransistor2
        )
        mixedCircuits = self.createTwoTransistorCircuit(
            normalTransistor, diodeTransistor
        )
        return chain(
            [twoDiodeTransistorCircuit, twoNormalTransistorCircuit, mixedCircuits]
        )

    def createOneTransistorCircuit(self, instance: Circuit) -> VoltageBias:
        """Wrap a single transistor in a one-transistor :class:`VoltageBias`
        (``IN``/``SOURCE``/``OUT`` ports tied to drain/source/gate)."""
        vb = VoltageBias(id=1, techtype=instance.tech)
        vb.ports = [VoltageBias.IN, VoltageBias.SOURCE, VoltageBias.OUT]
        vb.add_instance(instance)
        vb = self.connectInstanceTerminalsOneTransistorVoltageBias(vb, instance)
        return vb

    def createTwoTransistorCircuit(
        self, sourceTransistor: Circuit, outputTransistor: Circuit
    ) -> Union[VoltageBias, None]:
        """Stack *sourceTransistor* under *outputTransistor* into a
        two-transistor :class:`VoltageBias`, or ``None`` if neither transistor
        is a recognised diode ("dt")/normal ("nt") combination.

        The port set differs by case: diode output transistors expose
        ``OUTSOURCE``/``OUTINPUT``; normal-source transistors expose a plain
        ``OUTINPUT`` only (see :meth:`connectInstanceTerminalsTwoTransistorVoltageBias`).
        """
        if outputTransistor.name == "dt":
            vb = VoltageBias(id=1, techtype=sourceTransistor.tech)
            vb.ports = [
                VoltageBias.IN,
                VoltageBias.SOURCE,
                VoltageBias.INNER,
                VoltageBias.OUTSOURCE,
                VoltageBias.OUTINPUT,
            ]
            vb.add_instance(sourceTransistor)
            vb.add_instance(outputTransistor)
            vb = self.connectInstanceTerminalsTwoTransistorVoltageBias(
                vb, sourceTransistor, outputTransistor
            )
            return vb
        if sourceTransistor.name == "nt":
            vb = VoltageBias(id=1, techtype=sourceTransistor.tech)
            vb.ports = [
                VoltageBias.IN,
                VoltageBias.SOURCE,
                VoltageBias.INNER,
                VoltageBias.OUTINPUT,
            ]
            vb.add_instance(sourceTransistor)
            vb.add_instance(outputTransistor)
            vb = self.connectInstanceTerminalsTwoTransistorVoltageBias(
                vb, sourceTransistor, outputTransistor
            )
            return vb
        return None

    def connectInstanceTerminalsOneTransistorVoltageBias(
        self, vb: VoltageBias, transistor: Circuit
    ) -> VoltageBias:
        """Wire *transistor*'s gate/drain/source to *vb*'s ``OUT``/``IN``/``SOURCE``."""
        connect((vb, VoltageBias.OUT), (transistor, "gate"))
        connect((vb, VoltageBias.IN), (transistor, "drain"))
        connect((vb, VoltageBias.SOURCE), (transistor, "source"))
        return vb

    def connectInstanceTerminalsTwoTransistorVoltageBias(
        self, vb: VoltageBias, sourceTransistor: Circuit, outputTransistor: Circuit
    ) -> VoltageBias:
        """Wire both stacked transistors' pins to *vb*'s ports.

        *sourceTransistor*'s gate connects to ``OUTSOURCE`` if present,
        otherwise to ``IN``; its drain/source connect to ``INNER``/``SOURCE``.
        *outputTransistor*'s gate/drain/source connect to ``OUTINPUT``/``IN``/
        ``INNER``.
        """
        if VoltageBias.OUTSOURCE in vb.ports:
            connect((vb, VoltageBias.OUTSOURCE), (sourceTransistor, "gate"))
        else:
            connect((vb, VoltageBias.IN), (sourceTransistor, "gate"))

        connect((vb, VoltageBias.INNER), (sourceTransistor, "drain"))
        connect((vb, VoltageBias.SOURCE), (sourceTransistor, "source"))

        connect((vb, VoltageBias.OUTINPUT), (outputTransistor, "gate"))
        connect((vb, VoltageBias.IN), (outputTransistor, "drain"))
        connect((vb, VoltageBias.INNER), (outputTransistor, "source"))
        return vb


if __name__ == "__main__":
    vb_mng = VoltageBiasManager()
    all_vb = list(vb_mng.getAllVoltageBiasesNmos()) + list(
        vb_mng.getAllVoltageBiasesPmos()
    )

    case_id = 0
    for circuit_id, circuit in enumerate(all_vb):
        print(circuit)
        save_graphviz_figure(
            circuit, filename=GALLERY_DOT_DIR / f"vb_{case_id}_{circuit_id}.dot"
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR / f"vb_{case_id}_{circuit_id}.dot",
            GALLERY_IMAGE_DIR / f"vb_{case_id}_{circuit_id}.png",
        )
