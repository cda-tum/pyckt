"""Structure Recognition Model — runtime circuit overlay.

After the recognition engine matches library templates against a flat
transistor netlist, the results are stored in this hierarchical model.
The model overlays the original :class:`~core.Circuit` with
recognised analog structures (arrays, pairs, compound pairs) organised
by hierarchy level.

Key classes
-----------
- :class:`StructurePin` — a pin on a recognised structure, linked to a
  :class:`StructureNet`.
- :class:`StructureNet` — an electrical node in the structure-level
  view, backed by a :class:`~core.Net`.
- :class:`Structure` — abstract base for a recognised analog structure.
- :class:`ArrayStructure` — leaf structure wrapping grouped devices.
- :class:`PairStructure` — binary node combining two child structures.
- :class:`StructureCircuit` — single-level container of structures and
  nets.
- :class:`StructureCircuits` — top-level container holding all levels.

C++ reference
    ``StructRec/incl/StructureCircuit/Structure/Structure.h``
    ``StructRec/incl/StructureCircuit/Structure/Pair.h``
    ``StructRec/incl/StructureCircuit/Structure/Array.h``
    ``StructRec/incl/StructureCircuit/StructureCircuit.h``
    ``StructRec/incl/Results/StructureCircuits.h``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator, Sequence

from core.device import TechType
from core.net import Net, Supply

if TYPE_CHECKING:
    from core.circuit import Circuit
    from core.device import Device


# ═══════════════════════════════════════════════════════════════════════
#  Identifiers
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StructureId:
    """Unique identifier for a :class:`Structure`.

    Composed of the library template name and a sequential index that
    distinguishes multiple instances of the same template within a
    single circuit.

    Attributes
    ----------
    name : str
        Library item name (e.g. ``"MosfetSimpleCurrentMirror"``).
    index : int
        Instance index (0-based).
    """

    name: str
    index: int = 0

    def __str__(self) -> str:
        return f"{self.name}#{self.index}"


# ═══════════════════════════════════════════════════════════════════════
#  StructurePin
# ═══════════════════════════════════════════════════════════════════════

class StructurePin:
    """A pin on a recognised structure, connected to a :class:`StructureNet`.

    Each structure exposes a set of named pins (matching the library
    template).  Every pin is wired to exactly one :class:`StructureNet`.

    Navigation
    ----------
    ``pin.net``         → the :class:`StructureNet` this pin is on
    ``pin.structure``   → the :class:`Structure` that owns this pin

    C++ reference: ``StructRec::StructurePin``
    """

    __slots__ = ("_name", "_net", "_structure")

    def __init__(
        self,
        name: str,
        net: StructureNet | None = None,
        structure: Structure | None = None,
    ) -> None:
        self._name = name
        self._net: StructureNet | None = net
        self._structure: Structure | None = structure

    # ── Properties ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Pin name (e.g. ``"Drain"``, ``"Source"``, ``"Output"``)."""
        return self._name

    @property
    def net(self) -> StructureNet:
        """The :class:`StructureNet` this pin is connected to.

        Raises
        ------
        RuntimeError
            If the pin has not been wired to a net yet.
        """
        if self._net is None:
            raise RuntimeError(f"Pin {self._name!r} is not connected to a net")
        return self._net

    @net.setter
    def net(self, value: StructureNet) -> None:
        self._net = value

    @property
    def structure(self) -> Structure:
        """The :class:`Structure` that owns this pin.

        Raises
        ------
        RuntimeError
            If the owning structure has not been set.
        """
        if self._structure is None:
            raise RuntimeError(f"Pin {self._name!r} has no owning structure")
        return self._structure

    @structure.setter
    def structure(self, value: Structure) -> None:
        self._structure = value

    @property
    def is_connected(self) -> bool:
        """``True`` if this pin has been wired to a net."""
        return self._net is not None

    # ── Dunder ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        owner = self._structure.structure_id.name if self._structure else "?"
        net = self._net.name if self._net else "?"
        return f"StructurePin({owner}.{self._name} → {net})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StructurePin):
            return NotImplemented
        return (
            self._name == other._name
            and self._structure is other._structure
        )

    def __hash__(self) -> int:
        return hash((self._name, id(self._structure)))


# ═══════════════════════════════════════════════════════════════════════
#  StructureNet
# ═══════════════════════════════════════════════════════════════════════

