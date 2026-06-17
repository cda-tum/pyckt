"""Cross-coupled pair (CCP) factory at HL2.

A cross-coupled pair is a positive-feedback two-transistor cell where the
gate of each transistor is wired to the *opposite* drain.  The cell is the
foundational block for negative resistance, latch-style comparators, and
gain enhancement in differential loads.
"""
from topogen.common.circuit import *

GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "ccp" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "ccp" / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


class CrossCoupledPair(Circuit):
    """Two transistors with their gates cross-wired to the opposite drains.

    Ports
    -----
    OUTPUT1 : drain of T1, also gate of T2
    OUTPUT2 : drain of T2, also gate of T1
    SOURCE  : common source of both transistors
    """

    OUTPUT1 = "out1"
    OUTPUT2 = "out2"
    SOURCE = "source"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "ccp"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class CrossCoupledPairFactory:
    """Build the NMOS and PMOS variants of a cross-coupled pair."""

    def __init__(self):
        self.crossCoupledPairNmos_ = self._createCrossCoupledPair("n", id_=1)
        self.crossCoupledPairPmos_ = self._createCrossCoupledPair("p", id_=2)

    def getAllCrossCoupledPairs(self) -> list[CrossCoupledPair]:
        return [self.crossCoupledPairNmos_, self.crossCoupledPairPmos_]

    def getCrossCoupledPairNmos(self) -> CrossCoupledPair:
        return self.crossCoupledPairNmos_

    def getCrossCoupledPairPmos(self) -> CrossCoupledPair:
        return self.crossCoupledPairPmos_

    def _createCrossCoupledPair(self, techtype: str, id_: int) -> CrossCoupledPair:
        ccp = CrossCoupledPair(id=id_, techtype=techtype)
        ccp.ports = [
            CrossCoupledPair.OUTPUT1,
            CrossCoupledPair.OUTPUT2,
            CrossCoupledPair.SOURCE,
        ]
        t1 = NormalTransistor(techtype=techtype)
        t2 = NormalTransistor(techtype=techtype)
        t2.id = 2
        ccp.add_instance(t1)
        ccp.add_instance(t2)

        # T1: drain → OUTPUT1, gate → OUTPUT2 (cross), source → SOURCE
        ccp.add_connection_xxx(port=CrossCoupledPair.OUTPUT1, instance_id=0, instance_port="drain")
        ccp.add_connection_xxx(port=CrossCoupledPair.OUTPUT2, instance_id=0, instance_port="gate")
        ccp.add_connection_xxx(port=CrossCoupledPair.SOURCE, instance_id=0, instance_port="source")

        # T2: drain → OUTPUT2, gate → OUTPUT1 (cross), source → SOURCE
        ccp.add_connection_xxx(port=CrossCoupledPair.OUTPUT2, instance_id=1, instance_port="drain")
        ccp.add_connection_xxx(port=CrossCoupledPair.OUTPUT1, instance_id=1, instance_port="gate")
        ccp.add_connection_xxx(port=CrossCoupledPair.SOURCE, instance_id=1, instance_port="source")
        return ccp


if __name__ == "__main__":  # pragma: no cover
    factory = CrossCoupledPairFactory()
    for circuit_id, circuit in enumerate(factory.getAllCrossCoupledPairs()):
        print(circuit)
        save_graphviz_figure(
            circuit, filename=GALLERY_DOT_DIR / f"ccp_{circuit_id}.dot"
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR / f"ccp_{circuit_id}.dot",
            GALLERY_IMAGE_DIR / f"ccp_{circuit_id}.png",
        )
