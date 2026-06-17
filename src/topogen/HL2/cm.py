"""Current mirror factory at HL2.

A current mirror copies a reference current from an input branch (a
diode-connected transistor) to one or more output branches (normal
transistors with their gates tied to the diode's drain/gate).

Distinct from :class:`~topogen.HL2.cb.CurrentBiasManager`, which builds
*stack* / cascode-style bias networks where the output transistor's source
sits on the source transistor's drain.  In a mirror the two transistors
share a *common source* and a *common gate*; only the drains differ.
"""
from topogen.common.circuit import *

GALLERY_DOT_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "cm" / "dots"
)
GALLERY_DOT_DIR.mkdir(parents=True, exist_ok=True)

GALLERY_IMAGE_DIR = (
    Path(__file__).parent.parent.parent.parent / "gallery" / "HL2" / "cm" / "images"
)
GALLERY_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


class CurrentMirror(Circuit):
    """Two same-type transistors with shared gate and shared source.

    Ports
    -----
    INPUT  : reference branch — diode drain *and* both gates
    OUTPUT : mirrored branch — drain of the normal transistor
    SOURCE : common source of both transistors
    """

    INPUT = "input"
    OUTPUT = "output"
    SOURCE = "source"

    def __init__(self, *args, **kwargs):
        kwargs["name"] = "cm"
        if "id" not in kwargs:
            kwargs["id"] = 1
        super().__init__(*args, **kwargs)


class CurrentMirrorFactory:
    """Build the NMOS and PMOS variants of a simple two-transistor mirror.

    `CurrentBiasManager` already enumerates cascode-style bias networks (where
    the second transistor's *source* sits on the first transistor's *drain*),
    so it does not produce a true mirror.  This factory implements the
    diode-+-normal mirror topology directly, matching the
    ``MosfetSimpleCurrentMirror`` rule used by the recogniser.
    """

    def __init__(self):
        self.currentMirrorNmos_ = self._createSimpleMirror("n", id_=1)
        self.currentMirrorPmos_ = self._createSimpleMirror("p", id_=2)

    def getAllCurrentMirrors(self) -> list[CurrentMirror]:
        return [self.currentMirrorNmos_, self.currentMirrorPmos_]

    def getCurrentMirrorNmos(self) -> CurrentMirror:
        return self.currentMirrorNmos_

    def getCurrentMirrorPmos(self) -> CurrentMirror:
        return self.currentMirrorPmos_

    def _createSimpleMirror(self, techtype: str, id_: int) -> CurrentMirror:
        cm = CurrentMirror(id=id_, techtype=techtype)
        cm.ports = [CurrentMirror.INPUT, CurrentMirror.OUTPUT, CurrentMirror.SOURCE]

        diode = DiodeTransistor(techtype=techtype)
        normal = NormalTransistor(techtype=techtype)
        normal.id = 2
        cm.add_instance(diode)
        cm.add_instance(normal)

        # Diode (reference): drain & gate → INPUT, source → SOURCE
        cm.add_connection_xxx(port=CurrentMirror.INPUT, instance_id=0, instance_port="drain")
        cm.add_connection_xxx(port=CurrentMirror.INPUT, instance_id=0, instance_port="gate")
        cm.add_connection_xxx(port=CurrentMirror.SOURCE, instance_id=0, instance_port="source")

        # Normal (output): drain → OUTPUT, gate → INPUT (shared with diode), source → SOURCE
        cm.add_connection_xxx(port=CurrentMirror.OUTPUT, instance_id=1, instance_port="drain")
        cm.add_connection_xxx(port=CurrentMirror.INPUT, instance_id=1, instance_port="gate")
        cm.add_connection_xxx(port=CurrentMirror.SOURCE, instance_id=1, instance_port="source")
        return cm


if __name__ == "__main__":  # pragma: no cover
    factory = CurrentMirrorFactory()
    for circuit_id, circuit in enumerate(factory.getAllCurrentMirrors()):
        print(circuit)
        save_graphviz_figure(
            circuit, filename=GALLERY_DOT_DIR / f"cm_{circuit_id}.dot"
        )
        convert_dot_to_png(
            GALLERY_DOT_DIR / f"cm_{circuit_id}.dot",
            GALLERY_IMAGE_DIR / f"cm_{circuit_id}.png",
        )