class StructureNet:
    """An electrical node in the structure-level view.

    A :class:`StructureNet` is the structure-circuit analogue of a
    :class:`~core.Net`.  It wraps (optionally) a core net and
    collects all :class:`StructurePin` objects wired to it.

    Key queries
    -----------
    ``net.is_supply()``         → delegates to the underlying core net
    ``net.connected_structures`` → all structures with a pin on this net
    ``net.find_pins(pin_type)`` → filter pins by structure-pin type

    C++ reference: ``StructRec::StructureNet``
    """

    __slots__ = ("_name", "_core_net", "_supply", "_pins")

    def __init__(
        self,
        name: str,
        core_net: Net | None = None,
        supply: Supply | None = None,
    ) -> None:
        self._name = name
        self._core_net = core_net
        self._supply = supply or (core_net.supply if core_net else Supply.no_supply())
        self._pins: list[StructurePin] = []

    # ── Properties ───────────────────────────────────────────────────

    @property
    def name(self) -> str:
        """Net name (usually inherited from the core net)."""
        return self._name

    @property
    def core_net(self) -> Net | None:
        """The underlying :class:`~core.Net`, or ``None`` if
        this structure net is synthetic (no core counterpart)."""
        return self._core_net

    @property
    def supply(self) -> Supply:
        """Supply annotation (VDD / GND / none)."""
        return self._supply

    @supply.setter
    def supply(self, value: Supply) -> None:
        self._supply = value

    @property
    def pins(self) -> list[StructurePin]:
        """All structure pins wired to this net (read-only copy)."""
        return list(self._pins)

    # ── Supply queries ───────────────────────────────────────────────

    def is_supply(self) -> bool:
        """``True`` if this net is a supply rail (VDD or GND).

        Delegates to the core net when available; otherwise uses the
        locally stored :attr:`supply` annotation.
        """
        if self._core_net is not None:
            return self._core_net.is_supply()
        return self._supply.is_supply

    def is_vdd(self) -> bool:
        """``True`` if this net is a VDD supply."""
        if self._core_net is not None:
            return self._core_net.is_vdd()
        return self._supply.is_vdd

    def is_ground(self) -> bool:
        """``True`` if this net is a ground rail."""
        if self._core_net is not None:
            return self._core_net.is_ground()
        return self._supply.is_gnd

    # ── Pin management ───────────────────────────────────────────────

    def add_pin(self, pin: StructurePin) -> None:
        """Wire a :class:`StructurePin` to this net."""
        self._pins.append(pin)
        pin.net = self

    def remove_pin(self, pin: StructurePin) -> None:
        """Disconnect a :class:`StructurePin` from this net."""
        self._pins.remove(pin)

    # ── Queries ──────────────────────────────────────────────────────

    @property
    def connected_structures(self) -> list[Structure]:
        """All distinct structures that have at least one pin on this net."""
        seen: set[int] = set()
        result: list[Structure] = []
        for pin in self._pins:
            sid = id(pin._structure)
            if sid not in seen:
                seen.add(sid)
                if pin._structure is not None:
                    result.append(pin._structure)
        return result

    def find_pins_by_type(
        self, structure_name: str, pin_name: str | None = None
    ) -> list[StructurePin]:
        """Return pins matching a structure name (and optionally pin name).

        Parameters
        ----------
        structure_name : str
            Filter by owning structure's template name.
        pin_name : str, optional
            Additionally filter by pin name.
        """
        result: list[StructurePin] = []
        for pin in self._pins:
            if pin._structure is None:
                continue
            if pin._structure.structure_id.name != structure_name:
                continue
            if pin_name is not None and pin._name != pin_name:
                continue
            result.append(pin)
        return result

    @property
    def is_connected(self) -> bool:
        """``True`` if at least one pin is wired to this net."""
        return len(self._pins) > 0

    # ── Dunder ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        supply_tag = ""
        if self.is_supply():
            supply_tag = " [VDD]" if self.is_vdd() else " [GND]"
        return f"StructureNet({self._name!r}, {len(self._pins)} pins{supply_tag})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StructureNet):
            return NotImplemented
        return self._name == other._name

    def __hash__(self) -> int:
        return hash(self._name)


# ═══════════════════════════════════════════════════════════════════════
#  Structure (abstract base)
# ═══════════════════════════════════════════════════════════════════════

