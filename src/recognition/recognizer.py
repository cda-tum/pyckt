"""Structure Recognition Engine — bottom-up hierarchical recognition.

Transforms a flat :class:`~pyckt.core.Circuit` into a hierarchical
:class:`StructureCircuits` overlay by matching library templates:

    Level 0 → Arrays  |  Levels 1–3 → Pairs (with dominance resolution)

Also includes rule generation and XML writers.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from loguru import logger

from pyckt.core.device import Device, PinType
from pyckt.core.net import Net

from .library import (
    PERSISTENCE_MAX,
    ArrayConnectionRule,
    ArrayLibrary,
    ArrayLibraryItem,
    CharacteristicConnection,
    Library,
    PairConnectionRule,
    PairLibrary,
    PairLibraryItem,
    PairNetRule,
)
from .model import (
    ArrayStructure,
    PairStructure,
    Structure,
    StructureCircuits,
    StructureId,
    StructureNet,
    StructurePin,
)

if TYPE_CHECKING:
    from pyckt.core.circuit import Circuit


# ── Helpers ──────────────────────────────────────────────────────────

def _get_device_net(device: Device, pin_name: str) -> Net | None:
    """Safely get the net on *device*'s *pin_name*, or ``None``."""
    try:
        return device.get_net(PinType.from_text(pin_name))
    except (KeyError, Exception):
        return None


# ═════════════════════════════════════════════════════════════════════
#  Array Recognition (Level 0)
# ═════════════════════════════════════════════════════════════════════

class ArrayRecognizer:
    """Groups devices into arrays by template matching + parallel-net keys.

    C++ ref: ``StructRec::CreateArrays``
    """

    def __init__(self, array_library: ArrayLibrary) -> None:
        self._library = array_library

    def recognize(self, circuit: Circuit) -> list[ArrayStructure]:
        groups: dict[str, dict[tuple, ArrayStructure]] = defaultdict(dict)
        counters: dict[str, int] = defaultdict(int)
        result: list[ArrayStructure] = []

        for device in circuit.devices:
            template = self._classify(device)
            if template is None:
                continue
            key = self._grouping_key(device, template)
            if key in groups[template.name]:
                groups[template.name][key].add_device(device)
            else:
                idx = counters[template.name]; counters[template.name] += 1
                arr = self._create_array(device, template, idx)
                groups[template.name][key] = arr
                result.append(arr)

        logger.info("Array recognition: {} arrays from {} devices",
                     len(result), len(circuit.devices))
        return result

    def _classify(self, device: Device) -> ArrayLibraryItem | None:
        for entry in self._library.active:
            item = self._library.get_item(entry.name)
            if device.device_type.value.lower() != item.device_type_rule.lower():
                continue
            if not self._conn_rules_ok(device, item.connection_rules):
                continue
            return item
        return None

    @staticmethod
    def _conn_rules_ok(device: Device, rules: list[ArrayConnectionRule]) -> bool:
        for r in rules:
            n1, n2 = _get_device_net(device, r.pin1.pin_name), _get_device_net(device, r.pin2.pin_name)
            if n1 is None or n2 is None:
                return False
            same = n1.name == n2.name
            if r.connected != same:
                return False
        return True

    @staticmethod
    def _grouping_key(device: Device, tpl: ArrayLibraryItem) -> tuple:
        parts = [tpl.name, device.tech_type.value]
        for pn in tpl.parallel_nets:
            net = _get_device_net(device, pn.pin_name)
            parts.append(net.name if net else "?")
        return tuple(parts)

    def _create_array(self, device: Device, tpl: ArrayLibraryItem, idx: int) -> ArrayStructure:
        arr = ArrayStructure(StructureId(tpl.name, idx), device.tech_type, device_list=[device])
        for conn in tpl.connections:
            pin = StructurePin(name=conn.structure_pin.pin_name)
            arr.add_pin(pin)
            dnet = _get_device_net(device, conn.device_pin.pin_name)
            if dnet is not None:
                StructureNet(dnet.name, core_net=dnet).add_pin(pin)
        return arr


# ═════════════════════════════════════════════════════════════════════
#  Pair Recognition (Levels 1–3)
# ═════════════════════════════════════════════════════════════════════

