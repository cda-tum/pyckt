"""Recognition-rule learning — acst-style ``rulegen`` artifact.

acst's ``rulegen`` analysis does **not** emit sizing rules (that is pyckt's
native :class:`~recognition.rulegen.RuleGenerator`).  Instead it *learns a
recognition library*: it recognises the flat circuit, then bottom-up pairs the
surviving top structures into new named composite ``pairLibraryItem`` s
(``<StructureName>1``, ``2`` …) until the whole op-amp is one learned structure,
and writes them as a reusable ``pairLibrary``.

This module ports that learning loop (``StructRec::PairLibraryItemCreator`` /
``NewPairLibraryItem`` / ``StructureRecognitionRuleGeneration``) onto pyckt's
recognition hierarchy.  Rather than re-running recognition each round (acst's
``recognizeOnStructuresWithoutParents``) it builds the composite directly when a
pair is selected — the connectivity it needs comes from the structures' own
pins.

C++ ref: ``StructRec/src/RuleGeneration/*`` and
``StructureRecognitionRuleGeneration::compute``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from recognition.model import StructureCircuits

_BULK = "Bulk"


# ── learning-time node + output item ──────────────────────────────────────


@dataclass
class _Pin:
    name: str          # pin name on this node
    net: str           # electrical net name
    supply: str        # "vdd" | "gnd" | ""  (for net / supply rules)
    child: int = 0     # which child this pin came from (1/2), set on composites
    child_struct: str = ""   # owning child structure name
    child_pin: str = ""      # pin name on the child structure


@dataclass
class _Node:
    """A structure in the learning hierarchy (recognised leaf or learned pair)."""
    name: str
    tech: str
    level: int
    pins: list[_Pin]
    devices: tuple[str, ...]
    child1: "_Node | None" = None
    child2: "_Node | None" = None

    def signal_pins(self) -> list[_Pin]:
        return [p for p in self.pins if p.name != _BULK]


@dataclass
class LearnedItem:
    """One learned composite ``pairLibraryItem``."""
    name: str
    level: int
    child1_name: str
    child2_name: str
    symmetric: bool = False
    persistence: int | None = None   # None → MAX (never pruned)
    # composite pin name → (child_number, child_struct_name, child_pin_name)
    pair_connection: list[tuple[str, int, str, str]] = field(default_factory=list)
    # characteristic: (child1_struct, child1_pin, [(child2_struct, child2_pin)])
    characteristic: tuple[str, str, list[tuple[str, str]]] | None = None
    # (c1_struct, c1_pin, c2_struct, c2_pin, connected)
    connection_rules: list[tuple[str, str, str, str, bool]] = field(default_factory=list)
    tech_type_rule: str = "noRule"


@dataclass
class LearnedLibrary:
    """Result of rule learning: the items plus their hierarchy levels."""
    items: list[LearnedItem]
    base_name: str

    def levels(self) -> dict[int, list[LearnedItem]]:
        out: dict[int, list[LearnedItem]] = {}
        for item in self.items:
            out.setdefault(item.level, []).append(item)
        return dict(sorted(out.items()))


# ── the learner ───────────────────────────────────────────────────────────


class RuleLearner:
    """Learn a recognition library from a recognised circuit (acst rulegen)."""

    def __init__(self, base_name: str) -> None:
        self._base = base_name
        self._id = 1
        self._items: list[LearnedItem] = []
        self._by_name: dict[str, LearnedItem] = {}

    def learn(self, sc: "StructureCircuits") -> LearnedLibrary:
        roots = [
            self._to_node(s, sc.find_level_of(s) or 0)
            for s in sc.structures_without_parents
        ]
        # iteratively pair the surviving roots until a single structure remains
        guard = 0
        while len(roots) > 1 and guard < 100:
            guard += 1
            paired = self._pair_round(roots)
            if not paired:
                break
            roots = paired
        self._compute_persistence()
        logger.info("Rule learning: {} composite items, top roots {}",
                    len(self._items), len(roots))
        return LearnedLibrary(items=list(self._items), base_name=self._base)

    # ── one pairing round ─────────────────────────────────────────────

    def _pair_round(self, roots: list[_Node]) -> list[_Node]:
        # candidate pairs ranked by weighted shared-net count (desc), then
        # preferring equal hierarchy level and equal tech type (acst order).
        net_roots = self._net_to_roots(roots)
        candidates = []
        for a, b in combinations(roots, 2):
            conns = self._count_connections(a, b)
            if conns <= 0:
                continue
            same_level = a.level == b.level
            same_tech = a.tech == b.tech and a.tech not in ("", "undefined")
            rank = (conns, same_level and same_tech, same_tech,
                    -abs(a.level - b.level))
            candidates.append((rank, a, b))
        candidates.sort(key=lambda c: c[0], reverse=True)

        used: set[int] = set()
        composites: list[_Node] = []
        for _rank, a, b in candidates:
            if id(a) in used or id(b) in used:
                continue
            used.add(id(a)); used.add(id(b))
            composites.append(self._make_pair(a, b, net_roots))

        if not composites:
            return roots
        # carry over the roots that weren't paired this round
        carried = [r for r in roots if id(r) not in used]
        return composites + carried

    # ── build one composite + its learned item ────────────────────────

    def _make_pair(self, c1: _Node, c2: _Node,
                   net_roots: dict[str, list[int]]) -> _Node:
        # order children low→high hierarchy level (acst convention)
        if c2.level < c1.level:
            c1, c2 = c2, c1
        name = f"{self._base}{self._id}"
        self._id += 1
        level = max(c1.level, c2.level) + 1

        # pin-connection analysis (non-Bulk pins)
        shared: list[tuple[_Pin, _Pin]] = []
        for p1 in c1.signal_pins():
            for p2 in c2.signal_pins():
                if p1.net == p2.net:
                    shared.append((p1, p2))

        # connection rules: every cross pin pair, connected or not
        conn_rules: list[tuple[str, str, str, str, bool]] = []
        for p1 in c1.signal_pins():
            for p2 in c2.signal_pins():
                conn_rules.append((c1.name, p1.name, c2.name, p2.name,
                                   p1.net == p2.net))

        # characteristic: first shared net between the children
        characteristic = None
        if shared:
            p1, _ = shared[0]
            seconds = [(c2.name, q.name) for q in c2.signal_pins()
                       if q.net == p1.net]
            characteristic = (c1.name, p1.name, seconds)

        tech_rule = ("same" if c1.tech == c2.tech and c1.tech not in ("", "undefined")
                     else "different" if c1.tech != c2.tech else "noRule")

        # composite external pins: one per distinct net that leaves {c1, c2}
        internal_pair = {id(c1), id(c2)}
        pair_conn: list[tuple[str, int, str, str]] = []
        comp_pins: list[_Pin] = []
        seen_net: set[str] = set()
        for child_num, child in ((1, c1), (2, c2)):
            for p in child.signal_pins():
                if p.net in seen_net:
                    continue
                others = [r for r in net_roots.get(p.net, []) if r not in internal_pair]
                is_supply = bool(p.supply)
                # expose nets that reach outside the pair (or are supply rails)
                if others or is_supply:
                    seen_net.add(p.net)
                    pair_conn.append((p.net, child_num, child.name, p.name))
                    comp_pins.append(_Pin(p.net, p.net, p.supply))

        item = LearnedItem(
            name=name, level=level, child1_name=c1.name, child2_name=c2.name,
            pair_connection=pair_conn, characteristic=characteristic,
            connection_rules=conn_rules, tech_type_rule=tech_rule,
        )
        self._items.append(item)
        self._by_name[name] = item

        return _Node(
            name=name, tech=(c1.tech if c1.tech == c2.tech else "undefined"),
            level=level, pins=comp_pins,
            devices=tuple(sorted(set(c1.devices) | set(c2.devices))),
            child1=c1, child2=c2,
        )

    # ── persistence: parent level − child level (max), acst rule ───────

    def _compute_persistence(self) -> None:
        for item in self._items:
            for child_name in (item.child1_name, item.child2_name):
                child = self._by_name.get(child_name)
                if child is None:   # a base library structure, not learned
                    continue
                diff = item.level - child.level
                if child.persistence is None or child.persistence < diff:
                    child.persistence = diff

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _count_connections(a: _Node, b: _Node) -> int:
        total = 0
        for p1 in a.signal_pins():
            for p2 in b.signal_pins():
                if p1.net == p2.net:
                    total += 2 if p1.supply else 3
        return total

    @staticmethod
    def _net_to_roots(roots: list[_Node]) -> dict[str, list[int]]:
        index: dict[str, list[int]] = {}
        for r in roots:
            for p in r.signal_pins():
                index.setdefault(p.net, []).append(id(r))
        return index

    def _to_node(self, structure, level: int) -> _Node:
        pins: list[_Pin] = []
        for pin_name, pin in structure.pins.items():
            try:
                net = pin.net
            except RuntimeError:
                continue
            supply = "vdd" if net.is_vdd() else "gnd" if net.is_ground() else ""
            pins.append(_Pin(pin_name, net.name, supply))
        return _Node(
            name=structure.name, tech=structure.tech_type.value, level=level,
            pins=pins, devices=tuple(sorted(d.name for d in structure.devices)),
        )