_PERSISTENCE_MAX: int = -1
"""Sentinel for *never pruned* — mirrors C++ ``MAX_PERSISTENCE_``."""


class Structure:
    """Abstract base class for a recognised analog structure.

    A :class:`Structure` represents one recognised pattern instance in the
    circuit — e.g. one specific current mirror built from two specific
    transistor arrays.  Every structure has:

    * A :class:`StructureId` (template name + instance index).
    * A :class:`~core.TechType` (inferred from children).
    * Named :class:`StructurePin` objects connected to
      :class:`StructureNet` objects.
    * An optional persistence value controlling how long the structure
      survives pruning passes.
    * Zero or more parent structures at higher hierarchy levels.

    Two concrete subclasses exist:

    * :class:`ArrayStructure` — leaf node wrapping one or more devices.
    * :class:`PairStructure` — binary node combining two child
      structures.

    C++ reference: ``StructRec::Structure`` (abstract), ``StructRec::Array``,
    ``StructRec::Pair``
    """

    def __init__(
        self,
        structure_id: StructureId,
        tech_type: TechType = TechType.UNDEFINED,
        persistence: int = _PERSISTENCE_MAX,
    ) -> None:
        self._structure_id = structure_id
        self._tech_type = tech_type
        self._persistence = persistence
        self._pins: dict[str, StructurePin] = {}
        self._parents: list[Structure] = []

    # ── Identity ─────────────────────────────────────────────────────

    @property
    def structure_id(self) -> StructureId:
        """Unique identifier (template name + instance index)."""
        return self._structure_id

    @property
    def name(self) -> str:
        """Shorthand for the library template name."""
        return self._structure_id.name

    @property
    def tech_type(self) -> TechType:
        """Technology type (N / P / UNDEFINED)."""
        return self._tech_type

    @tech_type.setter
    def tech_type(self, value: TechType) -> None:
        self._tech_type = value

    @property
    def persistence(self) -> int:
        """Persistence value.  ``-1`` means *never pruned*."""
        return self._persistence

    @persistence.setter
    def persistence(self, value: int) -> None:
        self._persistence = value

    @property
    def has_max_persistence(self) -> bool:
        """``True`` if persistence is the sentinel *never-pruned* value."""
        return self._persistence == _PERSISTENCE_MAX

    # ── Pins ─────────────────────────────────────────────────────────

    def add_pin(self, pin: StructurePin) -> None:
        """Register a named pin on this structure.

        Also back-links the pin to this structure.
        """
        pin.structure = self
        self._pins[pin.name] = pin

    def get_pin(self, name: str) -> StructurePin:
        """Look up a pin by name.

        Raises
        ------
        KeyError
            If no pin with *name* exists on this structure.
        """
        try:
            return self._pins[name]
        except KeyError:
            raise KeyError(
                f"{self._structure_id}: no pin named {name!r}; "
                f"available: {list(self._pins)}"
            ) from None

    def has_pin(self, name: str) -> bool:
        """``True`` if a pin named *name* exists."""
        return name in self._pins

    @property
    def pins(self) -> dict[str, StructurePin]:
        """All pins on this structure (name → StructurePin)."""
        return dict(self._pins)

    @property
    def pin_names(self) -> list[str]:
        """Sorted list of pin names."""
        return sorted(self._pins)

    def find_net(self, pin_name: str) -> StructureNet:
        """Shorthand: ``structure.find_net("Source")`` ≡
        ``structure.get_pin("Source").net``."""
        return self.get_pin(pin_name).net

    # ── Parent hierarchy ─────────────────────────────────────────────

    def add_parent(self, parent: Structure) -> None:
        """Register *parent* as a higher-level structure containing this one."""
        self._parents.append(parent)

    def remove_parent(self, parent: Structure) -> None:
        """Un-register a parent structure."""
        self._parents.remove(parent)

    @property
    def parents(self) -> list[Structure]:
        """Direct parent structures (read-only copy)."""
        return list(self._parents)

    @property
    def has_parent(self) -> bool:
        """``True`` if at least one parent exists."""
        return len(self._parents) > 0

    @property
    def has_exactly_one_parent(self) -> bool:
        return len(self._parents) == 1

    @property
    def topmost_parents(self) -> list[Structure]:
        """Walk the parent chain(s) to the highest ancestor(s)."""
        if not self._parents:
            return [self]
        result: list[Structure] = []
        for p in self._parents:
            result.extend(p.topmost_parents)
        return result

    def has_common_parent(self, other: Structure) -> bool:
        """``True`` if *self* and *other* share at least one parent."""
        my_parents = {id(p) for p in self._parents}
        return any(id(p) in my_parents for p in other._parents)

    # ── Abstract interface ───────────────────────────────────────────

    @property
    def is_pair(self) -> bool:
        """``True`` if this is a :class:`PairStructure`."""
        return False

    @property
    def is_array(self) -> bool:
        """``True`` if this is an :class:`ArrayStructure`."""
        return False

    @property
    def devices(self) -> list[Device]:
        """All leaf devices belonging to this structure (recursive)."""
        raise NotImplementedError

    @property
    def array_children(self) -> list[ArrayStructure]:
        """All array-level descendants (recursive)."""
        raise NotImplementedError

    # ── Connectivity helpers ─────────────────────────────────────────

    def is_connected_to_net(self, net_name: str) -> bool:
        """``True`` if any pin on this structure is wired to *net_name*."""
        return any(
            p._net is not None and p._net.name == net_name
            for p in self._pins.values()
        )

    def shares_net_with(self, other: Structure) -> set[str]:
        """Return the set of net names shared between *self* and *other*."""
        my_nets = {
            p._net.name for p in self._pins.values() if p._net is not None
        }
        other_nets = {
            p._net.name for p in other._pins.values() if p._net is not None
        }
        return my_nets & other_nets

    def has_common_devices(self, other: Structure) -> bool:
        """``True`` if *self* and *other* share at least one leaf device."""
        my_devs = {id(d) for d in self.devices}
        return any(id(d) in my_devs for d in other.devices)

    # ── Current-mirror helpers ───────────────────────────────────────

    @property
    def is_current_mirror(self) -> bool:
        """``True`` if this structure's template name contains
        ``"CurrentMirror"``."""
        return "CurrentMirror" in self._structure_id.name

    @property
    def is_part_of_current_mirror(self) -> bool:
        """``True`` if this structure or any ancestor is a current mirror."""
        if self.is_current_mirror:
            return True
        return any(p.is_part_of_current_mirror for p in self._parents)

    # ── Dunder ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        kind = "Pair" if self.is_pair else ("Array" if self.is_array else "?")
        pins = ", ".join(self._pins)
        return f"Structure({self._structure_id}, {kind}, tech={self._tech_type.name}, pins=[{pins}])"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Structure):
            return NotImplemented
        return self._structure_id == other._structure_id

    def __hash__(self) -> int:
        return hash(self._structure_id)

    def __lt__(self, other: Structure) -> bool:
        return str(self._structure_id) < str(other._structure_id)


