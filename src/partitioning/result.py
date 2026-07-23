"""Partitioning result data structures.

Defines the classification enums, per-structure assignment record, and the
aggregate :class:`PartitionResult` container used by the partitioner and
consumed by the sizing pipeline.

C++ ref: ``Partitioning/incl/Results/Result.h``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from recognition.model import Structure


# ── Enumerations ─────────────────────────────────────────────────────

class PartType(Enum):
    """Functional role of a structure within an op-amp."""
    TRANSCONDUCTANCE = "transconductance"
    LOAD = "load"
    BIAS = "bias"
    CAPACITANCE = "capacitance"
    UNDEFINED = "undefined"


class StageType(Enum):
    """Amplifier stage a structure belongs to."""
    FIRST = "first"
    SECOND = "second"
    COMPENSATION = "compensation"
    UNDEFINED = "undefined"


# ── Per-structure assignment ─────────────────────────────────────────

@dataclass
class PartAssignment:
    """Classification of a single recognised structure.

    Attributes
    ----------
    structure : Structure
        The recognised structure this assignment refers to.
    part_type : PartType
        Functional role (transconductance, load, bias, …).
    stage : StageType
        Which amplifier stage the structure belongs to.
    role_description : str
        Human-readable label, e.g. ``"input differential pair"``.
    """

    structure: Structure
    part_type: PartType
    stage: StageType
    role_description: str = ""


# ── Aggregate result ─────────────────────────────────────────────────

class PartitionResult:
    """Complete partitioning of a circuit's recognised structures.

    Maps to C++ ``Partitioning::Result``.  Stores a
    ``{structure_id → PartAssignment}`` mapping and exposes convenience
    accessors for querying by role and stage.
    """

    def __init__(self) -> None:
        self._assignments: dict[int, PartAssignment] = {}

    # ── Mutation ─────────────────────────────────────────────────────

    def assign(
        self,
        structure: Structure,
        part_type: PartType,
        stage: StageType,
        description: str = "",
    ) -> None:
        """Assign a classification to *structure*."""
        self._assignments[id(structure)] = PartAssignment(
            structure=structure,
            part_type=part_type,
            stage=stage,
            role_description=description,
        )

    # ── Queries ──────────────────────────────────────────────────────

    def get_part(self, structure: Structure) -> PartAssignment | None:
        """Return the assignment for *structure*, or ``None``."""
        return self._assignments.get(id(structure))

    def is_classified(self, structure: Structure) -> bool:
        """``True`` if *structure* has already been assigned."""
        return id(structure) in self._assignments

    @property
    def all_assignments(self) -> list[PartAssignment]:
        """All recorded assignments (insertion order)."""
        return list(self._assignments.values())

    # ── Role-based accessors ─────────────────────────────────────────

    def transconductance_parts(
        self, stage: StageType | None = None
    ) -> list[Structure]:
        """Return structures classified as transconductance.

        If *stage* is given, filter to that stage only.
        """
        return [
            a.structure for a in self._assignments.values()
            if a.part_type is PartType.TRANSCONDUCTANCE
            and (stage is None or a.stage is stage)
        ]

    def load_parts(self, stage: StageType | None = None) -> list[Structure]:
        """Return structures classified as load."""
        return [
            a.structure for a in self._assignments.values()
            if a.part_type is PartType.LOAD
            and (stage is None or a.stage is stage)
        ]

    def bias_parts(self, stage: StageType | None = None) -> list[Structure]:
        """Return structures classified as bias."""
        return [
            a.structure for a in self._assignments.values()
            if a.part_type is PartType.BIAS
            and (stage is None or a.stage is stage)
        ]

    def capacitance_parts(self) -> list[Structure]:
        """Return structures classified as capacitance."""
        return [
            a.structure for a in self._assignments.values()
            if a.part_type is PartType.CAPACITANCE
        ]

    def undefined_parts(self) -> list[Structure]:
        """Return structures not yet meaningfully classified."""
        return [
            a.structure for a in self._assignments.values()
            if a.part_type is PartType.UNDEFINED
        ]

    # ── Derived properties ───────────────────────────────────────────

    def is_two_stage(self) -> bool:
        """``True`` if a second-stage transconductance part was identified."""
        return len(self.transconductance_parts(StageType.SECOND)) > 0

    @property
    def total(self) -> int:
        """Total number of classified structures."""
        return len(self._assignments)

    # ── Display ──────────────────────────────────────────────────────

    def summary(self) -> str:
        """One-line summary string for logging."""
        from collections import Counter
        c = Counter(a.part_type.value for a in self._assignments.values())
        parts = ", ".join(f"{v}={n}" for v, n in sorted(c.items()))
        stage = "two-stage" if self.is_two_stage() else "single-stage"
        return f"{self.total} structures ({stage}): {parts}"

    def __repr__(self) -> str:
        return f"PartitionResult({self.total} assignments)"
