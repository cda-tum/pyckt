from copy import deepcopy
from itertools import chain
from typing import Iterator

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
        """Build the four two-transistor bias stacks (acst
        ``createTwoTransistorVoltageBiases``): diode+diode, normal+normal, and
        *two* mixed normal+diode variants — one exposing the source gate on
        ``OUTSOURCE``, one tying it to the output node (``IN``)."""
        diodeTransistor1 = deepcopy(diodeTransistor)
        diodeTransistor2 = deepcopy(diodeTransistor)

        diodeTransistor1.id = 1
        diodeTransistor2.id = 1

        normalTransistor1 = deepcopy(normalTransistor)
        normalTransistor2 = deepcopy(normalTransistor)
        normalTransistor1.id = 1
        normalTransistor2.id = 2
        twoDiodeTransistorCircuits = self.createTwoTransistorCircuit(
            diodeTransistor1, diodeTransistor2
        )
        twoNormalTransistorCircuits = self.createTwoTransistorCircuit(
            normalTransistor1, normalTransistor2
        )
        mixedCircuits = self.createTwoTransistorCircuit(
            normalTransistor, diodeTransistor
        )
        return chain(
            twoDiodeTransistorCircuits, twoNormalTransistorCircuits, mixedCircuits
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
    ) -> list:
        """Stack *sourceTransistor* under *outputTransistor* into two-transistor
        :class:`VoltageBias` circuits, one per matching acst
        ``createTwoTransistorCircuit`` branch.

        acst runs *both* branches, so a mixed normal+diode pair yields **two**
        variants: one exposing the source gate on its own ``OUTSOURCE`` net
        (diode-output branch), one tying the source gate to the output node
        ``IN`` (normal-source branch — the gate-connected-cascode used by e.g.
        the symmetrical op-amp's four-transistor loads).  A diode+diode pair
        yields only the former, a normal+normal pair only the latter.
        """
        out = []
        if outputTransistor.name == "dt":
            vb = VoltageBias(id=1, techtype=sourceTransistor.tech)
            vb.ports = [
                VoltageBias.IN,
                VoltageBias.SOURCE,
                VoltageBias.INNER,
                VoltageBias.OUTSOURCE,
                VoltageBias.OUTINPUT,
            ]
            src, outp = deepcopy(sourceTransistor), deepcopy(outputTransistor)
            vb.add_instance(src)
            vb.add_instance(outp)
            out.append(
                self.connectInstanceTerminalsTwoTransistorVoltageBias(
                    vb, src, outp, outsource_aliases_in=False
                )
            )
        if sourceTransistor.name == "nt":
            vb = VoltageBias(id=1, techtype=sourceTransistor.tech)
            vb.ports = [
                VoltageBias.IN,
                VoltageBias.SOURCE,
                VoltageBias.INNER,
                VoltageBias.OUTSOURCE,
                VoltageBias.OUTINPUT,
            ]
            src, outp = deepcopy(sourceTransistor), deepcopy(outputTransistor)
            vb.add_instance(src)
            vb.add_instance(outp)
            out.append(
                self.connectInstanceTerminalsTwoTransistorVoltageBias(
                    vb, src, outp, outsource_aliases_in=True
                )
            )
        return out

    def connectInstanceTerminalsOneTransistorVoltageBias(
        self, vb: VoltageBias, transistor: Circuit
    ) -> VoltageBias:
        """Wire *transistor*'s gate/drain/source to *vb*'s ``OUT``/``IN``/``SOURCE``."""
        connect((vb, VoltageBias.OUT), (transistor, "gate"))
        connect((vb, VoltageBias.IN), (transistor, "drain"))
        connect((vb, VoltageBias.SOURCE), (transistor, "source"))
        return vb

    def connectInstanceTerminalsTwoTransistorVoltageBias(
        self,
        vb: VoltageBias,
        sourceTransistor: Circuit,
        outputTransistor: Circuit,
        outsource_aliases_in: bool = False,
    ) -> VoltageBias:
        """Wire both stacked transistors' pins to *vb*'s ports.

        *sourceTransistor*'s gate connects to its own ``OUTSOURCE`` node, or —
        when *outsource_aliases_in* (acst's no-``OUTSOURCE``-net branch) — to
        the output node ``IN`` with ``OUTSOURCE`` exposed as an alias of it;
        its drain/source connect to ``INNER``/``SOURCE``.  *outputTransistor*'s
        gate/drain/source connect to ``OUTINPUT``/``IN``/``INNER``.
        """
        if outsource_aliases_in:
            connect((vb, VoltageBias.IN), (sourceTransistor, "gate"))
            connect((vb, VoltageBias.OUTSOURCE), (sourceTransistor, "gate"))
        else:
            connect((vb, VoltageBias.OUTSOURCE), (sourceTransistor, "gate"))

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