# ═══════════════════════════════════════════════════════════════════════
#  ArrayStructure (leaf)
# ═══════════════════════════════════════════════════════════════════════

class ArrayStructure(Structure):
    """Leaf structure wrapping one or more grouped devices.

    An :class:`ArrayStructure` is the result of grouping identical
    transistors (or other devices) that share the same net connectivity
    pattern.  For example, three parallel NMOS transistors with tied
    gates form a single ``MosfetNormalArray``.

    C++ reference: ``StructRec::Array``

    Attributes
    ----------
    _devices : list[Device]
        The leaf devices belonging to this array.
    """

    def __init__(
        self,
        structure_id: StructureId,
        tech_type: TechType = TechType.UNDEFINED,
        persistence: int = _PERSISTENCE_MAX,
        device_list: Sequence[Device] | None = None,
    ) -> None:
        super().__init__(structure_id, tech_type, persistence)
        self._devices: list[Device] = list(device_list) if device_list else []

    # ── Device management ────────────────────────────────────────────

    def set_devices(self, devices: Sequence[Device]) -> None:
        """Replace the device list."""
        self._devices = list(devices)

    def add_device(self, device: Device) -> None:
        """Append a device to this array."""
        self._devices.append(device)

    @property
    def first_device(self) -> Device:
        """The first (representative) device in the array.

        Raises
        ------
        IndexError
            If the array is empty.
        """
        return self._devices[0]

    @property
    def device_count(self) -> int:
        """Number of devices in this array."""
        return len(self._devices)

    # ── Structure interface ──────────────────────────────────────────

    @property
    def is_array(self) -> bool:
        return True

    @property
    def devices(self) -> list[Device]:
        return list(self._devices)

    @property
    def array_children(self) -> list[ArrayStructure]:
        return [self]

    # ── Dunder ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        pins = ", ".join(self._pins)
        n = len(self._devices)
        return (
            f"ArrayStructure({self._structure_id}, "
            f"tech={self._tech_type.name}, {n} device(s), pins=[{pins}])"
        )