class PairRecognizer:
    """Recognises *all* matching pairs at one hierarchy level.

    Unlike a greedy/exclusive matcher, this mirrors acst's
    ``HierarchyLevel::recognize``: every library template that matches is
    instantiated, and child structures may be **shared** across several
    parents.  Conflicts are resolved afterwards by the orchestrator via
    dominance removal and persistence-based pruning (see
    :class:`StructureRecognizer`).

    C++ ref: ``StructRec::HierarchyLevel`` / ``PairLibrary``.
    """

    def __init__(self, pair_library: PairLibrary, level: int) -> None:
        self._library = pair_library
        self._level = level
        self._entries = pair_library.get_level_entries(level)

    def recognize(self, children: list[Structure]) -> list[PairStructure]:
        """Return every pair that matches a level-*N* template over *children*.

        *children* are all surviving lower-level structures.  No structure is
        consumed: a child may appear in multiple returned pairs.  Each pair's
        :attr:`persistence` is taken from its library hierarchy entry.
        """
        seen: set[tuple[str, frozenset[int]]] = set()
        counters: dict[str, int] = defaultdict(int)
        pairs: list[PairStructure] = []
        for entry in self._entries:
            item = self._library.get_item(entry.name)
            for a in children:
                for b in children:
                    if a is b:
                        continue
                    if not self._matches(item, a, b):
                        continue
                    key = (item.name, frozenset((id(a), id(b))))
                    if key in seen:
                        continue
                    seen.add(key)
                    if item.is_helper_structure:
                        # Helper structures are recognition scaffolding: acst
                        # does not instantiate them, it only pins their children
                        # to MAX persistence so those children survive as
                        # standalone top-level structures.  (PairLibraryItem::
                        # recognize, isHelperStructure branch.)
                        a.persistence = b.persistence = PERSISTENCE_MAX
                        continue
                    idx = counters[item.name]
                    counters[item.name] += 1
                    c1, c2 = a, b
                    if item.symmetry:
                        # canonical child order: smaller leaf device name → child1
                        def _sort_key(s: Structure) -> str:
                            devs = s.devices
                            return min(d.name for d in devs) if devs else str(s.structure_id.index)
                        if _sort_key(a) > _sort_key(b):
                            c1, c2 = b, a
                    pairs.append(
                        self._build_pair(item, c1, c2, idx, entry.persistence)
                    )
        logger.info("Level {} pair recognition: {} candidate pairs",
                    self._level, len(pairs))
        return pairs

    def _matches(self, item: PairLibraryItem, c1: Structure, c2: Structure) -> bool:
        return (self._check_characteristic(item.characteristic, c1, c2)
                and self._check_tech_type(item.tech_type_rule, c1, c2)
                and self._check_net_rules(item.net_rules, c1, c2)
                and self._check_conn_rules(item.connection_rules, c1, c2))

    # ── constraint checkers ──────────────────────────────────────────

    @staticmethod
    def _check_characteristic(char: CharacteristicConnection, c1: Structure, c2: Structure) -> bool:
        if c1.name != char.first_child_pin.structure_name:
            return False
        p1 = char.first_child_pin.pin_name
        if not c1.has_pin(p1):
            return False
        n1 = c1.get_pin(p1).net
        for sp in char.second_child_pins:
            if c2.name != sp.structure_name or not c2.has_pin(sp.pin_name):
                continue
            try:
                if c2.get_pin(sp.pin_name).net.name == n1.name:
                    return True
            except RuntimeError:
                continue
        return False

    @staticmethod
    def _check_tech_type(rule: str, c1: Structure, c2: Structure) -> bool:
        if rule == "same":    return c1.tech_type == c2.tech_type
        if rule == "different": return c1.tech_type != c2.tech_type
        return True  # "noRule" or unknown

    @staticmethod
    def _check_net_rules(rules: list[PairNetRule], c1: Structure, c2: Structure) -> bool:
        for r in rules:
            child = c1 if r.child_number == 1 else c2
            if r.structure_pin.structure_name != child.name or not child.has_pin(r.structure_pin.pin_name):
                return False
            try:
                snet = child.get_pin(r.structure_pin.pin_name).net
            except RuntimeError:
                return False
            s = r.supply.lower().strip()
            if s == "supply"    and not snet.is_supply():  return False
            if s == "no_supply" and snet.is_supply():      return False
            if s == "vdd"       and not snet.is_vdd():     return False
            if s == "gnd"       and not snet.is_ground():  return False
        return True

    @staticmethod
    def _check_conn_rules(rules: list[PairConnectionRule], c1: Structure, c2: Structure) -> bool:
        for r in rules:
            if r.first_child_pin.structure_name != c1.name or r.second_child_pin.structure_name != c2.name:
                return False
            p1, p2 = r.first_child_pin.pin_name, r.second_child_pin.pin_name
            if not c1.has_pin(p1) or not c2.has_pin(p2):
                return False
            try:
                same = c1.get_pin(p1).net.name == c2.get_pin(p2).net.name
            except RuntimeError:
                return False
            if r.connected != same:
                return False
        return True

    # ── pair construction ────────────────────────────────────────────

    def _build_pair(
        self, item: PairLibraryItem, c1: Structure, c2: Structure,
        idx: int, persistence: int,
    ) -> PairStructure:
        pair = PairStructure(StructureId(item.name, idx),
                             c1, c2, item.symmetry, c1.tech_type)
        pair.persistence = persistence
        for m in item.connections:
            pin = StructurePin(name=m.pair_pin.pin_name); pair.add_pin(pin)
            child = pair.get_child(m.child_pin.child_number)
            cpn = m.child_pin.structure_pin.pin_name
            if child.has_pin(cpn):
                try:
                    cn = child.get_pin(cpn).net
                    StructureNet(cn.name, core_net=cn.core_net, supply=cn.supply).add_pin(pin)
                except RuntimeError:
                    pass
        return pair


