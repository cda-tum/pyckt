"""Sizing problem — assembles the complete CSP from circuit + specs + rules.

The :class:`SizingProblem` is the integration point for Week 6.
Its :meth:`build` classmethod wires together variables, transistor model
constraints, KCL, sizing rules, performance specs, and frequency-domain
constraints into one object that the solver consumes.

C++ ref: ``AutomaticSizing::ConstraintProgram``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .constraints import (
    Constraint,
    KCLConstraints,
    PolesAndZerosConstraints,
    SizingRuleConstraints,
    SpecConstraints,
    TransistorConstraints,
)
from .variables import SizingVariableRegistry

if TYPE_CHECKING:
    from partitioning.result import PartitionResult
    from pyckt.core.circuit import Circuit
    from pyckt.io.circuit_info_parser import (
        CircuitInformation,
    )
    from recognition.rulegen import SizingRule


# ═══════════════════════════════════════════════════════════════════════════
#  Sizing problem
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class SizingProblem:
    """Assembled constraint-satisfaction problem for transistor sizing.

    Attributes
    ----------
    variables : SizingVariableRegistry
        All integer variables (transistor bundles + net voltages).
    constraints : list[Constraint]
        Every constraint that the solver must satisfy.
    num_transistors : int
        Number of MOSFETs in the problem.
    num_nets : int
        Number of internal-net voltage variables.

    The canonical way to create a ``SizingProblem`` is via
    :meth:`build`, which runs a 7-step assembly sequence.
    """

    variables: SizingVariableRegistry = field(
        default_factory=SizingVariableRegistry,
    )
    constraints: list[Constraint] = field(default_factory=list)
    num_transistors: int = 0
    num_nets: int = 0
    # Retained context for performance estimation (set by build()).
    partition: object | None = None
    circuit: object | None = None
    circuit_info: object | None = None

    # ── Builder ──────────────────────────────────────────────────────

    @classmethod
    def build(
        cls,
        circuit: Circuit,
        partition: PartitionResult,
        rules: list[SizingRule],
        circuit_info: CircuitInformation,
    ) -> SizingProblem:
        """Assemble a complete sizing problem in 7 steps.

        Parameters
        ----------
        circuit : Circuit
            Flat transistor-level netlist.
        partition : PartitionResult
            Functional classification of recognised structures.
        rules : list[SizingRule]
            Sizing rules from structure recognition (matched pairs, etc.).
        circuit_info : CircuitInformation
            Bundled circuit parameters, specifications, and technology.

        Returns
        -------
        SizingProblem
            Ready to be handed to a :class:`SizingSolver`.

        Steps
        -----
        1. Create transistor variables for every MOSFET.
        2. Create voltage variables for every internal net.
        3. Add per-transistor SHM constraints.
        4. Add KCL constraints.
        5. Add sizing-rule constraints.
        6. Add performance-specification constraints.
        7. Add poles-and-zeros (frequency-domain) constraints.
        """
        from pyckt.core.device import DeviceType

        tech = circuit_info.technology
        specs = circuit_info.specifications
        params = circuit_info.parameters

        problem = cls()
        problem.partition = partition
        problem.circuit = circuit
        problem.circuit_info = circuit_info
        reg = problem.variables

        # ── Step 1: Transistor variables ─────────────────────────────
        for device in circuit.devices:
            if device.device_type == DeviceType.MOSFET:
                reg.add_transistor(device, tech.nmos, tech.pmos)

        problem.num_transistors = len(reg.transistors)

        # ── Step 2: Voltage variables for internal nets ──────────────
        supply_mv = int(params.supply_voltage[1] * 1000) if params.supply_voltage[1] else 5000
        for net in circuit.nets:
            if not net.is_power():
                reg.add_voltage(net.name, supply_mv)

        problem.num_nets = len(reg.voltages)

        # ── Step 3: Per-transistor SHM constraints ───────────────────
        for tv in reg.transistors.values():
            tc = TransistorConstraints(tv)
            problem.constraints.extend(tc.as_constraints())

        # ── Step 4: KCL constraints ──────────────────────────────────
        kcl = KCLConstraints(circuit, reg)
        problem.constraints.extend(kcl.as_constraints())

        # ── Step 5: Sizing-rule constraints ──────────────────────────
        src = SizingRuleConstraints(rules, reg)
        problem.constraints.extend(src.as_constraints())

        # ── Step 6: Performance-spec constraints ─────────────────────
        sc = SpecConstraints(specs, partition, reg, params, tech, circuit)
        problem.constraints.extend(sc.as_constraints())

        # ── Step 7: Poles-and-zeros constraints ──────────────────────
        pz = PolesAndZerosConstraints(partition, reg, specs, params)
        problem.constraints.extend(pz.as_constraints())

        return problem

    # ── Introspection ────────────────────────────────────────────────

    @property
    def num_variables(self) -> int:
        """Total number of individual solver variables."""
        return self.variables.total_variables

    @property
    def num_constraints(self) -> int:
        """Total number of constraints."""
        return len(self.constraints)

    def summary(self) -> str:
        """Human-readable summary of the assembled problem."""
        lines = [
            "SizingProblem Summary",
            "═" * 50,
            f"  Transistors      : {self.num_transistors}",
            f"  Internal nets    : {self.num_nets}",
            f"  Total variables  : {self.num_variables}",
            f"  Total constraints: {self.num_constraints}",
            "",
            "Constraint breakdown:",
        ]

        # Count by type
        counts: dict[str, int] = {}
        for c in self.constraints:
            key = type(c).__name__
            counts[key] = counts.get(key, 0) + 1

        for name in sorted(counts):
            lines.append(f"  {name:30s}: {counts[name]}")

        lines.append("")
        lines.append("Variables per transistor:")
        for name in sorted(self.variables.transistors):
            tv = self.variables.transistors[name]
            lines.append(
                f"  {name:>8s}  W=[{tv.width.lower}..{tv.width.upper}]  "
                f"L=[{tv.length.lower}..{tv.length.upper}]"
            )

        return "\n".join(lines)

    def __repr__(self) -> str:
        return (
            f"SizingProblem({self.num_transistors} transistors, "
            f"{self.num_variables} vars, {self.num_constraints} constraints)"
        )