# ═══════════════════════════════════════════════════════════════════════
#  PairStructure (binary node)
# ═══════════════════════════════════════════════════════════════════════

class PairStructure(Structure):
    """Binary node combining two child structures.

    A :class:`PairStructure` represents a matched pair of sub-structures
    such as a differential pair (two normal arrays with shared sources)
    or a cascode current mirror (two simple current mirrors stacked).

    The two children are called **child1** and **child2**, matching the
    C++ convention.  If the pair is *symmetric*, the children are
    interchangeable.

    C++ reference: ``StructRec::Pair``

    Attributes
    ----------
    _child1 : Structure
        First child structure.
    _child2 : Structure
        Second child structure.
    _symmetric : bool
        Whether the children are interchangeable.
    """

    def __init__(
        self,
        structure_id: StructureId,
        child1: Structure,
        child2: Structure,
        symmetric: bool = False,
        tech_type: TechType = TechType.UNDEFINED,
        persistence: int = _PERSISTENCE_MAX,
    ) -> None:
        super().__init__(structure_id, tech_type, persistence)
        self._child1 = child1
        self._child2 = child2
        self._symmetric = symmetric
        # Back-link children to this parent
        child1.add_parent(self)
        child2.add_parent(self)

    # ── Children ─────────────────────────────────────────────────────

    @property
    def child1(self) -> Structure:
        """First child structure."""
        return self._child1

    @property
    def child2(self) -> Structure:
        """Second child structure."""
        return self._child2

    def get_child(self, number: int) -> Structure:
        """Return child by number (1 or 2).

        Raises
        ------
        ValueError
            If *number* is not 1 or 2.
        """
        if number == 1:
            return self._child1
        if number == 2:
            return self._child2
        raise ValueError(f"Child number must be 1 or 2, got {number}")

    @property
    def children(self) -> tuple[Structure, Structure]:
        """Both children as a tuple ``(child1, child2)``."""
        return (self._child1, self._child2)

    @property
    def symmetric(self) -> bool:
        """``True`` if the children are interchangeable."""
        return self._symmetric

    # ── Structure interface ──────────────────────────────────────────

    @property
    def is_pair(self) -> bool:
        return True

    @property
    def devices(self) -> list[Device]:
        """All leaf devices from both children (recursive)."""
        return self._child1.devices + self._child2.devices

    @property
    def array_children(self) -> list[ArrayStructure]:
        """All array-level descendants from both children (recursive)."""
        return self._child1.array_children + self._child2.array_children

    # ── Child-pin helpers ────────────────────────────────────────────

    def find_child1_pin(self, pin_name: str) -> StructurePin:
        """Look up a pin on child1."""
        return self._child1.get_pin(pin_name)

    def find_child2_pin(self, pin_name: str) -> StructurePin:
        """Look up a pin on child2."""
        return self._child2.get_pin(pin_name)

    # ── Tech-type inference ──────────────────────────────────────────

    def infer_tech_type(self) -> TechType:
        """Infer tech type from children.

        If both children have the same tech type, that type is returned.
        Otherwise returns :attr:`TechType.UNDEFINED`.
        """
        t1 = self._child1.tech_type
        t2 = self._child2.tech_type
        if t1 == t2:
            return t1
        return TechType.UNDEFINED

    # ── Dunder ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        pins = ", ".join(self._pins)
        sym = " symmetric" if self._symmetric else ""
        return (
            f"PairStructure({self._structure_id}, "
            f"tech={self._tech_type.name}{sym}, "
            f"children=[{self._child1.structure_id}, {self._child2.structure_id}], "
            f"pins=[{pins}])"
        )


# ═══════════════════════════════════════════════════════════════════════
#  StructureCircuit (single-level container)
# ═══════════════════════════════════════════════════════════════════════