# ═════════════════════════════════════════════════════════════════════
#  Orchestrator
# ═════════════════════════════════════════════════════════════════════

class StructureRecognizer:
    """Top-level recognition engine.

    Drives bottom-up recognition the way acst's ``PairLibrary::recognize``
    does: for each hierarchy level, recognise *all* matching pairs (children
    shared, not consumed), then remove dominated structures and prune
    *uncertain* ones (parentless structures whose persistence has expired).

    C++ ref: ``StructRec::StructureCore`` / ``PairLibrary::recognize``.
    """

    def __init__(self, library: Library) -> None:
        self._library = library
        self._name_to_level: dict[str, int] = {}
        self._name_to_persistence: dict[str, int] = {}

    def recognize(self, circuit: Circuit) -> StructureCircuits:
        result = StructureCircuits(circuit=circuit)
        self._build_registers()

        arrays = ArrayRecognizer(self._library.array_library).recognize(circuit)
        level0 = result.get_or_create_level(0)
        for a in arrays:
            level0.add_structure(a)

        for lvl in self._library.pair_library.hierarchy_levels:
            lower = self._structures_below(result, lvl)
            pairs = PairRecognizer(self._library.pair_library, lvl).recognize(lower)
            lc = result.get_or_create_level(lvl)
            for p in pairs:
                lc.add_structure(p)
            self._remove_dominated(result, lvl)
            self._remove_uncertain(result, lvl)

        logger.info("Recognition complete: {}", result.summary())
        return result

    # ── registers (name → level / persistence) ───────────────────────

    def _build_registers(self) -> None:
        self._name_to_level.clear()
        self._name_to_persistence.clear()
        for level, entries in self._library.pair_library.levels.items():
            for entry in entries:
                self._name_to_level[entry.name] = level
                self._name_to_persistence[entry.name] = entry.persistence

    def _structures_below(
        self, result: StructureCircuits, level: int
    ) -> list[Structure]:
        """All surviving structures at levels ``0 .. level-1``."""
        out: list[Structure] = []
        for lvl in range(level):
            if result.has_level(lvl):
                out.extend(result.get_level(lvl).structures)
        return out

    # ── dominance removal (after each level) ──────────────────────────

    def _remove_dominated(self, result: StructureCircuits, level: int) -> None:
        for dr in self._library.pair_library.dominance:
            if dr.for_current_mirrors:
                self._apply_cm_dominance(result, dr)
            else:
                self._apply_general_dominance(result, dr, level)

    def _apply_cm_dominance(self, result: StructureCircuits, dr) -> None:
        """A current mirror dominates sub-mirrors sharing both its children.

        C++ ref: ``DominanceRelationForCurrentMirrors::removeDominatedStructures``.
        """
        for dom_name in dr.dominating:
            lvl = self._name_to_level.get(dom_name)
            if lvl is None or not result.has_level(lvl):
                continue
            for cm in result.get_level(lvl).find_structures_by_name(dom_name):
                if not cm.is_pair:
                    continue
                c1, c2 = cm.child1, cm.child2
                for sub_name in dr.dominated:
                    slvl = self._name_to_level.get(sub_name)
                    if slvl is None or not result.has_level(slvl):
                        continue
                    for s in list(result.get_level(slvl).find_structures_by_name(sub_name)):
                        if s.has_common_devices(c1) and s.has_common_devices(c2):
                            self._disconnect(result, s)

    def _apply_general_dominance(
        self, result: StructureCircuits, dr, level: int
    ) -> None:
        """A dominating structure removes dominated parents of shared leaves.

        C++ ref: ``DominanceRelation::removeDominatedStructures``.
        """
        dominating = set(dr.dominating)
        dominated = set(dr.dominated)
        for dom_name in dr.dominating:
            lvl = self._name_to_level.get(dom_name)
            if lvl is None or not result.has_level(lvl):
                continue
            persistence = self._name_to_persistence.get(dom_name, PERSISTENCE_MAX)
            expired = (persistence == PERSISTENCE_MAX) or (persistence + lvl <= level)
            if not expired:
                continue
            for dstruct in result.get_level(lvl).find_structures_by_name(dom_name):
                for leaf in dstruct.array_children:
                    ancestors = self._ancestors(leaf)
                    if any(p.name in dominating for p in ancestors):
                        for p in list(ancestors):
                            if p.name in dominated:
                                self._disconnect(result, p)

    # ── uncertain pruning (after each level) ──────────────────────────

    def _remove_uncertain(self, result: StructureCircuits, current_max: int) -> None:
        """Prune parentless structures whose persistence has expired.

        C++ ref: ``StructureCircuits::removeUncertainStructures``.
        """
        for lvl in range(current_max - 1, -1, -1):
            if not result.has_level(lvl):
                continue
            for s in list(result.get_level(lvl).structures):
                if (not s.has_max_persistence
                        and not s.has_parent
                        and current_max >= lvl + s.persistence):
                    self._disconnect(result, s)

    # ── graph helpers ─────────────────────────────────────────────────

    @staticmethod
    def _ancestors(structure: Structure) -> list[Structure]:
        """All transitive parents of *structure* (breadth-first)."""
        seen: set[int] = set()
        out: list[Structure] = []
        frontier = list(structure.parents)
        while frontier:
            p = frontier.pop()
            if id(p) in seen:
                continue
            seen.add(id(p))
            out.append(p)
            frontier.extend(p.parents)
        return out

    def _disconnect(self, result: StructureCircuits, s: Structure) -> None:
        """Remove *s* from its level circuit and unlink it from its children."""
        lvl = result.find_level_of(s)
        if lvl is not None and result.has_level(lvl):
            circuit = result.get_level(lvl)
            if circuit.has_structure(s.structure_id):
                circuit.remove_structure(s)
        if s.is_pair:
            for child in (s.child1, s.child2):
                try:
                    child.remove_parent(s)
                except ValueError:
                    pass


# ═════════════════════════════════════════════════════════════════════
#  Re-exports (rule generation and writers live in their own modules)
# ═════════════════════════════════════════════════════════════════════

from .rulegen import (  # noqa: F401 – re-exported for backward compat
    EqualCurrentRule,
    EqualLengthRule,
    EqualWLRule,
    MatchedPairRule,
    RuleGenerator,
    SizingRule,
)
from .writer import RuleXMLWriter, StructRecXMLWriter  # noqa: F401
