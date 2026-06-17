"""Structure-net connectivity index for partitioning.

pyckt's recogniser wires each structure pin to its own :class:`StructureNet`
instance but does **not** maintain a global net registry — a freshly recognised
:class:`~recognition.model.StructureCircuits` reports ``0 nets``.  acst's
partitioner, by contrast, navigates almost entirely through shared nets
(``StructureNet::getAllConnectedStructures``,
``StructureNet::findConnectedStructures(StructurePinType)``).

This module rebuilds that connectivity as a post-recognition index keyed by the
electrical net name (the underlying core-net name shared by every pin on the
node), so the acst-faithful partitioner (stage 3+) can ask the same questions
acst's C++ does.  It is read-only and does not modify the recognition result.

C++ ref: ``StructRec::StructureNet`` connectivity queries.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from recognition.model import Structure, StructureCircuits, StructureNet


@dataclass(frozen=True)
class NetConnection:
    """One ``(structure, pin)`` attachment to an electrical net."""

    structure: "Structure"
    pin_name: str


class StructureNetIndex:
    """Global net → connected-structures index over a recognition result.

    Built once via :meth:`build`, then queried by the partitioner.  Every
    structure at every hierarchy level contributes its connected pins, so a
    single net exposes both its array-level and pair-level attachments — exactly
    as acst's shared nets do.
    """

    def __init__(self) -> None:
        self._by_net: dict[str, list[NetConnection]] = defaultdict(list)
        # A representative StructureNet per name, used for supply queries.
        self._repr: dict[str, "StructureNet"] = {}

    # ── construction ──────────────────────────────────────────────────

    @classmethod
    def build(cls, result: "StructureCircuits") -> "StructureNetIndex":
        """Index every connected pin of every structure in *result*."""
        index = cls()
        for level in result.hierarchy_levels:
            for structure in result.get_level(level).structures:
                index._add_structure(structure)
        return index

    def _add_structure(self, structure: "Structure") -> None:
        for pin_name, pin in structure.pins.items():
            if not pin.is_connected:
                continue
            net = pin.net
            self._by_net[net.name].append(NetConnection(structure, pin_name))
            self._repr.setdefault(net.name, net)

    # ── connectivity queries (mirror acst StructureNet) ───────────────

    def connected_structures(self, net_name: str) -> list["Structure"]:
        """All distinct structures with any pin on *net_name*.

        Mirrors ``StructureNet::getAllConnectedStructures``.
        """
        seen: set[int] = set()
        out: list[Structure] = []
        for conn in self._by_net.get(net_name, ()):
            if id(conn.structure) not in seen:
                seen.add(id(conn.structure))
                out.append(conn.structure)
        return out

    def connected_via(
        self, net_name: str, structure_name: str, pin_name: str
    ) -> list["Structure"]:
        """Structures named *structure_name* attached to *net_name* via *pin_name*.

        Mirrors ``StructureNet::findConnectedStructures(StructurePinType)``.
        """
        seen: set[int] = set()
        out: list[Structure] = []
        for conn in self._by_net.get(net_name, ()):
            if (
                conn.pin_name == pin_name
                and conn.structure.name == structure_name
                and id(conn.structure) not in seen
            ):
                seen.add(id(conn.structure))
                out.append(conn.structure)
        return out

    def connections(self, net_name: str) -> list[NetConnection]:
        """Raw ``(structure, pin)`` attachments on *net_name*."""
        return list(self._by_net.get(net_name, ()))

    def net_name(self, structure: "Structure", pin_name: str) -> str | None:
        """Net name on *structure*'s *pin_name*, or ``None`` if absent/unwired.

        Mirrors ``Structure::findNet(StructurePinType)`` (by name).
        """
        if not structure.has_pin(pin_name):
            return None
        pin = structure.get_pin(pin_name)
        return pin.net.name if pin.is_connected else None

    # ── supply queries ────────────────────────────────────────────────

    def is_supply(self, net_name: str) -> bool:
        net = self._repr.get(net_name)
        return net.is_supply() if net is not None else False

    def is_vdd(self, net_name: str) -> bool:
        net = self._repr.get(net_name)
        return net.is_vdd() if net is not None else False

    def is_ground(self, net_name: str) -> bool:
        net = self._repr.get(net_name)
        return net.is_ground() if net is not None else False

    # ── introspection ─────────────────────────────────────────────────

    @property
    def net_names(self) -> list[str]:
        return list(self._by_net)

    def __len__(self) -> int:
        return len(self._by_net)

    def __repr__(self) -> str:
        return f"StructureNetIndex({len(self._by_net)} nets)"