class StructureCircuit:
    """Container for structures and nets at one hierarchy level.

    Each :class:`StructureCircuit` represents a single level of the
    recognition hierarchy.  Structures and their connecting nets are
    stored here.  A :class:`StructureCircuits` instance holds one
    :class:`StructureCircuit` per active hierarchy level.

    C++ reference: ``StructRec::StructureCircuit``

    See the :attr:`level` property for the hierarchy level this circuit represents.
    """

    def __init__(self, level: int) -> None:
        self._level = level
        self._structures: dict[StructureId, Structure] = {}
        self._nets: dict[str, StructureNet] = {}

    # ── Properties ───────────────────────────────────────────────────

    @property
    def level(self) -> int:
        """Hierarchy level."""
        return self._level

    # ── Structure management ─────────────────────────────────────────

    def add_structure(self, structure: Structure) -> None:
        """Register a structure at this level."""
        self._structures[structure.structure_id] = structure

    def find_structure(self, structure_id: StructureId) -> Structure:
        """Look up a structure by its id.

        Raises
        ------
        KeyError
            If no structure with *structure_id* exists at this level.
        """
        return self._structures[structure_id]

    def has_structure(self, structure_id: StructureId) -> bool:
        return structure_id in self._structures

    def remove_structure(self, structure: Structure) -> None:
        """Remove a structure from this level.

        Raises
        ------
        KeyError
            If the structure is not present.
        """
        del self._structures[structure.structure_id]

    @property
    def structures(self) -> list[Structure]:
        """All structures at this level."""
        return list(self._structures.values())

    def find_structures_by_name(self, name: str) -> list[Structure]:
        """Return all structures whose template name matches *name*."""
        return [s for s in self._structures.values() if s.name == name]

    @property
    def structures_without_parents(self) -> list[Structure]:
        """Structures at this level that have no parent in any
        higher level."""
        return [s for s in self._structures.values() if not s.has_parent]

    # ── Net management ───────────────────────────────────────────────

    def add_net(self, net: StructureNet) -> None:
        """Register a structure net at this level."""
        self._nets[net.name] = net

    def find_net(self, name: str) -> StructureNet:
        """Look up a net by name.

        Raises
        ------
        KeyError
            If no net with *name* exists.
        """
        return self._nets[name]

    def find_or_create_net(
        self, name: str, core_net: Net | None = None
    ) -> StructureNet:
        """Return the named net, creating it if absent."""
        if name not in self._nets:
            self._nets[name] = StructureNet(name, core_net=core_net)
        return self._nets[name]

    def has_net(self, name: str) -> bool:
        return name in self._nets

    def remove_net(self, net: StructureNet) -> None:
        """Remove a net from this level."""
        del self._nets[net.name]

    @property
    def nets(self) -> list[StructureNet]:
        """All nets at this level."""
        return list(self._nets.values())

    # ── Queries ──────────────────────────────────────────────────────

    def find_connected_structures(self, net_name: str) -> list[Structure]:
        """Structures connected to the named net."""
        if net_name not in self._nets:
            return []
        return self._nets[net_name].connected_structures

    @property
    def empty(self) -> bool:
        """``True`` if no structures exist at this level."""
        return len(self._structures) == 0

    @property
    def num_structures(self) -> int:
        return len(self._structures)

    @property
    def num_nets(self) -> int:
        return len(self._nets)

    # ── Dunder ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"StructureCircuit(level={self._level}, "
            f"{self.num_structures} structures, {self.num_nets} nets)"
        )

    def __len__(self) -> int:
        return self.num_structures

    def __contains__(self, structure_id: StructureId) -> bool:
        return structure_id in self._structures

    def __iter__(self) -> Iterator[Structure]:
        return iter(self._structures.values())


# ═══════════════════════════════════════════════════════════════════════
#  StructureCircuits (top-level container)
# ═══════════════════════════════════════════════════════════════════════

