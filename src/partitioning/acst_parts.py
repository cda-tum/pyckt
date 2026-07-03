"""acst-faithful partition Part model.

A direct port of acst's ``Partitioning/Parts`` class family and the parts of
``Partitioning::Result`` the partitioner relies on.  Each :class:`Part` owns a
list of *main structures* (the recognised structures it is built from); the
:class:`AcstPartitionResult` keeps the structure→part registry that acst queries
via ``getPart`` / ``structureAlreadyClassified`` / ``getTransconductancePart``.

This model backs the acst-faithful partitioner (:mod:`partitioning.acst_partitioner`)
and the acst-format output writer.  It is independent of pyckt's native
``PartitionResult`` (which the native pipeline and its tests keep using).

C++ ref: ``Partitioning/incl/Parts/*.h`` and ``Partitioning/incl/Results/Result.h``.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from recognition.model import Structure


# ── Part hierarchy ────────────────────────────────────────────────────────


class Part:
    """Base class for every partition part.

    Attributes
    ----------
    main_structures : list[Structure]
        Recognised structures that make up this part.
    part_id : int
        Sequential id within its kind (assigned by the result registry).
    """

    kind: str = "part"

    def __init__(self, part_id: int = -1) -> None:
        self.part_id = part_id
        self.main_structures: list[Structure] = []

    def add_main_structure(self, structure: "Structure", result=None) -> None:
        """Add *structure* and, when *result* is given, immediately own its
        array leaves (acst ``Part::addMainStructure`` always registers via
        ``initializeComponents`` at add time — before the part itself is added
        to the result)."""
        if not self.has_as_main_structure(structure):
            self.main_structures.append(structure)
            if result is not None:
                result.register(self, structure)

    def has_as_main_structure(self, structure: "Structure") -> bool:
        return any(s is structure for s in self.main_structures)

    @property
    def has_main_structures(self) -> bool:
        return bool(self.main_structures)

    def devices(self) -> list[str]:
        """Leaf device names across all main structures (sorted, de-duped)."""
        names: set[str] = set()
        for s in self.main_structures:
            names.update(d.name for d in s.devices)
        return sorted(names)

    # part-kind predicates (mirror acst)
    def is_transconductance(self) -> bool: return False
    def is_load(self) -> bool: return False
    def is_bias(self) -> bool: return False
    def is_capacitance(self) -> bool: return False
    def is_undefined(self) -> bool: return False

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id={self.part_id}, devs={self.devices()})"


class TransconductancePart(Part):
    """A gm part: input diff pair, or a (primary/secondary) second-stage gm.

    ``type`` is one of ``firstStage`` / ``primarySecondStage`` /
    ``secondarySecondStage`` / ``thirdStage`` / ``feedBack``.
    ``first_stage_type`` (only meaningful for the first stage) is one of
    ``symmetrical`` / ``complementary`` / ``simple`` / ``telescopic`` /
    ``foldedCascode``.
    """

    kind = "transconductance"

    def __init__(self, part_id: int = -1) -> None:
        super().__init__(part_id)
        self.type: str = ""
        self.first_stage_type: str | None = None
        self.helper_structure: "Structure | None" = None
        self.load_parts: list[LoadPart] = []
        self.bias_parts: list[BiasPart] = []

    def is_transconductance(self) -> bool: return True
    def is_first_stage(self) -> bool: return self.type == "firstStage"
    def is_primary_second_stage(self) -> bool: return self.type == "primarySecondStage"
    def is_secondary_second_stage(self) -> bool: return self.type == "secondarySecondStage"
    def is_second_stage(self) -> bool:
        return self.type in ("primarySecondStage", "secondarySecondStage")
    def is_feedback(self) -> bool: return self.type == "feedBack"


class LoadPart(Part):
    """Active/diode load of a transconductance stage."""

    kind = "load"

    def __init__(self, part_id: int = -1) -> None:
        super().__init__(part_id)
        self.cascoded_pair: "Structure | None" = None
        # gate-driving voltage biases attached by findBiasOfLoadPart (a load
        # part can itself serve as another load's bias, hence Part)
        self.bias_parts: list[Part] = []
        # a folded-cascode pair's current-source arrays (acst
        # addCurrentBiasOfFoldedPair)
        self.current_biases_of_folded_pair: list["Structure"] = []

    def is_load(self) -> bool: return True


class BiasPart(Part):
    """Bias of a stage.  ``type`` is ``currentBias`` or ``voltageBias``."""

    kind = "bias"

    def __init__(self, part_id: int = -1) -> None:
        super().__init__(part_id)
        self.type: str = ""
        self.biased_parts: list[Part] = []

    def add_biased_part(self, part: Part) -> None:
        if part not in self.biased_parts:
            self.biased_parts.append(part)

    def is_bias(self) -> bool: return True


class CapacitancePart(Part):
    """Capacitance.  ``type`` is ``load`` or ``compensation``."""

    kind = "capacitance"

    def __init__(self, part_id: int = -1) -> None:
        super().__init__(part_id)
        self.type: str = ""

    def is_capacitance(self) -> bool: return True


class UndefinedPart(Part):
    """Anything not otherwise classified."""

    kind = "undefined"

    def is_undefined(self) -> bool: return True


# ── Result registry ───────────────────────────────────────────────────────


class AcstPartitionResult:
    """Holds all parts and the structure→part registry.

    Mirrors the subset of ``Partitioning::Result`` the partitioner needs.
    """

    def __init__(self) -> None:
        self.transconductance_parts: list[TransconductancePart] = []
        self.load_parts: list[LoadPart] = []
        self.bias_parts: list[BiasPart] = []
        self.capacitance_parts: list[CapacitancePart] = []
        self.undefined_parts: list[UndefinedPart] = []
        # array-leaf id → owning Part.  acst's registry is leaf-based
        # (Result::transistors_/twoPorts_, filled by Part::initializeComponents
        # the moment a main structure is added): classifying any structure
        # classifies its array leaves, "already classified" means *all* leaves
        # are owned, and getPart resolves any ancestor through its first owned
        # leaf.  Keying by exact structure object instead left pairs' arrays
        # "unclassified", so later sweeps re-classified the same devices
        # (issue #32's biasPart flood).
        self._registry: dict[int, Part] = {}
        self._counters: dict[str, int] = {}

    # ── id allocation ─────────────────────────────────────────────────
    def next_id(self, kind: str) -> int:
        n = self._counters.get(kind, 0)
        self._counters[kind] = n + 1
        return n

    # ── registration ──────────────────────────────────────────────────
    def register(self, part: Part, structure: "Structure") -> None:
        """Own *structure*'s array leaves (acst ``Part::initializeComponents``)."""
        for leaf in structure.array_children:
            self._registry.setdefault(id(leaf), part)

    def _register(self, part: Part) -> None:
        for s in part.main_structures:
            self.register(part, s)

    def add_transconductance_part(self, part: TransconductancePart) -> None:
        self.transconductance_parts.append(part); self._register(part)

    def add_load_part(self, part: LoadPart) -> None:
        self.load_parts.append(part); self._register(part)

    def add_bias_part(self, part: BiasPart) -> None:
        self.bias_parts.append(part); self._register(part)

    def add_capacitance_part(self, part: CapacitancePart) -> None:
        self.capacitance_parts.append(part); self._register(part)

    def add_undefined_part(self, part: UndefinedPart) -> None:
        self.undefined_parts.append(part); self._register(part)

    # ── queries (mirror acst Result) ──────────────────────────────────
    def structure_already_classified(self, structure: "Structure") -> bool:
        leaves = structure.array_children
        if not leaves:
            return False
        return all(id(leaf) in self._registry for leaf in leaves)

    def get_part(self, structure: "Structure") -> Part | None:
        for leaf in structure.array_children:
            part = self._registry.get(id(leaf))
            if part is not None:
                return part
        return None

    def get_transconductance_part(
        self, structure: "Structure"
    ) -> TransconductancePart | None:
        part = self.get_part(structure)
        return part if isinstance(part, TransconductancePart) else None

    def has_first_stage(self) -> bool:
        return any(t.is_first_stage() for t in self.transconductance_parts)

    def get_first_stage(self) -> TransconductancePart | None:
        for t in self.transconductance_parts:
            if t.is_first_stage():
                return t
        return None

    def get_second_stages(self) -> list[TransconductancePart]:
        return [t for t in self.transconductance_parts if t.is_second_stage()]

    def has_second_stage(self) -> bool:
        return bool(self.get_second_stages())

    def has_secondary_second_stage(self) -> bool:
        return any(t.is_secondary_second_stage() for t in self.transconductance_parts)