class StructureCircuits:
    """Top-level container holding all hierarchy levels.

    This is the main output of the structure recognition engine.
    It wraps the original :class:`~core.Circuit` and overlays it
    with a set of :class:`StructureCircuit` instances, one per
    hierarchy level.

    C++ reference: ``StructRec::StructureCircuits``

    Typical usage after recognition::

        circuits = recognizer.run(circuit, library)
        for s in circuits.all_structures:
            print(s.name, s.tech_type)
        top = circuits.top_level_structures
    """

    def __init__(self, circuit: Circuit | None = None) -> None:
        self._circuit = circuit
        self._levels: dict[int, StructureCircuit] = {}

    # ── Circuit reference ────────────────────────────────────────────

    @property
    def circuit(self) -> Circuit | None:
        """The original flat circuit, if set."""
        return self._circuit

    @circuit.setter
    def circuit(self, value: Circuit) -> None:
        self._circuit = value

    # ── Level management ─────────────────────────────────────────────

    def add_level(self, level_circuit: StructureCircuit) -> None:
        """Register a :class:`StructureCircuit` for a hierarchy level."""
        self._levels[level_circuit.level] = level_circuit

    def get_level(self, level: int) -> StructureCircuit:
        """Return the :class:`StructureCircuit` for *level*.

        Raises
        ------
        KeyError
            If no circuit exists at *level*.
        """
        return self._levels[level]

    def has_level(self, level: int) -> bool:
        return level in self._levels

    def get_or_create_level(self, level: int) -> StructureCircuit:
        """Return the level circuit, creating it if absent."""
        if level not in self._levels:
            self._levels[level] = StructureCircuit(level)
        return self._levels[level]

    @property
    def hierarchy_levels(self) -> list[int]:
        """Sorted list of active hierarchy levels."""
        return sorted(self._levels.keys())

    @property
    def max_level(self) -> int:
        """Highest active hierarchy level.

        Raises
        ------
        ValueError
            If no levels exist.
        """
        if not self._levels:
            raise ValueError("No hierarchy levels")
        return max(self._levels.keys())

    # ── Structure queries ────────────────────────────────────────────

    def add_structure(self, structure: Structure, level: int) -> None:
        """Add a structure to the specified hierarchy level.

        Creates the level's :class:`StructureCircuit` if needed.
        """
        lc = self.get_or_create_level(level)
        lc.add_structure(structure)

    @property
    def all_structures(self) -> list[Structure]:
        """All structures across all levels (ordered by level)."""
        result: list[Structure] = []
        for level in sorted(self._levels):
            result.extend(self._levels[level].structures)
        return result

    def find_structures_by_name(self, name: str) -> list[Structure]:
        """Find all structures with the given template name across
        all levels."""
        result: list[Structure] = []
        for lc in self._levels.values():
            result.extend(lc.find_structures_by_name(name))
        return result

    @property
    def top_level_structures(self) -> list[Structure]:
        """Structures at the highest hierarchy level.

        These are the most abstract recognised structures.
        """
        if not self._levels:
            return []
        return self._levels[max(self._levels)].structures

    @property
    def structures_without_parents(self) -> list[Structure]:
        """All structures across all levels that have no parent."""
        result: list[Structure] = []
        for lc in self._levels.values():
            result.extend(lc.structures_without_parents)
        return result

    def find_connected_structures(self, net_name: str) -> list[Structure]:
        """All structures (any level) with a pin on *net_name*."""
        result: list[Structure] = []
        for lc in self._levels.values():
            result.extend(lc.find_connected_structures(net_name))
        return result

    def find_level_of(self, structure: Structure) -> int | None:
        """Return the hierarchy level of *structure*, or ``None``."""
        for level, lc in self._levels.items():
            if lc.has_structure(structure.structure_id):
                return level
        return None

    # ── Summary ──────────────────────────────────────────────────────

    @property
    def total_structures(self) -> int:
        """Total number of structures across all levels."""
        return sum(lc.num_structures for lc in self._levels.values())

    @property
    def total_nets(self) -> int:
        """Total number of nets across all levels."""
        return sum(lc.num_nets for lc in self._levels.values())

    def summary(self) -> str:
        """Human-readable summary of all levels."""
        lines = [f"StructureCircuits ({self.total_structures} structures, "
                 f"{self.total_nets} nets)"]
        for level in sorted(self._levels):
            lc = self._levels[level]
            lines.append(
                f"  Level {level}: {lc.num_structures} structures, "
                f"{lc.num_nets} nets"
            )
        return "\n".join(lines)

    # ── Dunder ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        levels = ", ".join(
            f"L{k}={v.num_structures}" for k, v in sorted(self._levels.items())
        )
        return f"StructureCircuits({levels})"

    def __len__(self) -> int:
        return self.total_structures

    def __contains__(self, structure_id: StructureId) -> bool:
        return any(
            lc.has_structure(structure_id) for lc in self._levels.values()
        )

    def __iter__(self) -> Iterator[Structure]:
        for level in sorted(self._levels):
            yield from self._levels[level]
